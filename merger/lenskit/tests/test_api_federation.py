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
    }

    response = client.post("/api/federation/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

    data = response.json()
    # Contract constraint: with trace=True and a profile, we must receive a wrapper
    assert "context_bundle" in data
    assert "federation_trace" in data
    assert "agent_query_session" in data
    assert "hits" not in data  # hits must be strictly inside context_bundle

    bundle = data["context_bundle"]
    assert "hits" in bundle

    # Verify agent_minimal projection acted on federation hits
    # Note: `agent_minimal` projection applies only to existing fields on the federated hits structure.
    # It does not construct full semantic bundle context, only strips what exists.
    if len(bundle["hits"]) > 0:
        hit = bundle["hits"][0]
        assert "explain" not in hit  # stripped by agent_minimal
        assert "graph_context" not in hit

    session = data["agent_query_session"]
    assert "r1" in session["resolved_bundles"]
    assert "session_meta" in session
    assert session["session_meta"]["context_source"] == "both"


def test_api_federation_query_invalid_path(fed_setup):
    request_data = {
        "federation_index": "../federation.json",
        "q": "hello",
        "k": 1
    }
    response = client.post("/api/federation/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 400
    assert "Invalid federation_index path" in response.json()["detail"]


def test_api_federation_query_no_trace(fed_setup):
    request_data = {
        "federation_index": "federation.json",
        "q": "hello r1",
        "k": 1,
        "trace": False,
        "output_profile": "agent_minimal",
    }
    response = client.post("/api/federation/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

    data = response.json()
    # When trace is False, output profile "agent_minimal" returns the bundle contents directly at the top level
    assert "hits" in data
    assert "context_bundle" not in data
    assert "federation_trace" not in data
    assert "agent_query_session" not in data

def test_api_federation_query_invalid_output_profile(fed_setup):
    request_data = {
        "federation_index": "federation.json",
        "q": "hello",
        "k": 1,
        "output_profile": "invalid_profile"
    }
    response = client.post("/api/federation/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 422 # Pydantic validation error

def test_api_federation_query_file_not_found(fed_setup):
    request_data = {
        "federation_index": "does_not_exist.json",
        "q": "hello",
        "k": 1
    }
    response = client.post("/api/federation/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 404

def test_api_federation_query_schema_validation_error(fed_setup):
    merges_dir = fed_setup.parent
    invalid_index = merges_dir / "invalid_fed.json"
    invalid_index.write_text('{"kind": "not_a_federation"}', encoding="utf-8")

    request_data = {
        "federation_index": "invalid_fed.json",
        "q": "hello",
        "k": 1
    }
    response = client.post("/api/federation/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 400


def test_api_federation_query_agent_session_artifact_refs_crosscheck(fed_setup):
    """artifact_refs in agent_query_session must match artifact_ids in the federation response.

    Verifies:
    - artifact_ids.context_bundle and artifact_ids.agent_query_session are present.
    - artifact_ids.query_trace is absent (federation has no standalone query_trace artifact).
    - agent_query_session.artifact_refs.context_bundle_id == artifact_ids.context_bundle
    - agent_query_session.artifact_refs.query_trace_id is None (no standalone trace)
    - agent_query_session.artifact_refs.agent_query_session_id is None (Path 2: self-ID
      is circular; the assigned ID is surfaced via artifact_ids.agent_query_session).
    """
    request_data = {
        "federation_index": "federation.json",
        "q": "hello r1",
        "k": 1,
        "output_profile": "agent_minimal",
        "trace": True,
    }

    response = client.post(
        "/api/federation/query",
        json=request_data,
        headers={"Authorization": "Bearer test_token"},
    )
    assert response.status_code == 200

    data = response.json()
    assert "context_bundle" in data, "expected context_bundle wrapper"
    assert "agent_query_session" in data, "expected agent_query_session in response"

    # artifact_ids must include context_bundle and agent_query_session.
    assert "artifact_ids" in data, "artifact_ids missing from federation response"
    artifact_ids = data["artifact_ids"]
    assert "context_bundle" in artifact_ids, "artifact_ids.context_bundle missing"
    assert "agent_query_session" in artifact_ids, "artifact_ids.agent_query_session missing"
    # Federation does not produce a standalone query_trace artifact.
    assert "query_trace" not in artifact_ids, (
        "artifact_ids.query_trace must not be present in federation response"
    )

    session = data["agent_query_session"]
    refs = session["artifact_refs"]

    # Cross-check: context_bundle_id in refs must match artifact_ids.
    assert refs["context_bundle_id"] == artifact_ids["context_bundle"], (
        f"context_bundle_id mismatch: refs={refs['context_bundle_id']!r} vs "
        f"artifact_ids={artifact_ids['context_bundle']!r}"
    )

    # No standalone query_trace for federation — query_trace_id must be null.
    assert refs["query_trace_id"] is None, (
        "query_trace_id must be null for federation (no standalone query_trace artifact)"
    )

    # Path 2: agent_query_session_id is intentionally null (self-ID circular).
    # The assigned ID is available via artifact_ids.agent_query_session.
    assert refs["agent_query_session_id"] is None, (
        "agent_query_session_id must be null in the payload (self-ID is carried via "
        f"artifact_ids.agent_query_session={artifact_ids['agent_query_session']!r})"
    )
