import pytest
from pathlib import Path
import json
import time
from fastapi.testclient import TestClient

from merger.lenskit.service.app import app, init_service, verify_token
from merger.lenskit.service.models import AtlasArtifact

@pytest.fixture
def lifecycle_client(tmp_path: Path):
    # Setup test directories
    hub = tmp_path / "hub"
    merges = hub / ".repolens" / "merges"
    merges.mkdir(parents=True)

    # Create test artifacts in reverse chronological order
    # Oldest: Failed
    failed_data = {
        "status": "failed",
        "root": "/test",
        "created_at": "2024-01-01T10:00:00Z",
        "error": "Failed early"
    }
    (merges / "atlas-1000.json").write_text(json.dumps(failed_data), encoding="utf-8")

    # Middle: Completed
    completed_data = {
        "status": "completed",
        "root": "/test",
        "created_at": "2024-01-02T10:00:00Z",
        "stats": {"total_files": 1}
    }
    (merges / "atlas-2000.json").write_text(json.dumps(completed_data), encoding="utf-8")

    # Newest: Running
    running_data = {
        "status": "running",
        "root": "/test",
        "created_at": "2024-01-03T10:00:00Z"
    }
    (merges / "atlas-3000.json").write_text(json.dumps(running_data), encoding="utf-8")

    # Reset FastAPI middleware stack explicitly BEFORE init_service
    app.middleware_stack = None
    app.user_middleware.clear()

    init_service(hub_path=hub, merges_dir=merges)

    app.dependency_overrides[verify_token] = lambda: True
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()

def test_list_all_artifacts(lifecycle_client: TestClient):
    response = lifecycle_client.get("/api/atlas")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 3

    # Verify sorting: newest first (atlas-3000 -> 2000 -> 1000)
    assert data[0]["id"] == "atlas-3000"
    assert data[0]["status"] == "running"

    assert data[1]["id"] == "atlas-2000"
    assert data[1]["status"] == "completed"

    assert data[2]["id"] == "atlas-1000"
    assert data[2]["status"] == "failed"
    assert data[2]["error"] == "Failed early"

def test_get_latest_artifact_ignores_running_and_failed(lifecycle_client: TestClient):
    response = lifecycle_client.get("/api/atlas/latest")
    assert response.status_code == 200

    data = response.json()

    # Must skip 'atlas-3000' (running) and return 'atlas-2000' (completed)
    assert data["id"] == "atlas-2000"
    assert data["status"] == "completed"

def test_get_latest_artifact_404_if_none_completed(tmp_path: Path):
    # Setup hub with NO completed artifacts
    hub = tmp_path / "hub2"
    merges = hub / ".repolens" / "merges"
    merges.mkdir(parents=True)

    running_data = {
        "status": "running",
        "root": "/test",
        "created_at": "2024-01-03T10:00:00Z"
    }
    (merges / "atlas-3000.json").write_text(json.dumps(running_data), encoding="utf-8")

    app.middleware_stack = None
    app.user_middleware.clear()

    init_service(hub_path=hub, merges_dir=merges)

    app.dependency_overrides[verify_token] = lambda: True
    try:
        with TestClient(app) as client:
            response = client.get("/api/atlas/latest")
            assert response.status_code == 404
            assert "No completed atlas artifacts found" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
