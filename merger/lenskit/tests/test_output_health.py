"""
Tests for merger.lenskit.core.output_health (PR 2 — Output Health Artifact).

Test matrix:
  1. verdict=pass: all primary artifacts present + hash ok + non-empty sqlite
  2. verdict=warn: sqlite absent (only warning)
  3. verdict=fail: canonical_md missing
  4. verdict=fail: chunk_count == 0
  5. verdict=fail: sqlite row count mismatch vs chunk count
  6. verdict=fail: fts_content_non_empty=false (all empty rows)
  7. verdict=fail: range_ref resolution fails (broken ref JSON)
  8. range_ref skip: no chunk has content_range_ref → ok=None, only warning
  9. schema conformance: output JSON validates against output-health.v1.schema.json
"""

import hashlib
import json
import sqlite3
from pathlib import Path

import jsonschema
import pytest

from merger.lenskit.core.output_health import compute_output_health, write_output_health


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

_SCHEMA_PATH = (
    Path(__file__).parent.parent / "contracts" / "output-health.v1.schema.json"
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_file(path: Path, data: bytes) -> str:
    path.write_bytes(data)
    return _sha256_bytes(data)


def _make_chunk_jsonl(tmp_path: Path, chunks: list[dict]) -> tuple[Path, str]:
    """Write a chunk_index.jsonl and return (path, sha256)."""
    content = "\n".join(json.dumps(c) for c in chunks) + "\n"
    data = content.encode("utf-8")
    p = tmp_path / "test.chunk_index.jsonl"
    sha = _write_file(p, data)
    return p, sha


def _make_canonical_md(tmp_path: Path) -> tuple[Path, str]:
    data = b"# Test merge\n\nSome content.\n"
    p = tmp_path / "test.md"
    sha = _write_file(p, data)
    return p, sha


def _make_dump_index(tmp_path: Path) -> Path:
    """Write a minimal dump_index.json (no range refs needed for basic tests)."""
    p = tmp_path / "test.dump_index.json"
    p.write_text(json.dumps({"version": "1.0", "chunks": []}), encoding="utf-8")
    return p


def _make_sqlite(tmp_path: Path, chunks: list[dict]) -> Path:
    """Build a minimal SQLite with chunks + chunks_fts tables."""
    db_path = tmp_path / "test.index.sqlite"
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("CREATE TABLE chunks (id TEXT PRIMARY KEY, content TEXT, path TEXT)")
    c.execute(
        "CREATE VIRTUAL TABLE chunks_fts USING fts5(chunk_id, content, path_tokens)"
    )
    for chunk in chunks:
        cid = chunk.get("id", "cid-1")
        content = chunk.get("content", "hello world")
        path = chunk.get("path", "test/file.md")
        c.execute("INSERT INTO chunks VALUES (?, ?, ?)", (cid, content, path))
        c.execute("INSERT INTO chunks_fts VALUES (?, ?, ?)", (cid, content, path))
    conn.commit()
    conn.close()
    return db_path


def _make_bundle_manifest(tmp_path: Path) -> Path:
    p = tmp_path / "test.bundle.manifest.json"
    p.write_text(
        json.dumps({"kind": "repolens.bundle.manifest", "version": "1.0"}),
        encoding="utf-8",
    )
    return p


def _base_kwargs(
    *,
    tmp_path: Path,
    chunks: list[dict] | None = None,
    with_sqlite: bool = True,
    with_manifest: bool = True,
) -> dict:
    if chunks is None:
        chunks = [{"id": "c1", "content": "hello world", "path": "test/a.md"}]

    canonical_md_path, canonical_md_sha = _make_canonical_md(tmp_path)
    chunk_index_path, chunk_sha = _make_chunk_jsonl(tmp_path, chunks)
    dump_index_path = _make_dump_index(tmp_path)
    bundle_manifest_path = _make_bundle_manifest(tmp_path) if with_manifest else None
    sqlite_index_path = _make_sqlite(tmp_path, chunks) if with_sqlite else None

    return dict(
        run_id="run-test-1",
        stem="test",
        bundle_manifest_path=bundle_manifest_path,
        canonical_md_path=canonical_md_path,
        chunk_index_path=chunk_index_path,
        dump_index_path=dump_index_path,
        sqlite_index_path=sqlite_index_path,
        redact_secrets=False,
        expected_canonical_md_sha256=canonical_md_sha,
        expected_chunk_index_sha256=chunk_sha,
    )


# ────────────────────────────────────────────────────────────────────────────
# Test 1 — verdict=pass: all primary artifacts present, hashes ok, sqlite ok
# ────────────────────────────────────────────────────────────────────────────

def test_verdict_pass_all_present(tmp_path):
    kwargs = _base_kwargs(tmp_path=tmp_path)
    result = compute_output_health(**kwargs)

    assert result["kind"] == "lenskit.output_health"
    assert result["version"] == "1.0"
    assert result["verdict"] == "pass"
    assert result["errors"] == []
    assert result["checks"]["manifest_present"] is True
    assert result["checks"]["canonical_md_hash_ok"] is True
    assert result["checks"]["chunk_index_hash_ok"] is True
    assert result["checks"]["chunk_count"] == 1
    assert result["checks"]["sqlite_present"] is True
    assert result["checks"]["sqlite_row_count"] == 1
    assert result["checks"]["sqlite_row_count_matches_chunk_count"] is True
    assert result["checks"]["fts_content_non_empty"] is True
    assert result["checks"]["fts_empty_row_count"] == 0
    assert result["checks"]["redaction_status_explicit"] is True


# ────────────────────────────────────────────────────────────────────────────
# Test 2 — verdict=warn: sqlite absent → only warning, no error
# ────────────────────────────────────────────────────────────────────────────

def test_verdict_warn_sqlite_absent(tmp_path):
    kwargs = _base_kwargs(tmp_path=tmp_path, with_sqlite=False)
    result = compute_output_health(**kwargs)

    assert result["verdict"] == "warn"
    assert result["errors"] == []
    assert any("sqlite" in w.lower() for w in result["warnings"])
    assert result["checks"]["sqlite_present"] is False
    assert result["checks"]["sqlite_checks_required"] is False
    assert result["checks"]["sqlite_row_count"] is None
    assert result["checks"]["fts_content_non_empty"] is None


# ────────────────────────────────────────────────────────────────────────────
# Test 3 — verdict=fail: canonical_md missing
# ────────────────────────────────────────────────────────────────────────────

def test_verdict_fail_canonical_md_missing(tmp_path):
    kwargs = _base_kwargs(tmp_path=tmp_path)
    kwargs["canonical_md_path"] = tmp_path / "nonexistent.md"
    result = compute_output_health(**kwargs)

    assert result["verdict"] == "fail"
    assert result["checks"]["canonical_md_hash_ok"] is False
    assert any("canonical_md" in e for e in result["errors"])


# ────────────────────────────────────────────────────────────────────────────
# Test 4 — verdict=fail: chunk_count == 0 (empty chunk_index)
# ────────────────────────────────────────────────────────────────────────────

def test_verdict_fail_empty_chunk_index(tmp_path):
    kwargs = _base_kwargs(tmp_path=tmp_path, chunks=[])
    # chunk_index_hash_ok will still be True (file exists), but chunk_count=0 fails
    result = compute_output_health(**kwargs)

    assert result["verdict"] == "fail"
    assert result["checks"]["chunk_count"] == 0
    assert any("chunk_count" in e or "empty" in e.lower() for e in result["errors"])


# ────────────────────────────────────────────────────────────────────────────
# Test 5 — verdict=fail: sqlite row count mismatch vs chunk count
# ────────────────────────────────────────────────────────────────────────────

def test_verdict_fail_sqlite_row_count_mismatch(tmp_path):
    # Write chunk_index with 3 chunks but sqlite with only 1
    chunks_full = [
        {"id": "c1", "content": "aaa", "path": "a.md"},
        {"id": "c2", "content": "bbb", "path": "b.md"},
        {"id": "c3", "content": "ccc", "path": "c.md"},
    ]
    chunks_short = [{"id": "c1", "content": "aaa", "path": "a.md"}]

    canonical_md_path, canonical_md_sha = _make_canonical_md(tmp_path)
    chunk_index_path, chunk_sha = _make_chunk_jsonl(tmp_path, chunks_full)
    dump_index_path = _make_dump_index(tmp_path)
    # SQLite has only 1 row but chunk_index has 3
    sqlite_index_path = _make_sqlite(tmp_path, chunks_short)
    bundle_manifest_path = _make_bundle_manifest(tmp_path)

    result = compute_output_health(
        run_id="run-test-mismatch",
        stem="test",
        bundle_manifest_path=bundle_manifest_path,
        canonical_md_path=canonical_md_path,
        chunk_index_path=chunk_index_path,
        dump_index_path=dump_index_path,
        sqlite_index_path=sqlite_index_path,
        redact_secrets=False,
        expected_canonical_md_sha256=canonical_md_sha,
        expected_chunk_index_sha256=chunk_sha,
    )

    assert result["verdict"] == "fail"
    assert result["checks"]["sqlite_row_count_matches_chunk_count"] is False
    assert any("row count" in e.lower() or "chunk count" in e.lower() for e in result["errors"])


# ────────────────────────────────────────────────────────────────────────────
# Test 6 — verdict=fail: fts_content_non_empty=false (empty content rows)
# ────────────────────────────────────────────────────────────────────────────

def test_verdict_fail_fts_content_empty(tmp_path):
    # Build sqlite with empty content
    chunks = [{"id": "c1", "content": "text", "path": "a.md"}]
    canonical_md_path, canonical_md_sha = _make_canonical_md(tmp_path)
    chunk_index_path, chunk_sha = _make_chunk_jsonl(tmp_path, chunks)
    dump_index_path = _make_dump_index(tmp_path)
    bundle_manifest_path = _make_bundle_manifest(tmp_path)

    # Build SQLite with empty FTS content
    db_path = tmp_path / "empty_fts.index.sqlite"
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("CREATE TABLE chunks (id TEXT PRIMARY KEY, content TEXT, path TEXT)")
    c.execute(
        "CREATE VIRTUAL TABLE chunks_fts USING fts5(chunk_id, content, path_tokens)"
    )
    c.execute("INSERT INTO chunks VALUES (?, ?, ?)", ("c1", "text", "a.md"))
    c.execute("INSERT INTO chunks_fts VALUES (?, ?, ?)", ("c1", "", "a.md"))
    conn.commit()
    conn.close()

    result = compute_output_health(
        run_id="run-empty-fts",
        stem="test",
        bundle_manifest_path=bundle_manifest_path,
        canonical_md_path=canonical_md_path,
        chunk_index_path=chunk_index_path,
        dump_index_path=dump_index_path,
        sqlite_index_path=db_path,
        redact_secrets=False,
        expected_canonical_md_sha256=canonical_md_sha,
        expected_chunk_index_sha256=chunk_sha,
    )

    assert result["verdict"] == "fail"
    assert result["checks"]["fts_content_non_empty"] is False
    assert any("fts" in e.lower() or "empty" in e.lower() for e in result["errors"])


# ────────────────────────────────────────────────────────────────────────────
# Test 7 — verdict=fail: range_ref resolution fails (broken ref JSON in chunk)
# ────────────────────────────────────────────────────────────────────────────

def test_verdict_fail_range_ref_resolution_broken(tmp_path):
    # A chunk with a content_range_ref dict that points to a non-existent artifact
    chunks = [
        {
            "id": "c1",
            "content": "",
            "path": "a.md",
            "content_range_ref": {
                "artifact": "missing_artifact.json",
                "path": "a.md",
                "start": 0,
                "end": 10,
                "sha256": "0" * 64,
            },
        }
    ]
    canonical_md_path, canonical_md_sha = _make_canonical_md(tmp_path)
    chunk_index_path, chunk_sha = _make_chunk_jsonl(tmp_path, chunks)
    dump_index_path = _make_dump_index(tmp_path)
    bundle_manifest_path = _make_bundle_manifest(tmp_path)

    result = compute_output_health(
        run_id="run-broken-ref",
        stem="test",
        bundle_manifest_path=bundle_manifest_path,
        canonical_md_path=canonical_md_path,
        chunk_index_path=chunk_index_path,
        dump_index_path=dump_index_path,
        sqlite_index_path=None,
        redact_secrets=False,
        expected_canonical_md_sha256=canonical_md_sha,
        expected_chunk_index_sha256=chunk_sha,
    )

    # range_ref resolution failure is a blocking error
    assert result["checks"]["range_ref_resolution_ok"] is False
    assert any("range_ref" in e.lower() or "resolution" in e.lower() for e in result["errors"])


# ────────────────────────────────────────────────────────────────────────────
# Test 8 — range_ref skip: no chunk has content_range_ref → ok=None, warning only
# ────────────────────────────────────────────────────────────────────────────

def test_range_ref_skipped_when_no_ref_present(tmp_path):
    chunks = [{"id": "c1", "content": "plain content, no ref", "path": "a.md"}]
    kwargs = _base_kwargs(tmp_path=tmp_path, chunks=chunks, with_sqlite=False)
    result = compute_output_health(**kwargs)

    assert result["checks"]["range_ref_resolution_ok"] is None
    # ok=None means silently skipped — no warning, no fatal error
    assert not any("range_ref" in e.lower() for e in result["errors"])


# ────────────────────────────────────────────────────────────────────────────
# Test 9 — schema conformance: output JSON validates against output-health.v1
# ────────────────────────────────────────────────────────────────────────────

def test_schema_conformance(tmp_path):
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    kwargs = _base_kwargs(tmp_path=tmp_path)
    result = compute_output_health(**kwargs)
    # Should not raise
    jsonschema.validate(instance=result, schema=schema)


# ────────────────────────────────────────────────────────────────────────────
# Test 10 — write_output_health writes valid JSON to disk
# ────────────────────────────────────────────────────────────────────────────

def test_write_output_health_writes_file(tmp_path):
    kwargs = _base_kwargs(tmp_path=tmp_path, with_sqlite=False)
    out_path = tmp_path / "test.output_health.json"
    returned = write_output_health(out_path, **kwargs)

    assert returned == out_path
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["kind"] == "lenskit.output_health"
    assert data["verdict"] in {"pass", "warn", "fail"}
