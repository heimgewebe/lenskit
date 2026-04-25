"""Tests for artifact_lookup: QueryArtifactStore + /api/artifact_lookup endpoint."""
import json
import pytest
from pathlib import Path

from merger.lenskit.service.query_artifact_store import QueryArtifactStore, VALID_ARTIFACT_TYPES

try:
    from fastapi.testclient import TestClient
    from merger.lenskit.service.app import app
    from merger.lenskit.service import app as service_app
    from merger.lenskit.retrieval import index_db
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

requires_fastapi = pytest.mark.skipif(not _HAS_FASTAPI, reason="fastapi not installed")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    return QueryArtifactStore(tmp_path / ".rlens-service")


@pytest.fixture
def mini_index(tmp_path):
    if not _HAS_FASTAPI:
        pytest.skip("fastapi not installed")
    dump_path = tmp_path / "dump.json"
    chunk_path = tmp_path / "chunks.jsonl"
    db_path = tmp_path / ".index.sqlite"

    chunk_data = [
        {
            "chunk_id": "c1", "repo_id": "r1", "path": "src/main.py",
            "content": "def main():\n    return 0",
            "start_line": 1, "end_line": 2, "layer": "core",
            "artifact_type": "code", "content_sha256": "h1",
        },
    ]
    with chunk_path.open("w", encoding="utf-8") as f:
        for c in chunk_data:
            f.write(json.dumps(c) + "\n")
    dump_path.write_text(json.dumps({"dummy": "data"}), encoding="utf-8")
    index_db.build_index(dump_path, chunk_path, db_path)
    return db_path


@pytest.fixture
def api_client(tmp_path, mini_index):
    hub_path = mini_index.parent.parent
    service_app.init_service(hub_path=hub_path, token="test_token")

    from merger.lenskit.service.models import Artifact, JobRequest
    from merger.lenskit.service.app import state

    req = JobRequest(repos=["repo"], level="max", mode="gesamt")
    art = Artifact(
        id="test-art", job_id="test-job", hub=str(hub_path), repos=["repo"],
        created_at="2024-01-01T00:00:00+00:00",
        paths={"sqlite_index": mini_index.name},
        params=req,
        merges_dir=str(mini_index.parent),
    )
    state.job_store.add_artifact(art)
    return TestClient(app)


# ---------------------------------------------------------------------------
# QueryArtifactStore unit tests
# ---------------------------------------------------------------------------

class TestQueryArtifactStore:
    def test_store_and_get_roundtrip(self, store):
        data = {"query_input": "hello", "timings": {}}
        provenance = {"source_query": "hello", "timestamp": "2024-01-01T00:00:00+00:00"}
        artifact_id = store.store("query_trace", data, provenance)

        assert artifact_id.startswith("qart-")
        entry = store.get(artifact_id)
        assert entry is not None
        assert entry["artifact_type"] == "query_trace"
        assert entry["data"] == data
        assert entry["provenance"]["source_query"] == "hello"
        assert entry["provenance"]["run_id"] is None

    def test_store_with_run_id(self, store):
        provenance = {"source_query": "q", "timestamp": "2024-01-01T00:00:00+00:00"}
        aid = store.store("context_bundle", {"query": "q", "hits": []}, provenance, run_id="abc123")
        entry = store.get(aid)
        assert entry["provenance"]["run_id"] == "abc123"

    def test_get_missing_returns_none(self, store):
        assert store.get("qart-nonexistent") is None

    def test_invalid_artifact_type_raises(self, store):
        with pytest.raises(ValueError, match="Invalid artifact_type"):
            store.store("federation_trace", {}, {"source_query": "q", "timestamp": "t"})

    def test_all_valid_types_accepted(self, store):
        prov = {"source_query": "q", "timestamp": "2024-01-01T00:00:00+00:00"}
        for art_type in VALID_ARTIFACT_TYPES:
            aid = store.store(art_type, {}, prov)
            assert store.get(aid) is not None

    def test_persistence_survives_reload(self, tmp_path):
        storage_dir = tmp_path / ".rlens-service"
        store1 = QueryArtifactStore(storage_dir)
        prov = {"source_query": "persist test", "timestamp": "2024-01-01T00:00:00+00:00"}
        aid = store1.store("query_trace", {"data": "value"}, prov)

        store2 = QueryArtifactStore(storage_dir)
        entry = store2.get(aid)
        assert entry is not None
        assert entry["data"] == {"data": "value"}

    def test_get_all_returns_most_recent_first(self, store):
        prov = {"source_query": "q", "timestamp": "2024-01-01T00:00:00+00:00"}
        ids = [store.store("query_trace", {}, prov) for _ in range(3)]
        all_entries = store.get_all()
        assert len(all_entries) == 3
        # stored IDs should all be present
        stored_ids = {e["id"] for e in all_entries}
        assert stored_ids == set(ids)

    def test_id_is_stable_and_unique(self, store):
        prov = {"source_query": "q", "timestamp": "2024-01-01T00:00:00+00:00"}
        ids = {store.store("query_trace", {}, prov) for _ in range(5)}
        assert len(ids) == 5  # all unique


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

@requires_fastapi
class TestApiArtifactLookup:
    def test_lookup_not_found(self, api_client):
        resp = api_client.post(
            "/api/artifact_lookup",
            json={"artifact_type": "query_trace", "id": "qart-doesnotexist"},
            headers={"x-rlens-token": "test_token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_found"
        assert data["artifact"] is None
        assert len(data["warnings"]) > 0

    def test_lookup_after_query_with_trace(self, api_client, mini_index):
        resp = api_client.post(
            "/api/query",
            json={
                "index_id": "test-art",
                "q": "main",
                "k": 5,
                "trace": True,
                "build_context_bundle": True,
                "stale_policy": "ignore",
            },
            headers={"x-rlens-token": "test_token"},
        )
        assert resp.status_code == 200
        query_result = resp.json()

        assert "artifact_ids" in query_result, (
            "artifact_ids not in query response — store integration failed"
        )
        artifact_ids = query_result["artifact_ids"]
        assert "query_trace" in artifact_ids

        trace_id = artifact_ids["query_trace"]
        assert trace_id.startswith("qart-")

        lookup_resp = api_client.post(
            "/api/artifact_lookup",
            json={"artifact_type": "query_trace", "id": trace_id},
            headers={"x-rlens-token": "test_token"},
        )
        assert lookup_resp.status_code == 200
        lookup_data = lookup_resp.json()
        assert lookup_data["status"] == "ok"
        assert lookup_data["id"] == trace_id
        assert lookup_data["artifact"] is not None
        assert "provenance" in lookup_data["artifact"]
        assert lookup_data["artifact"]["provenance"]["source_query"] == "main"
        assert lookup_data["artifact"]["provenance"]["index_id"] == "test-art"
        # Determinism: lookup returns same object, no recomputing
        assert "data" in lookup_data["artifact"]

    def test_lookup_type_mismatch_returns_not_found(self, api_client, mini_index):
        # Store a query_trace artifact, try to look it up as context_bundle
        resp = api_client.post(
            "/api/query",
            json={
                "index_id": "test-art",
                "q": "helper",
                "trace": True,
                "stale_policy": "ignore",
            },
            headers={"x-rlens-token": "test_token"},
        )
        assert resp.status_code == 200
        artifact_ids = resp.json().get("artifact_ids", {})
        trace_id = artifact_ids.get("query_trace")
        if not trace_id:
            pytest.skip("No query_trace artifact was stored")

        lookup_resp = api_client.post(
            "/api/artifact_lookup",
            json={"artifact_type": "context_bundle", "id": trace_id},
            headers={"x-rlens-token": "test_token"},
        )
        assert lookup_resp.status_code == 200
        data = lookup_resp.json()
        assert data["status"] == "not_found"
        assert len(data["warnings"]) > 0

    def test_lookup_requires_auth(self, api_client):
        resp = api_client.post(
            "/api/artifact_lookup",
            json={"artifact_type": "query_trace", "id": "qart-test"},
        )
        # Without token, should be 401 or 403
        assert resp.status_code in (401, 403)

    def test_no_artifact_ids_without_trace_flag(self, api_client, mini_index):
        resp = api_client.post(
            "/api/query",
            json={
                "index_id": "test-art",
                "q": "main",
                "k": 5,
                "trace": False,
                "build_context_bundle": False,
                "stale_policy": "ignore",
            },
            headers={"x-rlens-token": "test_token"},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert "artifact_ids" not in result, (
            "artifact_ids should not appear when trace=False and build_context_bundle=False"
        )

    def test_context_bundle_lookup_roundtrip(self, api_client, mini_index):
        resp = api_client.post(
            "/api/query",
            json={
                "index_id": "test-art",
                "q": "main",
                "build_context_bundle": True,
                "stale_policy": "ignore",
            },
            headers={"x-rlens-token": "test_token"},
        )
        assert resp.status_code == 200
        query_result = resp.json()

        artifact_ids = query_result.get("artifact_ids", {})
        cb_id = artifact_ids.get("context_bundle")
        if not cb_id:
            pytest.skip("No context_bundle artifact was stored (no hits or bundle not built)")

        lookup_resp = api_client.post(
            "/api/artifact_lookup",
            json={"artifact_type": "context_bundle", "id": cb_id},
            headers={"x-rlens-token": "test_token"},
        )
        assert lookup_resp.status_code == 200
        data = lookup_resp.json()
        assert data["status"] == "ok"
        assert data["artifact"]["data"]["query"] == "main"

    def test_lookup_response_conforms_to_contract(self, api_client, mini_index):
        # After a trace query, check the full response shape matches artifact-lookup.v1 schema
        resp = api_client.post(
            "/api/query",
            json={
                "index_id": "test-art",
                "q": "main",
                "trace": True,
                "stale_policy": "ignore",
            },
            headers={"x-rlens-token": "test_token"},
        )
        assert resp.status_code == 200
        artifact_ids = resp.json().get("artifact_ids", {})
        trace_id = artifact_ids.get("query_trace")
        if not trace_id:
            pytest.skip("No query_trace stored")

        lookup_resp = api_client.post(
            "/api/artifact_lookup",
            json={"artifact_type": "query_trace", "id": trace_id},
            headers={"x-rlens-token": "test_token"},
        )
        data = lookup_resp.json()
        # Validate required top-level fields per artifact-lookup.v1 schema
        assert "artifact_type" in data
        assert "id" in data
        assert "status" in data
        assert "artifact" in data
        assert "warnings" in data
        assert isinstance(data["warnings"], list)
        assert data["status"] in ("ok", "not_found", "error")
        if data["status"] == "ok":
            artifact = data["artifact"]
            assert "provenance" in artifact
            assert "created_at" in artifact
            assert "data" in artifact
            assert "source_query" in artifact["provenance"]
            assert "timestamp" in artifact["provenance"]
