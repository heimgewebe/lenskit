import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from merger.lenskit.service.app import app
from merger.lenskit.service import app as service_app
import json
from merger.lenskit.retrieval import index_db

@pytest.fixture
def mini_index(tmp_path):
    dump_path = tmp_path / "dump.json"
    chunk_path = tmp_path / "chunks.jsonl"
    db_path = tmp_path / ".index.sqlite"

    chunk_data = [
        {
            "chunk_id": "c1", "repo_id": "r1", "path": "src/main.py",
            "content": "def main():\n    print('hello world')\n    return 0",
            "start_line": 10, "end_line": 12, "layer": "core", "artifact_type": "code", "content_sha256": "h1"
        },
        {
            "chunk_id": "c2", "repo_id": "r1", "path": "src/main.py",
            "content": "def helper():\n    pass",
            "start_line": 15, "end_line": 16, "layer": "core", "artifact_type": "code", "content_sha256": "h2"
        },
    ]
    with chunk_path.open("w", encoding="utf-8") as f:
        for c in chunk_data:
            f.write(json.dumps(c) + "\n")

    dump_path.write_text(json.dumps({"dummy": "data"}), encoding="utf-8")
    index_db.build_index(dump_path, chunk_path, db_path)
    return db_path

client = TestClient(app)

def setup_test_artifact(mini_index=None, merges_dir_name=None, key="sqlite_index", filename=None):
    hub_path = Path("/tmp")
    if mini_index and merges_dir_name:
        hub_path = Path(mini_index.parent.parent)

    service_app.init_service(hub_path=hub_path, token="test_token")
    from merger.lenskit.service.models import Artifact, JobRequest
    from merger.lenskit.service.app import state

    req = JobRequest(repos=["repo"], level="max", mode="gesamt")

    hub_str = str(mini_index.parent.parent) if (mini_index and merges_dir_name) else "/tmp"
    merges_dir_val = merges_dir_name if merges_dir_name else (str(mini_index.parent) if mini_index else "/tmp")

    art = Artifact(
        id="test", job_id="test", hub=hub_str, repos=["repo"],
        created_at="now", paths={}, params=req, merges_dir=merges_dir_val
    )
    if key and mini_index:
        art.paths[key] = filename if filename else mini_index.name
    state.job_store.add_artifact(art)
    return art


def test_api_query_valid(mini_index):
    art = setup_test_artifact(mini_index)

    request_data = {
        "index_id": art.id,
        "q": "hello",
        "k": 1,
        "explain": True, "stale_policy": "ignore"
    }

    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

    data = response.json()
    assert "hits" not in data # Because we didn't use an output profile, it returns the raw wrapper
    assert "results" in data
    assert len(data["results"]) == 1
    hit = data["results"][0]
    assert "explain" in data

    # Internal fields should not be present
    assert "_raw_content" not in str(data)

def test_api_query_agent_minimal(mini_index):
    art = setup_test_artifact(mini_index)

    request_data = {
        "index_id": art.id,
        "q": "hello",
        "k": 1,
        "output_profile": "agent_minimal",
        "explain": True, "stale_policy": "ignore"
    }

    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

    data = response.json()
    assert "hits" in data
    hit = data["hits"][0]

    # Agent minimal should strip explain and surrounding_context (if null)
    assert "explain" not in hit
    assert "graph_context" not in hit
    assert "surrounding_context" not in hit

def test_api_query_context_bundle(mini_index):
    art = setup_test_artifact(mini_index)

    request_data = {
        "index_id": art.id,
        "q": "hello",
        "k": 1,
        "build_context_bundle": True, "stale_policy": "ignore"
    }

    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

    data = response.json()
    assert "context_bundle" in data
    assert "hits" in data["context_bundle"]

def test_api_query_trace(mini_index):
    art = setup_test_artifact(mini_index)

    request_data = {
        "index_id": art.id,
        "q": "hello",
        "k": 1,
        "trace": True, "stale_policy": "ignore"
    }

    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

    data = response.json()
    assert "query_trace" in data
    assert "timings" in data["query_trace"]

def test_api_query_invalid_params(mini_index):
    art = setup_test_artifact(mini_index)

    request_data = {
        "index_id": art.id,
        "q": "hello",
        "context_mode": "window",
        "context_window_lines": 0, "stale_policy": "ignore" # Invalid
    }

    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 400
    assert "requires" in response.json()["detail"]

def test_api_query_trace_wrapper(mini_index):
    art = setup_test_artifact(mini_index)

    request_data = {
        "index_id": art.id,
        "q": "hello",
        "k": 1,
        "output_profile": "agent_minimal",
        "trace": True,
        "stale_policy": "ignore"
    }

    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

    data = response.json()
    assert "context_bundle" in data
    assert "query_trace" in data
    assert "query_trace" not in data["context_bundle"]

    hit = data["context_bundle"]["hits"][0]
    # Agent minimal should strip explain and surrounding_context (if null)
    assert "explain" not in hit
    assert "graph_context" not in hit
    assert "surrounding_context" not in hit

def test_api_query_relative_merges_dir(mini_index):
    art = setup_test_artifact(mini_index, merges_dir_name=mini_index.parent.name)

    request_data = {
        "index_id": art.id,
        "q": "hello",
        "k": 1,
        "explain": True, "stale_policy": "ignore"
    }

    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

def test_api_query_missing_sqlite_key():
    art = setup_test_artifact(mini_index=None, key=None)

    request_data = {
        "index_id": art.id,
        "q": "hello"
    }
    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 400
    assert "does not contain an SQLite index" in response.json()["detail"]

def test_api_query_legacy_index_sqlite_key(mini_index):
    art = setup_test_artifact(mini_index, key="index_sqlite")

    request_data = {
        "index_id": art.id,
        "q": "hello",
        "stale_policy": "ignore"
    }
    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

def test_api_query_file_not_found(mini_index):
    art = setup_test_artifact(mini_index, filename="does_not_exist.sqlite")

    request_data = {
        "index_id": art.id,
        "q": "hello",
        "stale_policy": "ignore"
    }
    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 404

def test_api_query_graph_index_not_found(mini_index):
    art = setup_test_artifact(mini_index)

    request_data = {
        "index_id": art.id,
        "q": "hello",
        "stale_policy": "ignore",
        "graph_index": "does_not_exist.json"
    }
    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 404
    assert "graph index" in response.json()["detail"].lower()

def test_api_query_invalid_paths(mini_index):
    art = setup_test_artifact(mini_index)

    # Test backslash (Windows-style traversal attack)
    request_data = {
        "index_id": art.id,
        "q": "hello",
        "stale_policy": "ignore",
        "graph_index": "..\\evil.json"
    }
    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 400
    assert "Invalid graph_index path" in response.json()["detail"]

    # Test colon (Drive letter attack)
    request_data["graph_index"] = "C:evil.json"
    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 400
    assert "Invalid graph_index path" in response.json()["detail"]

    # Test slash (Linux-style traversal attack)
    request_data["graph_index"] = "../evil.json"
    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 400
    assert "Invalid graph_index path" in response.json()["detail"]

    # Test embedding policy
    request_data["graph_index"] = None
    request_data["embedding_policy"] = "..\\evil.json"
    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 400
    assert "Invalid embedding_policy path" in response.json()["detail"]

def test_agent_query_contract_roundtrip(mini_index):
    art = setup_test_artifact(mini_index)

    request_data = {
        "index_id": art.id,
        "q": "hello",
        "k": 1,
        "output_profile": "agent_minimal",
        "trace": True,
        "explain": True,
        "stale_policy": "ignore"
    }

    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

    data = response.json()
    # Contract validation
    # Wrapper is expected since trace=True
    assert "context_bundle" in data
    assert isinstance(data["context_bundle"], dict)
    assert "query_trace" in data
    assert isinstance(data["query_trace"], dict)
    assert "hits" not in data

    bundle = data["context_bundle"]
    assert "hits" in bundle
    assert isinstance(bundle["hits"], list)

    assert len(bundle["hits"]) == 1
    hit = bundle["hits"][0]
    # Core fields must be present
    assert "hit_identity" in hit
    assert "resolved_code_snippet" in hit
    assert "path" in hit

    # Profile specific assert (agent_minimal strips explain and graph_context)
    assert "explain" not in hit
    assert "graph_context" not in hit

def test_api_query_lookup_minimal(mini_index):
    art = setup_test_artifact(mini_index)

    request_data = {
        "index_id": art.id,
        "q": "hello",
        "k": 1,
        "output_profile": "lookup_minimal",
        "explain": True, "stale_policy": "ignore"
    }

    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

    data = response.json()
    assert "hits" in data
    assert "context_bundle" not in data
    assert "query_trace" not in data
    assert len(data["hits"]) == 1
    hit = data["hits"][0]
    # lookup_minimal should strip explain, graph_context, surrounding_context
    assert "explain" not in hit
    assert "graph_context" not in hit
    assert "surrounding_context" not in hit
    # But core fields are retained
    assert "resolved_code_snippet" in hit

def test_api_query_review_context(mini_index):
    art = setup_test_artifact(mini_index)

    # Case A: Explicitly request context generation so surrounding_context is definitely present
    request_data_with_context = {
        "index_id": art.id,
        "q": "hello",
        "k": 1,
        "context_mode": "window",
        "context_window_lines": 5,
        "output_profile": "review_context",
        "explain": True,
        "stale_policy": "ignore"
    }

    response_with_ctx = client.post("/api/query", json=request_data_with_context, headers={"Authorization": "Bearer test_token"})
    assert response_with_ctx.status_code == 200

    data_with_ctx = response_with_ctx.json()
    assert "hits" in data_with_ctx
    assert "context_bundle" not in data_with_ctx
    assert "query_trace" not in data_with_ctx
    assert len(data_with_ctx["hits"]) == 1
    hit_with_ctx = data_with_ctx["hits"][0]

    # review_context MUST keep explain
    assert "explain" in hit_with_ctx
    # review_context MUST strip graph_context
    assert "graph_context" not in hit_with_ctx
    # surrounding_context MUST be present and not None because we requested window context
    assert "surrounding_context" in hit_with_ctx
    assert hit_with_ctx["surrounding_context"] is not None

    # Case B: Standard query without window context, surrounding_context defaults to None internally and should be STRIPPED.
    request_data_without_context = {
        "index_id": art.id,
        "q": "hello",
        "k": 1,
        "output_profile": "review_context",
        "explain": True,
        "stale_policy": "ignore"
    }

    response_no_ctx = client.post("/api/query", json=request_data_without_context, headers={"Authorization": "Bearer test_token"})
    assert response_no_ctx.status_code == 200

    data_no_ctx = response_no_ctx.json()
    assert "hits" in data_no_ctx
    assert "context_bundle" not in data_no_ctx
    assert "query_trace" not in data_no_ctx
    assert len(data_no_ctx["hits"]) == 1
    hit_no_ctx = data_no_ctx["hits"][0]

    # explain MUST be present
    assert "explain" in hit_no_ctx
    # graph_context MUST be stripped
    assert "graph_context" not in hit_no_ctx
    # surrounding_context MUST be strictly ABSENT (since it was None and should be removed)
    assert "surrounding_context" not in hit_no_ctx


def test_api_query_lookup_minimal_with_trace(mini_index):
    art = setup_test_artifact(mini_index)

    request_data = {
        "index_id": art.id,
        "q": "hello",
        "k": 1,
        "output_profile": "lookup_minimal",
        "trace": True,
        "explain": True,
        "stale_policy": "ignore"
    }

    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

    data = response.json()
    assert "context_bundle" in data
    assert isinstance(data["context_bundle"], dict)
    assert "query_trace" in data
    assert isinstance(data["query_trace"], dict)
    assert "hits" not in data

    bundle = data["context_bundle"]
    assert "hits" in bundle

    assert len(bundle["hits"]) == 1
    hit = bundle["hits"][0]
    # lookup_minimal should strip explain, graph_context, surrounding_context
    assert "explain" not in hit
    assert "graph_context" not in hit
    assert "surrounding_context" not in hit
    # But core fields are retained
    assert "resolved_code_snippet" in hit

def test_api_query_review_context_with_trace(mini_index):
    art = setup_test_artifact(mini_index)

    # Use context_mode="window" to guarantee surrounding_context is generated
    request_data = {
        "index_id": art.id,
        "q": "hello",
        "k": 1,
        "context_mode": "window",
        "context_window_lines": 5,
        "output_profile": "review_context",
        "trace": True,
        "explain": True,
        "stale_policy": "ignore"
    }

    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

    data = response.json()
    assert "context_bundle" in data
    assert isinstance(data["context_bundle"], dict)
    assert "query_trace" in data
    assert isinstance(data["query_trace"], dict)
    assert "hits" not in data

    bundle = data["context_bundle"]
    assert "hits" in bundle

    assert len(bundle["hits"]) == 1
    hit = bundle["hits"][0]
    # review_context MUST keep explain
    assert "explain" in hit
    # review_context MUST strip graph_context
    assert "graph_context" not in hit
    # surrounding_context MUST be present and not None because we requested window context
    assert "surrounding_context" in hit
    assert hit["surrounding_context"] is not None
