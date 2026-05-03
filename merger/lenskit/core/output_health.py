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

import hashlib
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .clock import now_utc
except ImportError:
    # Fallback if clock module not available
    import datetime
    def now_utc():
        return datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"

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


def _chunk_index_stats(chunk_index_path: Optional[Path]) -> Tuple[int, int, int, int]:
    """
    Validate chunk_index.jsonl and return (chunk_count, invalid_json_count, missing_id_count, empty_line_count).
    
    A valid chunk line must be:
    - non-empty
    - valid JSON
    - contains at least one of: 'id' or 'chunk_id' field
    """
    if not chunk_index_path or not chunk_index_path.exists():
        return 0, 0, 0, 0
    
    chunk_count = 0
    invalid_json_count = 0
    missing_id_count = 0
    empty_line_count = 0
    
    try:
        with chunk_index_path.open("r", encoding="utf-8") as f:
            for line in f:
                line_stripped = line.rstrip("\n\r")
                if not line_stripped:
                    empty_line_count += 1
                    continue
                
                try:
                    obj = json.loads(line_stripped)
                    if not isinstance(obj, dict):
                        invalid_json_count += 1
                        continue
                    
                    # Check for valid ID field (accept both 'id' and 'chunk_id')
                    has_id = ("id" in obj or "chunk_id" in obj)
                    if not has_id:
                        missing_id_count += 1
                        continue
                    
                    chunk_count += 1
                except json.JSONDecodeError:
                    invalid_json_count += 1
    except OSError:
        pass
    
    return chunk_count, invalid_json_count, missing_id_count, empty_line_count


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
        # No expected hash means we cannot prove hash consistency.
        return False, actual
    return actual == expected_sha256, actual


def _sqlite_checks(
    sqlite_path: Path,
    chunk_count: int,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Run all required SQLite checks and return a partial check dict.
    Returns dict with keys:
        sqlite_row_count, sqlite_row_count_matches_chunk_count,
        sqlite_fts_row_count, sqlite_fts_row_count_matches_chunk_count,
        fts_content_non_empty, fts_empty_row_count
    plus optional errors list.
    """
    result: Dict[str, Any] = {
        "sqlite_row_count": None,
        "sqlite_row_count_matches_chunk_count": None,
        "sqlite_fts_row_count": None,
        "sqlite_fts_row_count_matches_chunk_count": None,
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
            result["sqlite_fts_row_count"] = fts_count
            result["sqlite_fts_row_count_matches_chunk_count"] = fts_count == chunk_count

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
                        except json.JSONDecodeError as e:
                            return False, [f"invalid content_range_ref JSON string: {e}"]
                    if not isinstance(raw_ref, dict):
                        return False, [
                            f"content_range_ref must be an object, got {type(raw_ref).__name__}"
                        ]
                    sample_ref = raw_ref
                    break
    except OSError as e:
        return None, [f"Could not read chunk_index: {e}"]

    if sample_ref is None:
        # No range_ref present in any chunk; this is normal for inline-only bundles
        # but should be flagged as a non-blocking issue
        return None, ["no content_range_ref found; range_ref check skipped"]

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
    primary_manifest_path: Optional[Path],
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
    
    Note: primary_manifest_path is the dump_index or primary artifact manifest,
    NOT the final bundle manifest (which is written after health is computed).
    This avoids self-referential circularity: output_health.json does not verify
    its own SHA256 or its own entry in the final bundle manifest.
    """
    warnings: List[str] = []
    errors: List[str] = []
    checks: Dict[str, Any] = {}

    # ── manifest_present ────────────────────────────────────────────────────
    # In PR2, this checks the primary manifest (dump_index), not the final
    # bundle manifest (which is written after health is computed).
    # This avoids: output_health.json checking its own entry.
    manifest_present = bool(primary_manifest_path and primary_manifest_path.exists())
    checks["manifest_present"] = manifest_present
    if not manifest_present:
        errors.append("primary artifact manifest is missing")

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
    chunk_count, chunk_invalid_json_count, chunk_missing_id_count, chunk_empty_line_count = _chunk_index_stats(
        chunk_index_path
    )
    checks["chunk_count"] = chunk_count
    checks["chunk_invalid_json_line_count"] = chunk_invalid_json_count
    checks["chunk_missing_id_line_count"] = chunk_missing_id_count
    checks["chunk_empty_line_count"] = chunk_empty_line_count
    
    # Chunk validation errors are blocking
    if chunk_invalid_json_count > 0:
        errors.append(f"chunk_index.jsonl has {chunk_invalid_json_count} invalid JSON line(s)")
    if chunk_missing_id_count > 0:
        errors.append(f"chunk_index.jsonl has {chunk_missing_id_count} line(s) missing valid id/chunk_id")
    if chunk_count == 0 and chunk_index_path and chunk_index_path.exists():
        errors.append("chunk_index.jsonl has no valid chunk entries")

    # ── sqlite ──────────────────────────────────────────────────────────────
    sqlite_checks_required = sqlite_index_path is not None
    sqlite_present = bool(sqlite_index_path and sqlite_index_path.exists())
    checks["sqlite_present"] = sqlite_present
    checks["sqlite_checks_required"] = sqlite_checks_required

    if sqlite_present:
        sq, sq_errors = _sqlite_checks(sqlite_index_path, chunk_count)
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

            # FTS row count BLOCKING check
            sqlite_fts_row_count = sq.get("sqlite_fts_row_count")
            if sqlite_fts_row_count is not None:
                fts_row_match = sqlite_fts_row_count == chunk_count
                if not fts_row_match:
                    errors.append(
                        f"SQLite FTS row count ({sqlite_fts_row_count}) != chunk count ({chunk_count})"
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
        checks["sqlite_fts_row_count"] = None
        checks["sqlite_fts_row_count_matches_chunk_count"] = None
        checks["fts_content_non_empty"] = None
        checks["fts_empty_row_count"] = None
        if sqlite_checks_required:
            errors.append("sqlite_index expected but file is missing")
        else:
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
        "status": "skipped",
        "required": False,
        "reason": "stable sample query is introduced in a later work package",
    }
    if checks["sample_query_content_hit"]["status"] == "skipped":
        warnings.append("sample_query_content_hit not available in PR2; will be added later")

    checks["agent_pack_present"] = {
        "status": "skipped",
        "required": False,
        "reason": "agent_reading_pack is introduced in a later work package",
    }
    if checks["agent_pack_present"]["status"] == "skipped":
        warnings.append("agent_pack_present not available in PR2; will be added later")

    checks["redaction_status_explicit"] = True
    checks["redact_secrets_enabled"] = bool(redact_secrets)

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

    # Format created_at timestamp
    ts = now_utc()
    if isinstance(ts, str):
        created_at = ts if ts.endswith("Z") else ts + "Z"
    else:
        # Fallback if now_utc returns a datetime object
        created_at = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "kind": "lenskit.output_health",
        "version": "1.0",
        "run_id": run_id,
        "created_at": created_at,
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
    Compute and write the output health report to output_path.
    output_path must be the full destination file path, for example *.output_health.json;
    it is written exactly as provided.
    
    Note: Pass primary_manifest_path (dump_index), NOT the final bundle manifest.
    This prevents self-referential circularity during health computation.

    Returns the path to the written file.
    """
    health = compute_output_health(**kwargs)
    output_path.write_text(json.dumps(health, indent=2), encoding="utf-8")
    logger.debug("Output health written to %s (verdict=%s)", output_path, health["verdict"])
    return output_path
