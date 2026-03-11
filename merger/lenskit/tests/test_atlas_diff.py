import pytest
import sqlite3
import json
from pathlib import Path
from merger.lenskit.atlas.registry import AtlasRegistry
from merger.lenskit.atlas.diff import compute_snapshot_delta

@pytest.fixture
def temp_workspace(tmp_path):
    # Setup mock atlas structure
    registry_db = tmp_path / "atlas" / "registry" / "atlas_registry.sqlite"
    return tmp_path, registry_db

@pytest.fixture
def populated_registry(temp_workspace):
    tmp_path, registry_db = temp_workspace

    with AtlasRegistry(registry_db) as reg:
        reg.register_machine("m1", "host")
        reg.register_root("r1", "m1", "abs_path", "/var/www")

        # Write mock inventory 1
        inv1_path = tmp_path / "inv1.jsonl"
        with open(inv1_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"snapshot_id": "s1", "rel_path": "a.txt", "size_bytes": 100, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False}) + "\n")
            f.write(json.dumps({"snapshot_id": "s1", "rel_path": "b.txt", "size_bytes": 200, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False}) + "\n")

        reg.create_snapshot("s1", "m1", "r1", "hash1", "complete")
        reg.update_snapshot_artifacts("s1", {"inventory": str(inv1_path)})

        # Write mock inventory 2
        inv2_path = tmp_path / "inv2.jsonl"
        with open(inv2_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"snapshot_id": "s2", "rel_path": "a.txt", "size_bytes": 100, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False}) + "\n") # Unchanged
            f.write(json.dumps({"snapshot_id": "s2", "rel_path": "b.txt", "size_bytes": 250, "mtime": "2023-01-02T00:00:00Z", "is_symlink": False}) + "\n") # Changed
            f.write(json.dumps({"snapshot_id": "s2", "rel_path": "c.txt", "size_bytes": 300, "mtime": "2023-01-02T00:00:00Z", "is_symlink": False}) + "\n") # New
            # b is changed, c is new, d is missing (there was no d in s1, actually b is changed and there's no removed).
            # Let's add d to s1 and remove from s2

        # Re-write s1 with d.txt
        with open(inv1_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"snapshot_id": "s1", "rel_path": "d.txt", "size_bytes": 400, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False}) + "\n")

        reg.create_snapshot("s2", "m1", "r1", "hash2", "complete")
        reg.update_snapshot_artifacts("s2", {"inventory": str(inv2_path)})

        yield reg

def test_compute_snapshot_delta(temp_workspace, populated_registry):
    tmp_path, _ = temp_workspace

    # Needs to be run from tmp_path conceptually so Path("atlas") works,
    # but compute_snapshot_delta writes to `Path("atlas")` relative to cwd.
    # We should patch the output directory logic in diff.py or run the test carefully.
    import os
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        delta = compute_snapshot_delta(populated_registry, "s1", "s2")

        assert len(delta["new_files"]) == 1
        assert delta["new_files"][0] == "c.txt"

        assert len(delta["removed_files"]) == 1
        assert delta["removed_files"][0] == "d.txt"

        assert len(delta["changed_files"]) == 1
        assert delta["changed_files"][0] == "b.txt"

        # Check delta in registry
        reg_deltas = populated_registry.list_deltas()
        assert len(reg_deltas) == 1
        assert reg_deltas[0]["delta_id"] == delta["delta_id"]
    finally:
        os.chdir(old_cwd)

def test_compute_delta_errors(populated_registry):
    with pytest.raises(ValueError, match="Snapshot not found"):
        compute_snapshot_delta(populated_registry, "s1", "nonexistent")

    populated_registry.register_root("r2", "m1", "abs_path", "/var/lib")
    populated_registry.create_snapshot("s3", "m1", "r2", "hash3", "complete")

    with pytest.raises(ValueError, match="Snapshots must belong to the same machine and root"):
        compute_snapshot_delta(populated_registry, "s1", "s3")
