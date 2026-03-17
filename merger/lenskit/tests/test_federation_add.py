import json
from pathlib import Path
import pytest
from merger.lenskit.core.federation import init_federation, add_bundle

def test_add_bundle_success(tmp_path: Path):
    index_path = tmp_path / "fed.json"
    init_federation("test-add-fed", index_path)

    bundle_path = tmp_path / "my_bundle"
    bundle_path.mkdir()

    updated_data = add_bundle(index_path, "repo-1", str(bundle_path))

    assert "bundles" in updated_data
    assert len(updated_data["bundles"]) == 1
    assert updated_data["bundles"][0]["repo_id"] == "repo-1"
    assert "my_bundle" in updated_data["bundles"][0]["bundle_path"]

    # Verify write
    with index_path.open() as f:
        read_data = json.load(f)
        assert read_data["bundles"][0]["repo_id"] == "repo-1"
        assert read_data["updated_at"] >= read_data["created_at"]

def test_add_bundle_duplicate_repo_id(tmp_path: Path):
    index_path = tmp_path / "fed.json"
    init_federation("test-dup-fed", index_path)

    b1_path = str(tmp_path / "b1")
    b2_path = str(tmp_path / "b2")

    add_bundle(index_path, "repo-1", b1_path)

    with pytest.raises(ValueError) as exc_info:
        add_bundle(index_path, "repo-1", b2_path)

    assert "already exists in federation index" in str(exc_info.value)

def test_add_bundle_index_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        add_bundle(tmp_path / "nonexistent.json", "repo-1", str(tmp_path / "b1"))
