import hashlib
import json
import sqlite3
from pathlib import Path

from merger.lenskit.core.parity_gates import evaluate_parity_gates
from merger.lenskit.core.parity_state import build_parity_state


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _make_sqlite(path: Path, rows: list[tuple[str, str]]) -> None:
    conn = sqlite3.connect(str(path))
    try:
        c = conn.cursor()
        c.execute("CREATE TABLE chunks (chunk_id TEXT PRIMARY KEY, content TEXT)")
        c.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(chunk_id UNINDEXED, content, path_tokens)")
        for chunk_id, content in rows:
            c.execute("INSERT INTO chunks (chunk_id, content) VALUES (?, ?)", (chunk_id, content))
            c.execute(
                "INSERT INTO chunks_fts (chunk_id, content, path_tokens) VALUES (?, ?, ?)",
                (chunk_id, content, "x"),
            )
        conn.commit()
    finally:
        conn.close()


def _make_bundle(
    root: Path,
    *,
    retrieval_manifested: bool,
    citation_manifested: bool,
    citation_valid: bool,
    sqlite_present: bool,
    fts_non_empty: bool,
    health_warning: bool,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)

    canonical_md = b"# demo\n\nhello\n"
    canonical_md_path = root / "merge.md"
    canonical_md_path.write_bytes(canonical_md)

    chunk_rows = [
        {
            "chunk_id": "c1",
            "path": "src/a.py",
            "sha256": _sha256_bytes(b"print('a')"),
            "content": "print('a')",
        },
        {
            "chunk_id": "c2",
            "path": "src/b.py",
            "sha256": _sha256_bytes(b"print('b')"),
            "content": "print('b')",
        },
    ]

    chunk_index_path = root / "chunk_index.jsonl"
    chunk_payload = "\n".join(json.dumps({"chunk_id": r["chunk_id"]}) for r in chunk_rows) + "\n"
    chunk_index_path.write_text(chunk_payload, encoding="utf-8")

    sidecar = {
        "meta": {"contract": "repolens-agent", "contract_version": "v2"},
        "coverage": {
            "included_text_files": 2,
            "total_text_files": 2,
            "coverage_pct": 100.0,
        },
        "files": [
            {"path": r["path"], "included": True, "sha256": r["sha256"]}
            for r in chunk_rows
        ],
    }
    sidecar_path = root / "index.sidecar.json"
    _write_json(sidecar_path, sidecar)

    dump_index = {
        "contract": "dump-index",
        "contract_version": "v1",
        "artifacts": {
            "canonical_md": {"path": "merge.md", "role": "canonical_md"},
            "chunk_index_jsonl": {"path": "chunk_index.jsonl", "role": "chunk_index_jsonl"},
        },
    }
    dump_index_path = root / "bundle.dump_index.json"
    _write_json(dump_index_path, dump_index)

    sqlite_path = root / "bundle.index.sqlite"
    if sqlite_present:
        rows = [(r["chunk_id"], r["content"] if fts_non_empty else "") for r in chunk_rows]
        _make_sqlite(sqlite_path, rows)

    retrieval_path = root / "bundle.retrieval_eval.json"
    if retrieval_manifested:
        _write_json(retrieval_path, {"ok": True})

    citation_path = root / "bundle.citation_map.jsonl"
    if citation_manifested:
        if citation_valid:
            citation_path.write_text(json.dumps({"citation_id": "x"}) + "\n", encoding="utf-8")
        else:
            citation_path.write_text("{bad-json\n", encoding="utf-8")

    output_health = {
        "kind": "lenskit.output_health",
        "version": "1.0",
        "run_id": "r1",
        "created_at": "2026-05-16T00:00:00Z",
        "stem": root.name,
        "checks": {
            "range_ref_resolution_ok": True,
            "sqlite_checks_required": sqlite_present,
            "fts_content_non_empty": fts_non_empty,
        },
        "warnings": ["warn"] if health_warning else [],
        "errors": [],
        "verdict": "warn" if health_warning else "pass",
    }
    output_health_path = root / "bundle.output_health.json"
    _write_json(output_health_path, output_health)

    artifacts: list[dict] = []
    for role, path, ctype in [
        ("canonical_md", canonical_md_path, "text/markdown"),
        ("chunk_index_jsonl", chunk_index_path, "application/x-ndjson"),
        ("index_sidecar_json", sidecar_path, "application/json"),
        ("dump_index_json", dump_index_path, "application/json"),
        ("output_health", output_health_path, "application/json"),
    ]:
        data = path.read_bytes()
        artifacts.append(
            {
                "role": role,
                "path": path.name,
                "content_type": ctype,
                "bytes": len(data),
                "sha256": _sha256_bytes(data),
            }
        )

    if sqlite_present:
        data = sqlite_path.read_bytes()
        artifacts.append(
            {
                "role": "sqlite_index",
                "path": sqlite_path.name,
                "content_type": "application/octet-stream",
                "bytes": len(data),
                "sha256": _sha256_bytes(data),
            }
        )
    if retrieval_manifested:
        data = retrieval_path.read_bytes()
        artifacts.append(
            {
                "role": "retrieval_eval_json",
                "path": retrieval_path.name,
                "content_type": "application/json",
                "bytes": len(data),
                "sha256": _sha256_bytes(data),
            }
        )
    if citation_manifested:
        data = citation_path.read_bytes()
        artifacts.append(
            {
                "role": "citation_map_jsonl",
                "path": citation_path.name,
                "content_type": "application/x-ndjson",
                "bytes": len(data),
                "sha256": _sha256_bytes(data),
            }
        )

    manifest = {
        "kind": "repolens.bundle.manifest",
        "version": "1.0",
        "run_id": "run-1",
        "created_at": "2026-05-16T00:00:00Z",
        "generator": {"name": "test", "version": "0.1", "config_sha256": "a" * 64},
        "artifacts": artifacts,
        "links": {},
        "capabilities": {"fts5_bm25": sqlite_present, "redaction": False},
    }
    manifest_path = root / "bundle.bundle.manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def test_identical_minimal_bundles_are_green(tmp_path):
    left = _make_bundle(
        tmp_path / "left",
        retrieval_manifested=True,
        citation_manifested=True,
        citation_valid=True,
        sqlite_present=True,
        fts_non_empty=True,
        health_warning=False,
    )
    right = _make_bundle(
        tmp_path / "right",
        retrieval_manifested=True,
        citation_manifested=True,
        citation_valid=True,
        sqlite_present=True,
        fts_non_empty=True,
        health_warning=False,
    )

    built = build_parity_state(left, right)
    gates = evaluate_parity_gates(built.state)

    assert gates.content_parity_pass is True
    assert gates.diagnostic_parity_pass is True


def test_missing_retrieval_eval_when_expected_fails_diagnostic(tmp_path):
    left = _make_bundle(
        tmp_path / "left",
        retrieval_manifested=True,
        citation_manifested=False,
        citation_valid=False,
        sqlite_present=True,
        fts_non_empty=True,
        health_warning=False,
    )
    right = _make_bundle(
        tmp_path / "right",
        retrieval_manifested=False,
        citation_manifested=False,
        citation_valid=False,
        sqlite_present=True,
        fts_non_empty=True,
        health_warning=False,
    )

    built = build_parity_state(left, right)
    gates = evaluate_parity_gates(built.state)

    assert built.state["retrieval_eval_json_expected"] is True
    assert built.state["retrieval_eval_json_manifested"] is False
    assert gates.diagnostic_parity_pass is False
    assert any("retrieval_eval_json_manifested" in r for r in gates.diagnostic_reasons)


def test_invalid_citation_map_when_expected_fails_diagnostic(tmp_path):
    left = _make_bundle(
        tmp_path / "left",
        retrieval_manifested=False,
        citation_manifested=True,
        citation_valid=True,
        sqlite_present=True,
        fts_non_empty=True,
        health_warning=False,
    )
    right = _make_bundle(
        tmp_path / "right",
        retrieval_manifested=False,
        citation_manifested=True,
        citation_valid=False,
        sqlite_present=True,
        fts_non_empty=True,
        health_warning=False,
    )

    built = build_parity_state(left, right)
    gates = evaluate_parity_gates(built.state)

    assert built.state["citation_map_jsonl_expected"] is True
    assert built.state["citation_map_jsonl_valid"] is False
    assert gates.diagnostic_parity_pass is False
    assert any("citation_map_jsonl_valid" in r for r in gates.diagnostic_reasons)


def test_health_warning_triggers_diagnostic_fail(tmp_path):
    left = _make_bundle(
        tmp_path / "left",
        retrieval_manifested=False,
        citation_manifested=False,
        citation_valid=False,
        sqlite_present=True,
        fts_non_empty=True,
        health_warning=False,
    )
    right = _make_bundle(
        tmp_path / "right",
        retrieval_manifested=False,
        citation_manifested=False,
        citation_valid=False,
        sqlite_present=True,
        fts_non_empty=True,
        health_warning=True,
    )

    built = build_parity_state(left, right)
    gates = evaluate_parity_gates(built.state)

    assert built.state["no_health_warnings"] is False
    assert gates.diagnostic_parity_pass is False


def test_content_parity_passes_with_equal_empty_fts_when_not_expected(tmp_path):
    left = _make_bundle(
        tmp_path / "left",
        retrieval_manifested=False,
        citation_manifested=False,
        citation_valid=False,
        sqlite_present=False,
        fts_non_empty=False,
        health_warning=False,
    )
    right = _make_bundle(
        tmp_path / "right",
        retrieval_manifested=False,
        citation_manifested=False,
        citation_valid=False,
        sqlite_present=False,
        fts_non_empty=False,
        health_warning=False,
    )

    built = build_parity_state(left, right)
    gates = evaluate_parity_gates(built.state)

    assert built.state["fts_non_empty_expected"] is False
    assert built.state["fts_non_empty"] is False
    assert gates.content_parity_pass is True
