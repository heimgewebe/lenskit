"""
Output Health writer for Lenskit bundles.

Computes a machine-readable diagnostic health report for an output bundle and
writes it as ``<stem>.output_health.json``.

Design contract:
- Checks primary artifacts (manifest, canonical_md, chunk_index, sqlite_index).
- NO self-hash circularity: output_health.json does NOT verify its own SHA256.
- The bundle manifest is updated by the caller AFTER this module writes the file.
- Blocking checks failing → verdict "fail".
- Only non-blocking gaps → verdict "warn".
- All blocking checks pass → verdict "pass".
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _sha256_file(path: Path) -> Optional[str]:
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _check_file_hash(path: Optional[Path], expected_sha256: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Returns (ok, actual_sha256).
    ok=False if path missing, hash computation fails, or hash mismatches.
    """
    if not path or not path.exists():
        return False, None
    actual = _sha256_file(path)
    if actual is None:
        return False, None
    if not expected_sha256:
        # No expected hash to compare against; treat as OK
        return True, actual
    return actual == expected_sha256, actual


def _sqlite_checks(
    sqlite_path: Path,
) -> Dict[str, Any]:
    """
    Run all required SQLite checks and return a partial check dict.
    Returns dict with keys:
        sqlite_row_count, sqlite_row_count_matches_chunk_count,
        fts_content_non_empty, fts_empty_row_count
    plus optional errors list.
    """
    result: Dict[str, Any] = {
        "sqlite_row_count": None,
        "sqlite_row_count_matches_chunk_count": None,
        "fts_content_non_empty": None,
        "fts_empty_row_count": None,
    }
    errors: List[str] = []
    try:
        conn = sqlite3.connect(str(sqlite_path))
        try:
            c = conn.cursor()
            row_count = c.execute("SELECT count(*) FROM chunks").fetchone()[0]
            result["sqlite_row_count"] = row_count

            fts_count = c.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]

            fts_stats = c.execute(
                "SELECT avg(length(content)), max(length(content)) FROM chunks_fts"
            ).fetchone()
            avg_len = fts_stats[0] or 0
            max_len = fts_stats[1] or 0

            empty_count = c.execute(
                "SELECT count(*) FROM chunks_fts WHERE content IS NULL OR length(content) = 0"
            ).fetchone()[0]
            result["fts_empty_row_count"] = empty_count
            result["fts_content_non_empty"] = (
                avg_len > 0 and max_len > 0 and empty_count == 0
            )
        finally:
            conn.close()
    except Exception as e:
        errors.append(f"SQLite check failed: {e}")
    return result, errors


def _range_ref_check(
    dump_index_path: Optional[Path],
    chunk_index_path: Optional[Path],
) -> Tuple[Optional[bool], List[str]]:
    """
    Find one chunk with content_range_ref and attempt resolution.
    Returns (ok, errors).
    ok=None if no chunk with content_range_ref found (treated as warning, not fail).
    ok=True if at least one resolved successfully.
    ok=False if resolution fails.
    """
    if not chunk_index_path or not chunk_index_path.exists():
        return None, ["chunk_index not available for range_ref check"]
    if not dump_index_path or not dump_index_path.exists():
        return None, ["dump_index not available for range_ref check"]

    sample_ref = None
    try:
        with chunk_index_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                raw_ref = chunk.get("content_range_ref")
                if raw_ref is not None:
                    if isinstance(raw_ref, str):
                        try:
                            raw_ref = json.loads(raw_ref)
                        except json.JSONDecodeError:
                            continue
                    if isinstance(raw_ref, dict):
                        sample_ref = raw_ref
                        break
    except OSError as e:
        return None, [f"Could not read chunk_index: {e}"]

    if sample_ref is None:
        return None, []

    try:
        from .range_resolver import resolve_range_ref
        resolve_range_ref(dump_index_path, sample_ref)
        return True, []
    except Exception as e:
        return False, [f"range_ref resolution failed: {e}"]


def compute_output_health(
    *,
    run_id: str,
    stem: str,
    bundle_manifest_path: Optional[Path],
    canonical_md_path: Optional[Path],
    chunk_index_path: Optional[Path],
    dump_index_path: Optional[Path],
    sqlite_index_path: Optional[Path],
    redact_secrets: bool,
    # Expected hashes from dump_index / bundle manifest for cross-checking
    expected_canonical_md_sha256: Optional[str] = None,
    expected_chunk_index_sha256: Optional[str] = None,
    # Optional diagnostics
    retrieval_eval_path: Optional[Path] = None,
    retrieval_eval_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute the output health report.  Does NOT write to disk.
    Returns a dict conforming to output-health.v1.schema.json.
    """
    warnings: List[str] = []
    errors: List[str] = []
    checks: Dict[str, Any] = {}

    # ── manifest_present ────────────────────────────────────────────────────
    manifest_present = bool(bundle_manifest_path and bundle_manifest_path.exists())
    checks["manifest_present"] = manifest_present
    if not manifest_present:
        errors.append("bundle manifest file is missing")

    # ── canonical_md_hash_ok ────────────────────────────────────────────────
    canonical_ok, _ = _check_file_hash(canonical_md_path, expected_canonical_md_sha256)
    checks["canonical_md_hash_ok"] = canonical_ok
    if not canonical_ok:
        errors.append(
            "canonical_md hash check failed (file missing or hash mismatch)"
        )

    # ── chunk_index_hash_ok ─────────────────────────────────────────────────
    chunk_ok, _ = _check_file_hash(chunk_index_path, expected_chunk_index_sha256)
    checks["chunk_index_hash_ok"] = chunk_ok
    if not chunk_ok:
        errors.append(
            "chunk_index hash check failed (file missing or hash mismatch)"
        )

    # ── chunk_count ─────────────────────────────────────────────────────────
    chunk_count = 0
    if chunk_index_path and chunk_index_path.exists():
        try:
            with chunk_index_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            json.loads(line)
                            chunk_count += 1
                        except json.JSONDecodeError:
                            pass
        except OSError:
            pass
    checks["chunk_count"] = chunk_count
    if chunk_count == 0:
        errors.append("chunk_count is 0; index is empty")

    # ── sqlite ──────────────────────────────────────────────────────────────
    sqlite_present = bool(sqlite_index_path and sqlite_index_path.exists())
    checks["sqlite_present"] = sqlite_present
    checks["sqlite_checks_required"] = sqlite_present

    if sqlite_present:
        sq, sq_errors = _sqlite_checks(sqlite_index_path)
        checks.update(sq)
        if sq_errors:
            errors.extend(sq_errors)
        else:
            # Row count match check
            sqlite_row_count = sq.get("sqlite_row_count")
            if sqlite_row_count is not None:
                row_match = sqlite_row_count == chunk_count
                checks["sqlite_row_count_matches_chunk_count"] = row_match
                if not row_match:
                    errors.append(
                        f"SQLite row count ({sqlite_row_count}) != chunk count ({chunk_count})"
                    )
            # FTS content check
            fts_ok = sq.get("fts_content_non_empty")
            if fts_ok is False:
                errors.append(
                    "SQLite FTS content is empty (fts_content_non_empty=false)"
                )
    else:
        checks["sqlite_row_count"] = None
        checks["sqlite_row_count_matches_chunk_count"] = None
        checks["fts_content_non_empty"] = None
        checks["fts_empty_row_count"] = None
        warnings.append(
            "sqlite_index not present in bundle; SQLite checks skipped"
        )

    # ── range_ref_resolution_ok ─────────────────────────────────────────────
    rr_ok, rr_msgs = _range_ref_check(dump_index_path, chunk_index_path)
    checks["range_ref_resolution_ok"] = rr_ok
    if rr_ok is False:
        errors.extend(rr_msgs)
    elif rr_ok is None:
        warnings.extend(rr_msgs)

    # ── non-blocking optional checks ────────────────────────────────────────
    checks["sample_query_content_hit"] = {
        "status": "warning",
        "required": False,
        "reason": "stable sample query is introduced in a later work package",
    }

    checks["agent_pack_present"] = {
        "status": "warning",
        "required": False,
        "reason": "agent_reading_pack is introduced in a later work package",
    }

    checks["redaction_status_explicit"] = True

    # ── diagnostic_artifacts ────────────────────────────────────────────────
    diagnostic_artifacts: Dict[str, Any] = {}
    if retrieval_eval_path and retrieval_eval_path.exists():
        actual_sha = _sha256_file(retrieval_eval_path)
        ok = True
        if retrieval_eval_sha256 and actual_sha != retrieval_eval_sha256:
            ok = False
            warnings.append("retrieval_eval_json hash mismatch (not blocking)")
        diagnostic_artifacts["retrieval_eval_json"] = {
            "path": retrieval_eval_path.name,
            "hash_ok": ok,
            "sha256": actual_sha,
        }

    # ── verdict ─────────────────────────────────────────────────────────────
    if errors:
        verdict = "fail"
    elif warnings:
        verdict = "warn"
    else:
        verdict = "pass"

    return {
        "kind": "lenskit.output_health",
        "version": "1.0",
        "run_id": run_id,
        "created_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "stem": stem,
        "checks": checks,
        "diagnostic_artifacts": diagnostic_artifacts,
        "warnings": warnings,
        "errors": errors,
        "verdict": verdict,
    }


def write_output_health(
    output_path: Path,
    **kwargs: Any,
) -> Path:
    """
    Compute and write ``<output_path>.output_health.json``.
    ``output_path`` should be the bundle stem path (without extension);
    the actual file is written alongside the other bundle artifacts.

    Returns the path to the written file.
    """
    health = compute_output_health(**kwargs)
    output_path.write_text(json.dumps(health, indent=2), encoding="utf-8")
    logger.debug("Output health written to %s (verdict=%s)", output_path, health["verdict"])
    return output_path
