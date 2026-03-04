import pytest
from pathlib import Path
from merger.lenskit.adapters.atlas import AtlasScanner
from fastapi.testclient import TestClient
from merger.lenskit.service.app import app, init_service, state
from unittest.mock import patch, MagicMock

def test_atlas_scan_root_allowed():
    client = TestClient(app)

    mock_hub = Path("/tmp/mock_hub")
    mock_merges = Path("/tmp/mock_merges")

    with patch("merger.lenskit.service.app.get_security_config") as mock_get_sec, \
         patch("merger.lenskit.service.app.AtlasScanner") as MockScanner, \
         patch("merger.lenskit.service.app.render_atlas_md") as mock_render, \
         patch("merger.lenskit.adapters.filesystem.get_security_config") as mock_fs_sec:

        mock_sec_instance = MagicMock()
        mock_sec_instance.validate_path.side_effect = lambda p: Path(p).resolve()
        mock_get_sec.return_value = mock_sec_instance
        mock_fs_sec.return_value = mock_sec_instance

        # Avoid real filesystem issues by passing a state directly
        app.dependency_overrides = {}
        # Setup mock state for test client endpoint
        state.hub = mock_hub
        state.merges_dir = mock_merges

        mock_instance = MockScanner.return_value
        mock_instance.scan.return_value = {"root": "/", "tree": {}}
        mock_render.return_value = "Mock MD"

        payload = {
            "root_id": "/",
            "max_depth": 1,
            "max_entries": 100
        }

        # Override verify_token since we just want to test path resolution
        from merger.lenskit.service.auth import verify_token
        app.dependency_overrides[verify_token] = lambda: True

        response = client.post("/api/atlas", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["root_scanned"] == str(Path("/").resolve())

def test_atlas_scan_home_allowed():
    client = TestClient(app)

    with patch("merger.lenskit.service.app.get_security_config") as mock_get_sec, \
         patch("merger.lenskit.service.app.AtlasScanner") as MockScanner, \
         patch("merger.lenskit.service.app.render_atlas_md") as mock_render:

        mock_sec_instance = MagicMock()
        mock_sec_instance.validate_path.side_effect = lambda p: Path(p).resolve()
        mock_get_sec.return_value = mock_sec_instance

        state.hub = Path("/tmp/mock_hub")
        state.merges_dir = Path("/tmp/mock_merges")

        mock_instance = MockScanner.return_value
        mock_instance.scan.return_value = {"root": "/home", "tree": {}}
        mock_render.return_value = "Mock MD"

        payload = {
            "root_id": "/home",
            "max_depth": 1,
            "max_entries": 100
        }

        from merger.lenskit.service.auth import verify_token
        app.dependency_overrides[verify_token] = lambda: True

        response = client.post("/api/atlas", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["root_scanned"] == str(Path("/home").resolve())

def test_atlas_excludes_proc(tmp_path: Path):
    scanner = AtlasScanner(Path("/"))
    # We must pass strings that don't start with / if we want to test relative path globs matching
    # Because AtlasScanner._is_excluded specifically rejects strings starting with / as absolute paths
    # However, since root is /, walking gives relative paths like "proc", "sys"
    assert scanner._is_excluded("proc") is True
    assert scanner._is_excluded("proc/1/cmdline") is True

def test_atlas_excludes_sys(tmp_path: Path):
    scanner = AtlasScanner(Path("/"))
    assert scanner._is_excluded("sys") is True
    assert scanner._is_excluded("sys/kernel/debug") is True

def test_atlas_override_excludes(tmp_path: Path):
    # Using no_default_excludes flag should prevent default /proc exclusion
    scanner = AtlasScanner(Path("/"), no_default_excludes=True)
    # the exclude patterns built initially won't have /proc etc unless passed in exclude_globs
    assert scanner._is_excluded("proc") is False
    assert scanner._is_excluded("sys") is False
    # But normal defaults like .git should still be there because they are passed or defaulted
    assert scanner._is_excluded(".git") is True
