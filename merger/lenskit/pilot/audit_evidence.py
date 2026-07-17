"""Validate one immutable-looking RepoBrief evidence bundle for audit pilots."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any

from merger.lenskit.pilot.audit_types import AuditPilotError, EvidenceSnapshot

_MANIFEST_MAX_BYTES = 4 * 1024 * 1024
_ARTIFACT_MAX_BYTES = 256 * 1024 * 1024
_JSONL_LINE_MAX_BYTES = 1024 * 1024
_CITATION_MAX_COUNT = 250_000
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_CITATION_RE = re.compile(r"^cit_[a-f0-9]{16}$")


def _open_regular(path: Path) -> tuple[int, os.stat_result]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        file_descriptor = os.open(path, flags)
        info = os.fstat(file_descriptor)
    except OSError as exc:
        raise AuditPilotError(
            f"evidence file cannot be opened safely: {path}"
        ) from exc
    if not stat.S_ISREG(info.st_mode):
        os.close(file_descriptor)
        raise AuditPilotError(
            f"evidence path is not a regular file: {path}"
        )
    return file_descriptor, info


def _read_bounded(path: Path, max_bytes: int) -> bytes:
    file_descriptor, info = _open_regular(path)
    try:
        if info.st_size > max_bytes:
            raise AuditPilotError(
                f"evidence file exceeds its size limit: {path.name}"
            )
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(
                file_descriptor,
                min(65536, remaining),
            )
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
    finally:
        os.close(file_descriptor)
    if len(data) > max_bytes:
        raise AuditPilotError(
            f"evidence file exceeds its byte limit: {path.name}"
        )
    return data


def _manifest_document(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = _read_bounded(path, _MANIFEST_MAX_BYTES)
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditPilotError(
            "bundle manifest is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(document, dict):
        raise AuditPilotError(
            "bundle manifest must be a JSON object"
        )
    if document.get("kind") != "repolens.bundle.manifest":
        raise AuditPilotError(
            "bundle manifest has an invalid kind"
        )
    if document.get("version") != "1.0":
        raise AuditPilotError(
            "bundle manifest has an unsupported version"
        )
    if not isinstance(document.get("run_id"), str):
        raise AuditPilotError(
            "bundle manifest run_id is missing"
        )
    if not isinstance(document.get("artifacts"), list):
        raise AuditPilotError(
            "bundle manifest artifacts must be an array"
        )
    return document, raw


def _require_snapshot_revision(
    document: dict[str, Any],
    repository_name: str,
    expected_revision: str,
) -> None:
    provenance = document.get("snapshot_provenance")
    records = (
        provenance.get("repositories")
        if isinstance(provenance, dict)
        else None
    )
    if not isinstance(records, list):
        raise AuditPilotError(
            "bundle snapshot provenance is unavailable"
        )
    matches = [
        record
        for record in records
        if isinstance(record, dict)
        and record.get("name") == repository_name
        and record.get("git_commit") == expected_revision
        and record.get("git_dirty") is False
        and record.get("provenance_status") == "present"
    ]
    if len(matches) != 1:
        raise AuditPilotError(
            "bundle is not uniquely bound to the reviewed clean revision"
        )


def _safe_artifact_path(root: Path, raw_path: Any) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise AuditPilotError(
            "bundle artifact path must be a non-empty string"
        )
    if "\\" in raw_path or "\x00" in raw_path:
        raise AuditPilotError(
            "bundle artifact path is not normalized POSIX"
        )
    pure = PurePosixPath(raw_path)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise AuditPilotError(
            "bundle artifact path escapes the evidence root"
        )
    candidate = root.joinpath(*pure.parts)
    try:
        candidate.resolve(strict=True).relative_to(
            root.resolve(strict=True)
        )
    except (OSError, ValueError) as exc:
        raise AuditPilotError(
            "bundle artifact path escapes the evidence root"
        ) from exc
    return candidate


def _artifact_records(
    document: dict[str, Any],
    root: Path,
) -> list[tuple[dict[str, Any], Path]]:
    records: list[tuple[dict[str, Any], Path]] = []
    seen_paths: set[Path] = set()
    for artifact in document["artifacts"]:
        if not isinstance(artifact, dict):
            raise AuditPilotError(
                "bundle artifacts must contain objects"
            )
        path = _safe_artifact_path(
            root,
            artifact.get("path"),
        )
        if path in seen_paths:
            raise AuditPilotError(
                "bundle manifest contains duplicate artifact paths"
            )
        seen_paths.add(path)
        records.append((artifact, path))
    return records


def _artifact_expectations(
    artifact: dict[str, Any],
) -> tuple[int, str]:
    expected_bytes = artifact.get("bytes")
    expected_sha256 = artifact.get("sha256")
    if isinstance(expected_bytes, bool):
        raise AuditPilotError(
            "bundle artifact byte count is invalid"
        )
    if not isinstance(expected_bytes, int) or expected_bytes < 0:
        raise AuditPilotError(
            "bundle artifact byte count is invalid"
        )
    if expected_bytes > _ARTIFACT_MAX_BYTES:
        raise AuditPilotError(
            "bundle artifact exceeds the pilot size limit"
        )
    if not isinstance(expected_sha256, str):
        raise AuditPilotError(
            "bundle artifact digest is missing"
        )
    if _SHA256_RE.fullmatch(expected_sha256) is None:
        raise AuditPilotError(
            "bundle artifact digest is invalid"
        )
    return expected_bytes, expected_sha256


def _stream_artifact_digest(
    path: Path,
) -> tuple[int, int, str]:
    file_descriptor, info = _open_regular(path)
    digest = hashlib.sha256()
    total = 0
    try:
        while True:
            chunk = os.read(file_descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > _ARTIFACT_MAX_BYTES:
                raise AuditPilotError(
                    "bundle artifact exceeds the pilot size limit"
                )
            digest.update(chunk)
    finally:
        os.close(file_descriptor)
    return total, info.st_size, digest.hexdigest()


def _hash_artifact(
    artifact: dict[str, Any],
    path: Path,
) -> None:
    expected_bytes, expected_sha256 = _artifact_expectations(
        artifact
    )
    total, file_size, actual_sha256 = _stream_artifact_digest(
        path
    )
    if total != expected_bytes or file_size != expected_bytes:
        raise AuditPilotError(
            f"bundle artifact size mismatch: {path.name}"
        )
    if actual_sha256 != expected_sha256:
        raise AuditPilotError(
            f"bundle artifact digest mismatch: {path.name}"
        )


def _citation_ids(path: Path) -> frozenset[str]:
    file_descriptor, _info = _open_regular(path)
    citations: set[str] = set()
    with os.fdopen(file_descriptor, "rb", closefd=True) as handle:
        while True:
            line = handle.readline(_JSONL_LINE_MAX_BYTES + 1)
            if not line:
                break
            _consume_citation_line(line, citations)
    if not citations:
        raise AuditPilotError(
            "citation map contains no citation ids"
        )
    return frozenset(citations)


def _consume_citation_line(
    line: bytes,
    citations: set[str],
) -> None:
    if not line.strip():
        return
    if len(line) > _JSONL_LINE_MAX_BYTES:
        raise AuditPilotError(
            "citation map line exceeds its size limit"
        )
    try:
        record = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditPilotError(
            "citation map is not valid UTF-8 JSONL"
        ) from exc
    if not isinstance(record, dict):
        raise AuditPilotError(
            "citation map records must be objects"
        )
    citation_id = record.get("citation_id")
    if not isinstance(citation_id, str):
        raise AuditPilotError(
            "citation map record is missing citation_id"
        )
    if _CITATION_RE.fullmatch(citation_id) is None:
        raise AuditPilotError(
            "citation map contains an invalid citation id"
        )
    if citation_id in citations:
        raise AuditPilotError(
            "citation map contains duplicate citation ids"
        )
    citations.add(citation_id)
    if len(citations) > _CITATION_MAX_COUNT:
        raise AuditPilotError(
            "citation map exceeds the pilot citation limit"
        )


def inspect_evidence_bundle(
    bundle_manifest: str | Path,
    *,
    repository_root: str | Path,
    expected_revision: str,
) -> EvidenceSnapshot:
    """Validate manifest identity, artifact hashes and citation registry."""

    manifest = Path(bundle_manifest).expanduser()
    if manifest.is_symlink():
        raise AuditPilotError(
            "bundle manifest must not be a symlink"
        )
    manifest = manifest.resolve(strict=True)
    if not manifest.name.endswith(".bundle.manifest.json"):
        raise AuditPilotError(
            "bundle manifest has an unexpected file name"
        )
    repository = Path(repository_root).expanduser().resolve(strict=True)
    document, raw = _manifest_document(manifest)
    _require_snapshot_revision(
        document,
        repository.name,
        expected_revision,
    )
    records = _artifact_records(document, manifest.parent)
    citation_paths: list[Path] = []
    for artifact, path in records:
        _hash_artifact(artifact, path)
        if artifact.get("role") == "citation_map_jsonl":
            citation_paths.append(path)
    if len(citation_paths) != 1:
        raise AuditPilotError(
            "bundle must contain exactly one citation map artifact"
        )
    return EvidenceSnapshot(
        root=manifest.parent,
        manifest=manifest,
        manifest_sha256=hashlib.sha256(raw).hexdigest(),
        run_id=document["run_id"],
        reviewed_revision=expected_revision,
        citation_ids=_citation_ids(citation_paths[0]),
    )


def require_same_evidence(
    expected: EvidenceSnapshot,
    current: EvidenceSnapshot,
) -> None:
    """Fail closed when an evidence probe no longer matches the spec identity."""

    expected_identity = (
        expected.root,
        expected.manifest,
        expected.manifest_sha256,
        expected.run_id,
        expected.reviewed_revision,
        expected.citation_ids,
    )
    current_identity = (
        current.root,
        current.manifest,
        current.manifest_sha256,
        current.run_id,
        current.reviewed_revision,
        current.citation_ids,
    )
    if current_identity != expected_identity:
        raise AuditPilotError(
            "evidence bundle changed during the pilot"
        )
