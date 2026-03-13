import os
import json
from datetime import datetime, timezone
from pathlib import Path
from merger.lenskit.adapters.atlas import AtlasScanner
import time

def setup_test_tree(tmp_path: Path):
    root_dir = tmp_path / "test_root"
    root_dir.mkdir()

    (root_dir / "file1.txt").write_bytes(b"root file")

    sub1 = root_dir / "sub1"
    sub1.mkdir()
    (sub1 / "file2.txt").write_bytes(b"sub1 file")

    sub2 = sub1 / "sub2"
    sub2.mkdir()
    (sub2 / "file3.txt").write_bytes(b"sub2 file")

    return root_dir

def test_atlas_dir_rollup(tmp_path: Path):
    root_dir = setup_test_tree(tmp_path)
    scanner = AtlasScanner(root=root_dir, snapshot_id="snap_1", enable_content_stats=True)

    inv = root_dir.parent / "inv.jsonl"
    dirs = root_dir.parent / "dirs.jsonl"

    scanner.scan(inventory_file=inv, dirs_inventory_file=dirs)

    with open(dirs) as f:
        dirs_data = [json.loads(line) for line in f]

    d_map = {d["rel_path"]: d for d in dirs_data}

    # Verify Rollups
    assert d_map["sub1/sub2"]["subtree_file_count"] == 1
    assert d_map["sub1/sub2"]["subtree_dir_count"] == 0

    assert d_map["sub1"]["subtree_file_count"] == 2 # sub1/file2 + sub1/sub2/file3
    assert d_map["sub1"]["subtree_dir_count"] == 1  # sub1/sub2

    assert d_map["."]["subtree_file_count"] == 3 # root + sub1 + sub1/sub2
    assert d_map["."]["subtree_dir_count"] == 2 # sub1 + sub1/sub2
