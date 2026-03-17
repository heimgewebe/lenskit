import pytest
import json
import sqlite3
from pathlib import Path

from merger.lenskit.core.federation import init_federation, add_bundle
from merger.lenskit.retrieval.federation_query import execute_federated_query
from merger.lenskit.retrieval import index_db

@pytest.fixture
def federated_setup(tmp_path):
    # Setup paths
    fed_path = tmp_path / "federation.json"
    init_federation("test-fed", fed_path)

    # Bundle 1
    b1_dir = tmp_path / "repo1"
    b1_dir.mkdir()
    b1_dump = b1_dir / "dump.json"
    b1_chunks = b1_dir / "chunks.jsonl"
    b1_db = b1_dir / "chunk_index.index.sqlite"

    chunk_data_1 = [
        {"chunk_id": "c1", "repo_id": "repo1", "path": "src/main.py", "content": "def main(): print('hello repo1')", "start_line": 1, "end_line": 1, "layer": "core", "artifact_type": "code", "content_sha256": "h1"}
    ]
    with b1_chunks.open("w", encoding="utf-8") as f:
        for c in chunk_data_1:
            f.write(json.dumps(c) + "\n")
    b1_dump.write_text(json.dumps({"dummy": "data"}), encoding="utf-8")
    index_db.build_index(b1_dump, b1_chunks, b1_db)

    # Bundle 2
    b2_dir = tmp_path / "repo2"
    b2_dir.mkdir()
    b2_dump = b2_dir / "dump.json"
    b2_chunks = b2_dir / "chunks.jsonl"
    b2_db = b2_dir / "chunk_index.index.sqlite"

    chunk_data_2 = [
        {"chunk_id": "c2", "repo_id": "repo2", "path": "src/main.py", "content": "def main(): print('hello repo2')", "start_line": 1, "end_line": 1, "layer": "core", "artifact_type": "code", "content_sha256": "h2"},
        {"chunk_id": "c3", "repo_id": "repo2", "path": "tests/test_main.py", "content": "def test_main(): assert True", "start_line": 1, "end_line": 1, "layer": "test", "artifact_type": "code", "content_sha256": "h3"}
    ]
    with b2_chunks.open("w", encoding="utf-8") as f:
        for c in chunk_data_2:
            f.write(json.dumps(c) + "\n")
    b2_dump.write_text(json.dumps({"dummy": "data"}), encoding="utf-8")
    index_db.build_index(b2_dump, b2_chunks, b2_db)

    # Add bundles to federation
    add_bundle(fed_path, "repo1", str(b1_dir))
    add_bundle(fed_path, "repo2", str(b2_dir))

    return fed_path

def test_execute_federated_query(federated_setup):
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10
    )

    assert res["federation_id"] == "test-fed"
    assert res["count"] == 2

    # Verify provenance
    repos = {h["federation_bundle"] for h in res["results"]}
    assert repos == {"repo1", "repo2"}

def test_execute_federated_query_with_repo_filter(federated_setup):
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        filters={"repo": "repo1"}
    )

    assert res["count"] == 1
    assert res["results"][0]["federation_bundle"] == "repo1"

def test_execute_federated_query_with_trace(federated_setup):
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        trace=True
    )

    assert "federation_trace" in res
    trace = res["federation_trace"]
    assert "bundle_status" in trace
    assert trace["bundle_status"]["repo1"] == "ok"
    assert trace["bundle_status"]["repo2"] == "ok"
    assert "bundle_traces" in trace
    assert "repo1" in trace["bundle_traces"]
    assert "repo2" in trace["bundle_traces"]
