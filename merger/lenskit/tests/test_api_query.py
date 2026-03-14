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

def test_api_query_valid(mini_index):
    # Setup state
    service_app.init_service(hub_path=Path("/tmp"), token="test_token")

    # We must patch get_artifact to return an artifact with the index path
    from merger.lenskit.service.models import Artifact, JobRequest
    from merger.lenskit.service.app import state

    req = JobRequest(repos=["repo"], level="max", mode="gesamt")
    art = Artifact(id="test", job_id="test", hub=str(mini_index.parent.parent), repos=["repo"], created_at="now", paths={}, params=req, merges_dir=str(mini_index.parent))
    art.paths["sqlite_index"] = mini_index.name
    state.job_store.add_artifact(art)

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
    service_app.init_service(hub_path=Path("/tmp"), token="test_token")
    from merger.lenskit.service.models import Artifact, JobRequest
    from merger.lenskit.service.app import state
    req = JobRequest(repos=["repo"], level="max", mode="gesamt")
    art = Artifact(id="test", job_id="test", hub=str(mini_index.parent.parent), repos=["repo"], created_at="now", paths={}, params=req, merges_dir=str(mini_index.parent))
    art.paths["sqlite_index"] = mini_index.name
    state.job_store.add_artifact(art)

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
    service_app.init_service(hub_path=Path("/tmp"), token="test_token")
    from merger.lenskit.service.models import Artifact, JobRequest
    from merger.lenskit.service.app import state
    req = JobRequest(repos=["repo"], level="max", mode="gesamt")
    art = Artifact(id="test", job_id="test", hub=str(mini_index.parent.parent), repos=["repo"], created_at="now", paths={}, params=req, merges_dir=str(mini_index.parent))
    art.paths["sqlite_index"] = mini_index.name
    state.job_store.add_artifact(art)

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
    service_app.init_service(hub_path=Path("/tmp"), token="test_token")
    from merger.lenskit.service.models import Artifact, JobRequest
    from merger.lenskit.service.app import state
    req = JobRequest(repos=["repo"], level="max", mode="gesamt")
    art = Artifact(id="test", job_id="test", hub=str(mini_index.parent.parent), repos=["repo"], created_at="now", paths={}, params=req, merges_dir=str(mini_index.parent))
    art.paths["sqlite_index"] = mini_index.name
    state.job_store.add_artifact(art)

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
    service_app.init_service(hub_path=Path("/tmp"), token="test_token")
    from merger.lenskit.service.models import Artifact, JobRequest
    from merger.lenskit.service.app import state
    req = JobRequest(repos=["repo"], level="max", mode="gesamt")
    art = Artifact(id="test", job_id="test", hub=str(mini_index.parent.parent), repos=["repo"], created_at="now", paths={}, params=req, merges_dir=str(mini_index.parent))
    art.paths["sqlite_index"] = mini_index.name
    state.job_store.add_artifact(art)

    request_data = {
        "index_id": art.id,
        "q": "hello",
        "context_mode": "window",
        "context_window_lines": 0, "stale_policy": "ignore" # Invalid
    }

    response = client.post("/api/query", json=request_data, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 400
    assert "requires" in response.json()["detail"]
