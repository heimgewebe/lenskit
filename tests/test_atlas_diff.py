import json
import pytest
from pathlib import Path
from merger.lenskit.atlas.diff import _compare_file_sets, _load_inventory_index

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
    assert sorted(changed) == ["mtime_change.txt", "size_change.txt", "symlink_change.txt"]

def test_compare_file_sets_sorting():
    from_files = {}
    to_files = {
        "c.txt": {},
        "a.txt": {},
        "b.txt": {}
    }
    new, _, _ = _compare_file_sets(from_files, to_files)
    assert new == ["a.txt", "b.txt", "c.txt"]

def test_load_inventory_index(tmp_path):
    inv_path = tmp_path / "inventory.jsonl"
    data = [
        {"rel_path": "file1.txt", "size_bytes": 10},
        {"rel_path": "file2.txt", "size_bytes": 20},
        "malformed line",
        {"not_rel_path": "oops"},
        {"rel_path": 123}, # invalid type
        "", # empty line
        {"rel_path": "file3.txt", "size_bytes": 30}
    ]
    with open(inv_path, "w", encoding="utf-8") as f:
        for item in data:
            if isinstance(item, str):
                f.write(item + "\n")
            else:
                f.write(json.dumps(item) + "\n")

    index = _load_inventory_index(inv_path)
    assert len(index) == 3
    assert "file1.txt" in index
    assert "file2.txt" in index
    assert "file3.txt" in index
    assert index["file1.txt"]["size_bytes"] == 10
