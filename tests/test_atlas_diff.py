import json
from pathlib import Path
from merger.lenskit.atlas.diff import _compare_file_sets, _load_inventory_index, compute_snapshot_comparison
from merger.lenskit.atlas.paths import resolve_artifact_ref

def test_compare_file_sets_empty():
    from_files = {}
    to_files = {}
    new, removed, changed = _compare_file_sets(from_files, to_files)
    assert new == []
    assert removed == []
    assert changed == []

def test_compare_file_sets_identical():
    files = {
        "file1.txt": {"size_bytes": 100, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False},
        "dir/file2.txt": {"size_bytes": 200, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False}
    }
    new, removed, changed = _compare_file_sets(files, files)
    assert new == []
    assert removed == []
    assert changed == []

def test_compare_file_sets_added_removed():
    from_files = {
        "removed.txt": {"size_bytes": 100, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False},
        "stay.txt": {"size_bytes": 50, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False}
    }
    to_files = {
        "new.txt": {"size_bytes": 150, "mtime": "2023-01-02T00:00:00Z", "is_symlink": False},
        "stay.txt": {"size_bytes": 50, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False}
    }
    new, removed, changed = _compare_file_sets(from_files, to_files)
    assert new == ["new.txt"]
    assert removed == ["removed.txt"]
    assert changed == []

def test_compare_file_sets_changed():
    from_files = {
        "size_change.txt": {"size_bytes": 100, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False},
        "mtime_change.txt": {"size_bytes": 100, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False},
        "symlink_change.txt": {"size_bytes": 100, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False}
    }
    to_files = {
        "size_change.txt": {"size_bytes": 101, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False},
        "mtime_change.txt": {"size_bytes": 100, "mtime": "2023-01-01T00:00:01Z", "is_symlink": False},
        "symlink_change.txt": {"size_bytes": 100, "mtime": "2023-01-01T00:00:00Z", "is_symlink": True}
    }
    new, removed, changed = _compare_file_sets(from_files, to_files)
    assert new == []
    assert removed == []
    # Verify deterministic sorting of changed_files
    assert changed == ["mtime_change.txt", "size_change.txt", "symlink_change.txt"]

def test_compare_file_sets_sorting():
    """Verify that new, removed, and changed lists are all deterministically sorted."""
    from_files = {
        "r2.txt": {}, "r1.txt": {},
        "c2.txt": {"size_bytes": 10}, "c1.txt": {"size_bytes": 10}
    }
    to_files = {
        "n2.txt": {}, "n1.txt": {},
        "c2.txt": {"size_bytes": 20}, "c1.txt": {"size_bytes": 20}
    }
    new, removed, changed = _compare_file_sets(from_files, to_files)
    assert new == ["n1.txt", "n2.txt"]
    assert removed == ["r1.txt", "r2.txt"]
    assert changed == ["c1.txt", "c2.txt"]

def test_compare_file_sets_missing_fields():
    """
    Verify behavior when comparison fields are missing.
    The implementation uses .get(), so missing fields are treated as None.
    If both items lack the field, it's not a change.
    """
    from_files = {
        "both_missing.txt": {"mtime": "X"},
        "one_missing.txt": {"size_bytes": 100}
    }
    to_files = {
        "both_missing.txt": {"mtime": "X"},
        "one_missing.txt": {}
    }
    new, removed, changed = _compare_file_sets(from_files, to_files)
    assert "both_missing.txt" not in changed
    assert "one_missing.txt" in changed

def test_load_inventory_index_basic(tmp_path):
    inv_path = tmp_path / "inventory.jsonl"
    data = [
        {"rel_path": "file1.txt", "size_bytes": 10},
        {"rel_path": "file2.txt", "size_bytes": 20}
    ]
    with open(inv_path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")

    index = _load_inventory_index(inv_path)
    assert len(index) == 2
    assert index["file1.txt"]["size_bytes"] == 10

def test_load_inventory_index_malformed_and_types(tmp_path):
    """Verify handling of malformed JSON and incorrect top-level types."""
    inv_path = tmp_path / "inventory.jsonl"
    with open(inv_path, "w", encoding="utf-8") as f:
        f.write('{"rel_path": "valid.txt"}\n')
        f.write('malformed json\n')
        f.write('[]\n') # Wrong top-level type (list)
        f.write('123\n') # Wrong top-level type (int)
        f.write('{"missing_rel_path": true}\n')
        f.write('{"rel_path": 123}\n') # rel_path not a string

    index = _load_inventory_index(inv_path)
    assert list(index.keys()) == ["valid.txt"]

def test_load_inventory_index_duplicate_rel_path_last_wins(tmp_path):
    """Verify that for duplicate rel_path entries, the last one in the file wins."""
    inv_path = tmp_path / "inventory.jsonl"
    with open(inv_path, "w", encoding="utf-8") as f:
        f.write('{"rel_path": "dup.txt", "val": 1}\n')
        f.write('{"rel_path": "dup.txt", "val": 2}\n')

    index = _load_inventory_index(inv_path)
    assert len(index) == 1
    assert index["dup.txt"]["val"] == 2

def test_load_inventory_index_whitespace_only_line(tmp_path):
    """Verify that lines containing only whitespace are silently ignored."""
    inv_path = tmp_path / "inventory.jsonl"
    with open(inv_path, "w", encoding="utf-8") as f:
        f.write('{"rel_path": "file1.txt"}\n')
        f.write('   \n')
        f.write('\t\n')
        f.write('{"rel_path": "file2.txt"}\n')

    index = _load_inventory_index(inv_path)
    assert sorted(index.keys()) == ["file1.txt", "file2.txt"]

def test_compute_snapshot_comparison_integration(tmp_path):
    """
    Lean integration test for compute_snapshot_comparison.
    Ensures that _load_inventory_index and _compare_file_sets work together
    via the public entry point.
    """
    atlas_base = tmp_path / "atlas"
    registry_db = atlas_base / "registry" / "atlas.db"
    registry_db.parent.mkdir(parents=True)

    # Mock registry to avoid dependency on real SQLite/AtlasRegistry logic
    class MockRegistry:
        def __init__(self, db_path):
            self.db_path = db_path
        def get_snapshot(self, snap_id):
            if snap_id == "s1":
                return {
                    "machine_id": "m1", "root_id": "r1", "status": "complete",
                    "inventory_ref": "machines/m1/roots/r1/snapshots/s1/inv.jsonl"
                }
            if snap_id == "s2":
                return {
                    "machine_id": "m2", "root_id": "r2", "status": "complete",
                    "inventory_ref": "machines/m2/roots/r2/snapshots/s2/inv.jsonl"
                }
            return None
        def get_root(self, root_id):
            return {"root_id": root_id, "root_value": f"/path/to/{root_id}"}

    registry = MockRegistry(registry_db)

    # Create inventory files in the expected canonical structure
    inv1_path = resolve_artifact_ref(atlas_base, "machines/m1/roots/r1/snapshots/s1/inv.jsonl")
    inv1_path.parent.mkdir(parents=True)
    with open(inv1_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"rel_path": "shared.txt", "size_bytes": 10}) + "\n")
        f.write(json.dumps({"rel_path": "removed.txt", "size_bytes": 10}) + "\n")

    inv2_path = resolve_artifact_ref(atlas_base, "machines/m2/roots/r2/snapshots/s2/inv.jsonl")
    inv2_path.parent.mkdir(parents=True)
    with open(inv2_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"rel_path": "shared.txt", "size_bytes": 20}) + "\n")
        f.write(json.dumps({"rel_path": "new.txt", "size_bytes": 10}) + "\n")

    result = compute_snapshot_comparison(registry, "s1", "s2")

    # Verify result structure and semantic correctness
    assert result["mode"] == "cross-root-comparison"
    assert result["is_cross_root"] is True
    assert result["from_snapshot_id"] == "s1"
    assert result["to_snapshot_id"] == "s2"
    assert result["summary"]["new_count"] == 1
    assert result["summary"]["removed_count"] == 1
    assert result["summary"]["changed_count"] == 1
    assert result["new_files"] == ["new.txt"]
    assert result["removed_files"] == ["removed.txt"]
    assert result["changed_files"] == ["shared.txt"]
