import json
from pathlib import Path
import pytest
import hashlib
from merger.lenskit.retrieval import index_db, query_core
from merger.lenskit.core.range_resolver import resolve_range_ref

def test_range_roundtrip(tmp_path):
    # This acts as the PR 5 "Roundtrip-Test: Top-Result -> range_get -> extrahierter Text matcht Hash"
    # We will build a dummy chunk that points to a dummy source.

    # 1. Setup the workspace files
    manifest_path = tmp_path / "bundle.manifest.json"
    artifact_path = tmp_path / "code.md"
    content = b"Line 1\nHello World\nLine 3\n"
    artifact_path.write_bytes(content)

    start_byte = 7
    end_byte = 19 # "Hello World\n"
    expected_sha256 = hashlib.sha256(content[start_byte:end_byte]).hexdigest()

    manifest_data = {
        "kind": "repolens.bundle.manifest",
        "run_id": "test-run",
        "artifacts": [
            {
                "role": "canonical_md",
                "path": "code.md"
            }
        ]
    }
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    # 2. Build the Index with range_ref attached
    db_path = tmp_path / "index.sqlite"
    dump_path = tmp_path / "dump.json"
    chunk_path = tmp_path / "chunks.jsonl"

    ref_obj = {
        "artifact_role": "canonical_md",
        "repo_id": "r1",
        "file_path": "code.md",
        "start_byte": start_byte,
        "end_byte": end_byte,
        "start_line": 2,
        "end_line": 2,
        "content_sha256": expected_sha256
    }

    chunk_data = [
        {
            "chunk_id": "c1", "repo_id": "r1", "path": "code.md", "content": "Hello World\n",
            "start_line": 2, "end_line": 2, "layer": "core", "artifact_type": "code", "content_sha256": expected_sha256,
            "content_range_ref": ref_obj
        }
    ]
    with chunk_path.open("w", encoding="utf-8") as f:
        for c in chunk_data:
            f.write(json.dumps(c) + "\n")

    dump_path.write_text(json.dumps({"dummy": "data"}))
    index_db.build_index(dump_path, chunk_path, db_path)

    # 3. Query the text
    res = query_core.execute_query(db_path, query_text="Hello", k=1)
    assert res["count"] == 1
    hit = res["results"][0]

    # 4. Resolve the text
    assert "range_ref" in hit
    retrieved_ref = hit["range_ref"]

    resolved = resolve_range_ref(manifest_path, retrieved_ref)

    # 5. Assert match
    assert resolved["text"] == "Hello World\n"
    assert resolved["sha256"] == expected_sha256
