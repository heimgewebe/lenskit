import pytest
import json
import os
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
            f.write(json.dumps({"snapshot_id": "s2", "rel_path": "a.txt", "size_bytes": 100, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False}) + "\n")
            f.write(json.dumps({"snapshot_id": "s2", "rel_path": "b.txt", "size_bytes": 250, "mtime": "2023-01-02T00:00:00Z", "is_symlink": False}) + "\n")
            f.write(json.dumps({"snapshot_id": "s2", "rel_path": "c.txt", "size_bytes": 300, "mtime": "2023-01-02T00:00:00Z", "is_symlink": False}) + "\n")

        # Re-write s1 with d.txt to test removals
        with open(inv1_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"snapshot_id": "s1", "rel_path": "d.txt", "size_bytes": 400, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False}) + "\n")

        reg.create_snapshot("s2", "m1", "r1", "hash2", "complete")
        reg.update_snapshot_artifacts("s2", {"inventory": str(inv2_path)})

        yield reg

def test_compute_snapshot_delta(temp_workspace, populated_registry):
    tmp_path, _ = temp_workspace

    # Run test from tmp_path so the registry artifact paths resolve correctly
    # based on the current CWD convention for Atlas outputs.
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

    populated_registry.create_snapshot("s_partial", "m1", "r1", "hashx", "running")
    with pytest.raises(ValueError, match="status='complete'"):
        compute_snapshot_delta(populated_registry, "s1", "s_partial")

    populated_registry.register_root("r2", "m1", "abs_path", "/var/lib")
    populated_registry.create_snapshot("s3", "m1", "r2", "hash3", "complete")

    with pytest.raises(ValueError, match="Snapshots must belong to the same machine and root"):
        compute_snapshot_delta(populated_registry, "s1", "s3")



def test_cross_machine_delta(temp_workspace, populated_registry):
    tmp_path, _ = temp_workspace

    populated_registry.register_machine("m2", "otherhost")
    populated_registry.register_root("r2", "m2", "abs_path", "/var/backup")

    inv3_path = tmp_path / "inv3.jsonl"
    with open(inv3_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"snapshot_id": "s3", "rel_path": "a.txt", "size_bytes": 100, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False}) + "\n")
        f.write(json.dumps({"snapshot_id": "s3", "rel_path": "new.txt", "size_bytes": 50, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False}) + "\n")

    populated_registry.create_snapshot("s3", "m2", "r2", "hash3", "complete")
    populated_registry.update_snapshot_artifacts("s3", {"inventory": str(inv3_path)})

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        from merger.lenskit.atlas.diff import compute_snapshot_comparison
        delta = compute_snapshot_comparison(populated_registry, "s1", "s3")

        assert delta["mode"] == "cross-root-comparison"
        assert delta["is_cross_root"] is True
        assert delta["from_machine_id"] == "m1"
        assert delta["to_machine_id"] == "m2"
        assert delta["from_root_id"] == "r1"
        assert delta["to_root_id"] == "r2"
        assert delta["summary"]["new_count"] == 1
        assert delta["new_files"][0] == "new.txt"
        assert delta["summary"]["removed_count"] == 2 # b.txt, d.txt
        assert delta["summary"]["changed_count"] == 0 # a.txt is identical
    finally:
        os.chdir(old_cwd)

def test_resolve_snapshot_ref(populated_registry):
    from merger.lenskit.cli.cmd_atlas import _resolve_snapshot_ref
    import time

    # Normal ref
    assert _resolve_snapshot_ref("s1", populated_registry) == "s1"

    # machine:root path finding newest
    # Right now r1 has s1 and s2. Both created at roughly the same time.
    # Let's manually set s1 created_at early and s2 later in the DB to test the sort.
    with populated_registry.conn:
        populated_registry.conn.execute("UPDATE snapshots SET created_at = '2023-01-01T00:00:00Z' WHERE snapshot_id = 's1'")
        populated_registry.conn.execute("UPDATE snapshots SET created_at = '2023-01-02T00:00:00Z' WHERE snapshot_id = 's2'")

    resolved_id = _resolve_snapshot_ref("m1:/var/www", populated_registry)
    assert resolved_id == "s2" # The newer one

    # Not found paths
    with pytest.raises(ValueError, match="No root found"):
        _resolve_snapshot_ref("m1:/nowhere", populated_registry)
