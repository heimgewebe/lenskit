import pytest
from pathlib import Path
from merger.lenskit.adapters.atlas import AtlasScanner
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

def test_atlas_scan_root_allowed(service_client):
    # Use the test client provided by conftest.py
    client = service_client.client

    with patch("merger.lenskit.service.app.get_security_config") as mock_get_sec, \
         patch("merger.lenskit.service.app.AtlasScanner") as MockScanner, \
         patch("merger.lenskit.service.app.render_atlas_md") as mock_render, \
         patch("merger.lenskit.adapters.filesystem.get_security_config") as mock_fs_sec:

        mock_sec_instance = MagicMock()
        mock_sec_instance.validate_path.side_effect = lambda p: Path(p).resolve()
        mock_get_sec.return_value = mock_sec_instance
        mock_fs_sec.return_value = mock_sec_instance

        mock_instance = MockScanner.return_value
        mock_instance.scan.return_value = {"root": "/", "tree": {}}
        mock_render.return_value = "Mock MD"

        payload = {
            "root_id": "/",
            "max_depth": 1,
            "max_entries": 100
        }

        response = client.post("/api/atlas", json=payload, headers=service_client.headers)
        assert response.status_code == 200

        data = response.json()
        assert data["root_scanned"] == str(Path("/").resolve())

def test_atlas_scan_home_allowed(service_client):
    client = service_client.client

    with patch("merger.lenskit.service.app.get_security_config") as mock_get_sec, \
         patch("merger.lenskit.service.app.AtlasScanner") as MockScanner, \
         patch("merger.lenskit.service.app.render_atlas_md") as mock_render:

        mock_sec_instance = MagicMock()
        mock_sec_instance.validate_path.side_effect = lambda p: Path(p).resolve()
        mock_get_sec.return_value = mock_sec_instance

        mock_instance = MockScanner.return_value
        mock_instance.scan.return_value = {"root": "/home", "tree": {}}
        mock_render.return_value = "Mock MD"

        payload = {
            "root_id": "/home",
            "max_depth": 1,
            "max_entries": 100
        }

        response = client.post("/api/atlas", json=payload, headers=service_client.headers)
        assert response.status_code == 200

        data = response.json()
        assert data["root_scanned"] == str(Path("/home").resolve())

def test_atlas_excludes_proc(tmp_path: Path):
    # Setup mock filesystem
    (tmp_path / "proc").mkdir()
    (tmp_path / "proc" / "1").mkdir()
    (tmp_path / "proc" / "1" / "cmdline").write_text("mock")

    (tmp_path / "home").mkdir()
    (tmp_path / "home" / "proc").mkdir()
    (tmp_path / "home" / "proc" / "notes.txt").write_text("notes")

    # Run scan with inventory
    inv_file = tmp_path / "inventory.jsonl"
    scanner = AtlasScanner(tmp_path)
    result = scanner.scan(inventory_file=inv_file)

    # Get relative paths of all files found
    paths = []
    with open(inv_file, "r") as f:
        for line in f:
            import json
            paths.append(json.loads(line)["rel_path"])

    assert not any(p.startswith("proc/") or p == "proc" for p in paths), f"Root /proc was not excluded. Found: {paths}"
    assert any(p == "home/proc/notes.txt" for p in paths), f"Nested /home/proc was improperly excluded. Found: {paths}"

def test_atlas_excludes_sys(tmp_path: Path):
    (tmp_path / "sys").mkdir()
    (tmp_path / "sys" / "kernel").mkdir()
    (tmp_path / "sys" / "kernel" / "debug").write_text("mock")

    inv_file = tmp_path / "inventory.jsonl"
    scanner = AtlasScanner(tmp_path)
    result = scanner.scan(inventory_file=inv_file)

    paths = []
    with open(inv_file, "r") as f:
        import json
        for line in f:
            paths.append(json.loads(line)["rel_path"])

    assert not any(p.startswith("sys/") or p == "sys" for p in paths), f"sys was not excluded. Found: {paths}"

def test_atlas_override_excludes(tmp_path: Path):
    (tmp_path / "proc").mkdir()
    (tmp_path / "proc" / "1").write_text("mock")

    inv_file = tmp_path / "inventory.jsonl"
    scanner = AtlasScanner(tmp_path, no_default_excludes=True)
    result = scanner.scan(inventory_file=inv_file)

    paths = []
    with open(inv_file, "r") as f:
        import json
        for line in f:
            paths.append(json.loads(line)["rel_path"])

    assert any(p == "proc/1" for p in paths), f"proc was excluded despite no_default_excludes=True. Found: {paths}"

def test_atlas_max_file_size_validation():
    with pytest.raises(ValueError, match="max_file_size must be a positive integer or None."):
        AtlasScanner(Path("/"), max_file_size=0)

    with pytest.raises(ValueError, match="max_file_size must be a positive integer or None."):
        AtlasScanner(Path("/"), max_file_size=-5)

def test_atlas_max_file_size_unlimited(tmp_path: Path):
    big_file = tmp_path / "big.bin"
    # Create a real file that is e.g. 2048 bytes
    big_file.write_bytes(b"0" * 2048)

    # 1. With a limit strictly smaller than the file, the big file should be skipped
    scanner = AtlasScanner(tmp_path, max_file_size=1024)
    res = scanner.scan()
    assert scanner.stats["total_files"] == 0

    # 2. With no limit (None), the big file should be included
    scanner_unlimited = AtlasScanner(tmp_path, max_file_size=None)
    res_unlimited = scanner_unlimited.scan()
    assert scanner_unlimited.stats["total_files"] == 1

def test_atlas_exclude_globs_no_mutation(tmp_path: Path):
    my_excludes = ["**/.custom"]
    original_id = id(my_excludes)
    original_len = len(my_excludes)

    scanner = AtlasScanner(tmp_path, exclude_globs=my_excludes, no_default_excludes=False)

    # Check that my_excludes wasn't mutated
    assert len(my_excludes) == original_len
    assert my_excludes == ["**/.custom"]
    assert id(my_excludes) == original_id

    # Check that scanner correctly added defaults internally
    assert len(scanner.exclude_globs) > original_len
    assert "proc/**" in scanner.exclude_globs
