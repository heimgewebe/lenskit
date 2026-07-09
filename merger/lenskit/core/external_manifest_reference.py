"""External manifest reference surface for RepoBrief/Lenskit consumers."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

SUPPORTED_FAMILIES = {"repobrief", "lenskit"}
BUNDLE_KIND = "repolens.bundle.manifest"
DOES_NOT_ESTABLISH = (
    "dump_freshness_truth",
    "claim_truth",
    "runtime_correctness",
    "semantic_correctness",
    "task_approval",
    "dump_generation_permission",
    "repo_understood",
    "merge_readiness",
)


class ExternalManifestReferenceError(ValueError):
    """Raised when an external manifest reference cannot be built."""


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ExternalManifestReferenceError(f"bundle manifest does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ExternalManifestReferenceError(f"bundle manifest is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ExternalManifestReferenceError("bundle manifest must be a JSON object")
    return data


def _relative_path(target: Path, base_dir: Path) -> str:
    return Path(os.path.relpath(target.resolve(), base_dir.resolve())).as_posix()


def _registry_segment(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value or "/" in value or "\\" in value:
        raise ExternalManifestReferenceError(f"{label} must be a non-empty registry segment")
    if value in {".", ".."}:
        raise ExternalManifestReferenceError(f"{label} must not be a traversal segment")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_rows(bundle_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = bundle_manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ExternalManifestReferenceError("bundle manifest artifacts must be a list")
    rows: list[dict[str, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        role = artifact.get("role")
        path = artifact.get("path")
        sha256 = artifact.get("sha256")
        if not isinstance(role, str) or not isinstance(path, str):
            continue
        row: dict[str, Any] = {
            "role": role,
            "path": path,
            "sha256": sha256 if isinstance(sha256, str) else None,
        }
        if isinstance(artifact.get("bytes"), int):
            row["bytes"] = artifact["bytes"]
        if isinstance(artifact.get("content_type"), str):
            row["contentType"] = artifact["content_type"]
        rows.append(row)
    return rows


def _linked_sidecar_rows(bundle_manifest_path: Path, bundle_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    links = bundle_manifest.get("links")
    if not isinstance(links, dict):
        return []
    linked_roles = {
        "post_emit_health_path": "post_emit_health",
        "bundle_surface_validation_path": "bundle_surface_validation",
        "surface_validation_path": "bundle_surface_validation",
    }
    rows: list[dict[str, Any]] = []
    bundle_dir = bundle_manifest_path.parent.resolve()
    seen_paths: set[str] = set()
    for link_key, role in linked_roles.items():
        raw_path = links.get(link_key)
        if not isinstance(raw_path, str) or not raw_path:
            continue
        linked_path = (bundle_dir / raw_path).resolve()
        try:
            linked_path.relative_to(bundle_dir)
        except ValueError as exc:
            raise ExternalManifestReferenceError(
                f"bundle manifest link {link_key} must stay inside the bundle directory"
            ) from exc
        if not linked_path.is_file():
            raise ExternalManifestReferenceError(
                f"bundle manifest link {link_key} does not exist: {raw_path}"
            )
        path_value = Path(raw_path).as_posix()
        if path_value in seen_paths:
            continue
        seen_paths.add(path_value)
        rows.append({
            "role": role,
            "path": path_value,
            "sha256": _sha256_file(linked_path),
            "bytes": linked_path.stat().st_size,
            "contentType": "application/json",
        })
    return rows


def _combined_artifact_rows(bundle_manifest_path: Path, bundle_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in _artifact_rows(bundle_manifest) + _linked_sidecar_rows(bundle_manifest_path, bundle_manifest):
        rows_by_key[(row["role"], row["path"])] = row
    return sorted(rows_by_key.values(), key=lambda item: (item["role"], item["path"]))


def _require_inside_publication_root(bundle_manifest_path: Path, publication_root: Path | None) -> None:
    if publication_root is None:
        return
    root = publication_root.expanduser().resolve()
    try:
        bundle_manifest_path.relative_to(root)
    except ValueError as exc:
        raise ExternalManifestReferenceError(
            "bundle manifest must be inside publication_root for portable external publication"
        ) from exc


def build_external_manifest_reference(
    bundle_manifest_path: str | Path,
    *,
    repository: str,
    ref: str,
    artifact_family: str = "repobrief",
    output_path: str | Path | None = None,
    publication_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build a bounded external manifest reference from an existing bundle manifest."""
    family = artifact_family.strip().lower() if isinstance(artifact_family, str) else ""
    if family not in SUPPORTED_FAMILIES:
        raise ExternalManifestReferenceError("artifact_family must be repobrief or lenskit")
    repository = _registry_segment(repository, "repository")
    ref = _registry_segment(ref, "ref")
    manifest_path = Path(bundle_manifest_path).expanduser().resolve()
    _require_inside_publication_root(
        manifest_path,
        Path(publication_root) if publication_root is not None else None,
    )
    bundle = _read_json_object(manifest_path)
    if bundle.get("kind") != BUNDLE_KIND:
        raise ExternalManifestReferenceError("bundle manifest kind must be repolens.bundle.manifest")
    created_at = bundle.get("created_at")
    if not isinstance(created_at, str) or not created_at:
        raise ExternalManifestReferenceError("bundle manifest created_at must be present")
    output_base = Path(output_path).expanduser().resolve().parent if output_path is not None else manifest_path.parent
    snapshot_provenance = bundle.get("snapshot_provenance")
    return {
        "kind": f"{family}_bundle_manifest",
        "version": "1",
        "artifactFamily": family,
        "repository": repository,
        "ref": ref,
        "generatedAt": created_at,
        "freshnessBasis": "bundle_manifest.created_at",
        "bundleManifest": {
            "kind": BUNDLE_KIND,
            "path": _relative_path(manifest_path, output_base),
            "runId": bundle.get("run_id"),
            "createdAt": created_at,
        },
        "snapshotProvenance": snapshot_provenance if isinstance(snapshot_provenance, dict) else None,
        "artifacts": _combined_artifact_rows(manifest_path, bundle),
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }


def publication_manifest_path(
    publication_root: str | Path,
    *,
    repository: str,
    ref: str,
    artifact_family: str,
) -> Path:
    """Return the stable external manifest publication path for a registry segment."""
    family = artifact_family.strip().lower() if isinstance(artifact_family, str) else ""
    if family not in SUPPORTED_FAMILIES:
        raise ExternalManifestReferenceError("artifact_family must be repobrief or lenskit")
    repository = _registry_segment(repository, "repository")
    ref = _registry_segment(ref, "ref")
    return Path(publication_root).expanduser().resolve() / "external" / family / repository / ref / "manifest.json"


def publish_external_manifest_references(
    bundle_manifest_path: str | Path,
    publication_root: str | Path,
    *,
    repository: str,
    ref: str,
    artifact_families: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Publish one or more external manifest references under a stable root."""
    families = list(dict.fromkeys(artifact_families)) if artifact_families is not None else sorted(SUPPORTED_FAMILIES)
    if not families:
        raise ExternalManifestReferenceError("at least one artifact family is required")
    published = []
    for family in families:
        out = publication_manifest_path(
            publication_root,
            repository=repository,
            ref=ref,
            artifact_family=family,
        )
        manifest = write_external_manifest_reference(
            bundle_manifest_path,
            out,
            repository=repository,
            ref=ref,
            artifact_family=family,
            publication_root=publication_root,
        )
        published.append({
            "artifactFamily": manifest["artifactFamily"],
            "kind": manifest["kind"],
            "path": str(out),
            "generatedAt": manifest["generatedAt"],
            "relativePublicationPath": Path(os.path.relpath(out, Path(publication_root).expanduser().resolve())).as_posix(),
        })
    return {
        "kind": "repobrief.external_manifest_publication",
        "version": "1",
        "repository": _registry_segment(repository, "repository"),
        "ref": _registry_segment(ref, "ref"),
        "publicationRoot": str(Path(publication_root).expanduser().resolve()),
        "bundleManifest": str(Path(bundle_manifest_path).expanduser().resolve()),
        "published": published,
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }


def write_external_manifest_reference(
    bundle_manifest_path: str | Path,
    output_path: str | Path,
    *,
    repository: str,
    ref: str,
    artifact_family: str = "repobrief",
    publication_root: str | Path | None = None,
) -> dict[str, Any]:
    """Write an external manifest reference atomically and return it."""
    out = Path(output_path).expanduser().resolve()
    data = build_external_manifest_reference(
        bundle_manifest_path,
        repository=repository,
        ref=ref,
        artifact_family=artifact_family,
        output_path=out,
        publication_root=publication_root,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=str(out.parent),
            prefix=f".{out.name}.",
            suffix=".tmp",
        ) as tmp_file:
            json.dump(data, tmp_file, indent=2, sort_keys=True)
            tmp_file.write("\n")
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
            tmp_path = Path(tmp_file.name)
        os.replace(tmp_path, out)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()
    return data
