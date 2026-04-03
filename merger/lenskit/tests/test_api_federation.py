import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from merger.lenskit.service.app import app
from merger.lenskit.service import app as service_app
import json
from merger.lenskit.retrieval import index_db

client = TestClient(app)

@pytest.fixture
def fed_setup(tmp_path):
    hub_path = tmp_path / "hub"
    hub_path.mkdir()
    merges_dir = tmp_path / "merges"
    merges_dir.mkdir()

    # repo 1
    dump_path1 = tmp_path / "dump1.json"
    chunk_path1 = tmp_path / "chunks1.jsonl"
    db_path1 = tmp_path / "1.chunk_index.index.sqlite"

    chunk_data1 = [{"chunk_id": "c1", "repo_id": "r1", "path": "src/main.py", "content": "def main(): print('hello r1')", "start_line": 1, "end_line": 2, "layer": "core", "artifact_type": "code", "content_sha256": "h1"}]
    with chunk_path1.open("w", encoding="utf-8") as f:
        for c in chunk_data1: f.write(json.dumps(c) + "\n")
    dump_path1.write_text(json.dumps({"dummy": "data"}), encoding="utf-8")
    index_db.build_index(dump_path1, chunk_path1, db_path1)

    fed_index = merges_dir / "federation.json"
    fed_data = {
        "kind": "repolens.federation.index", "version": "1.0", "created_at": "2026-04-03T16:30:36.125043+00:00", "updated_at": "2026-04-03T16:30:55.046944+00:00", "federation_id": "fed1",
        "bundles": [
            {"repo_id": "r1", "bundle_path": str(tmp_path)}
        ]
    }
    fed_index.write_text(json.dumps(fed_data), encoding="utf-8")

    service_app.init_service(hub_path=hub_path, token="test_token", merges_dir=merges_dir)
    return fed_index

def test_api_federation_query_valid(fed_setup):
    request_data = {
        "federation_index": "federation.json",
        "q": "hello r1",
        "k": 1,
        "explain": True,
        "trace": True,
        "output_profile": "agent_minimal",
        "stale_policy": "ignore"
    }

    response = client.post("/api/federation/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

    data = response.json()
    assert "context_bundle" in data
    assert "agent_query_session" in data

    session = data["agent_query_session"]
    assert "r1" in session["resolved_bundles"]
    assert session["session_meta"]["context_source"] == "both"
