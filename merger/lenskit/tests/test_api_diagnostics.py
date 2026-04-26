"""Tests for GET /api/diagnostics: typed read-only facade over diagnostics.snapshot.json.
"""
import json
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except ImportError:
    jsonschema = None

from fastapi.testclient import TestClient
from merger.lenskit.service.app import app
from merger.lenskit.service import app as service_app
_HAS_FASTAPI = True

requires_fastapi = pytest.mark.skipif(not _HAS_FASTAPI, reason="fastapi not installed")

_AUTH = {"Authorization": "Bearer test_token"}

_SCHEMA_PATH = Path(__file__).parent.parent / "contracts" / "diagnostics-lookup.v1.schema.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_hub(tmp_path):
    hub_path = tmp_path / "hub"
    hub_path.mkdir()
    merges_dir = tmp_path / "merges"
    merges_dir.mkdir()

    # Initialize service state to ensure hub is configured
    service_app.init_service(hub_path=hub_path, token="test_token", merges_dir=merges_dir)
    return hub_path


@pytest.fixture
def api_client(test_hub):
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@requires_fastapi
class TestApiDiagnosticsLookup:

    def test_diagnostics_lookup_not_found(self, api_client, test_hub):
        """If diagnostics.snapshot.json is missing, should return status: not_found."""
        # Ensure the cache dir exists and file does NOT exist
        cache_dir = test_hub / ".gewebe" / "cache"
        if cache_dir.exists():
            diag_file = cache_dir / "diagnostics.snapshot.json"
            if diag_file.exists():
                diag_file.unlink()

        resp = api_client.get("/api/diagnostics", headers=_AUTH)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_found"
        assert "message" in data

    def test_diagnostics_lookup_invalid_json(self, api_client, test_hub):
        """If diagnostics.snapshot.json is invalid JSON, should return status: error."""
        cache_dir = test_hub / ".gewebe" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        diag_file = cache_dir / "diagnostics.snapshot.json"
        diag_file.write_text("invalid json {", encoding="utf-8")

        resp = api_client.get("/api/diagnostics", headers=_AUTH)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "message" in data

    def test_diagnostics_lookup_ok(self, api_client, test_hub):
        """If valid diagnostics snapshot exists, should return data directly without rebuild side effect."""
        cache_dir = test_hub / ".gewebe" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        diag_file = cache_dir / "diagnostics.snapshot.json"

        valid_data = {
            "schema_version": "diagnostics.snapshot.v1",
            "status": "ok",
            "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "summary": {"ok": 1, "issue": 0, "missing": 0, "issues_total": 0},
            "data": {
                "repo-a": {"status": "ok", "checks": [], "role": "unknown"}
            }
        }
        diag_file.write_text(json.dumps(valid_data), encoding="utf-8")

        # Track mtime to verify no rebuild occurs
        mtime_before = diag_file.stat().st_mtime

        resp = api_client.get("/api/diagnostics", headers=_AUTH)
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "ok"
        assert data["summary"]["ok"] == 1
        assert "repo-a" in data["data"]

        # Verify no rebuild side-effect
        assert diag_file.stat().st_mtime == mtime_before

    def test_diagnostics_lookup_ttl_warn(self, api_client, test_hub):
        """If generated_at is older than TTL_HOURS (24), should return warn status."""
        cache_dir = test_hub / ".gewebe" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        diag_file = cache_dir / "diagnostics.snapshot.json"

        old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime('%Y-%m-%dT%H:%M:%SZ')
        valid_data = {
            "schema_version": "diagnostics.snapshot.v1",
            "status": "ok",
            "generated_at": old_ts,
            "summary": {"ok": 1, "issue": 0, "missing": 0, "issues_total": 0},
            "data": {}
        }
        diag_file.write_text(json.dumps(valid_data), encoding="utf-8")

        resp = api_client.get("/api/diagnostics", headers=_AUTH)
        assert resp.status_code == 200
        data = resp.json()

        # Status should be modified to warn on the fly
        assert data["status"] == "warn"
        assert "outdated" in data["message"]

    def test_diagnostics_lookup_requires_auth(self, api_client):
        """Ensure endpoint requires authentication."""
        resp = api_client.get("/api/diagnostics")
        assert resp.status_code == 401

    def test_diagnostics_lookup_contract_compliance(self, api_client, test_hub):
        """Responses must validate against diagnostics-lookup.v1.schema.json."""
        if jsonschema is None:
            pytest.skip("jsonschema not available")

        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

        # 1. Check Not Found Response
        cache_dir = test_hub / ".gewebe" / "cache"
        if cache_dir.exists():
            diag_file = cache_dir / "diagnostics.snapshot.json"
            if diag_file.exists():
                diag_file.unlink()

        resp = api_client.get("/api/diagnostics", headers=_AUTH)
        assert resp.status_code == 200
        jsonschema.validate(instance=resp.json(), schema=schema)

        # 2. Check OK Response
        cache_dir.mkdir(parents=True, exist_ok=True)
        diag_file = cache_dir / "diagnostics.snapshot.json"
        valid_data = {
            "schema_version": "diagnostics.snapshot.v1",
            "status": "ok",
            "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "summary": {"ok": 1, "issue": 0, "missing": 0, "issues_total": 0},
            "data": {
                "repo-a": {"status": "ok", "checks": [], "role": "unknown"}
            }
        }
        diag_file.write_text(json.dumps(valid_data), encoding="utf-8")

        resp2 = api_client.get("/api/diagnostics", headers=_AUTH)
        assert resp2.status_code == 200
        jsonschema.validate(instance=resp2.json(), schema=schema)
