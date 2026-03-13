import os
import json
from datetime import datetime, timezone
from pathlib import Path
from merger.lenskit.adapters.atlas import AtlasScanner
from tests.test_atlas_subtree_skip import setup_test_tree, run_scan

def test_incremental_scan_no_double_counting(tmp_path: Path):
    root_dir = setup_test_tree(tmp_path)
    res1, inv1, dirs1 = run_scan(root_dir, "base")

    res2, inv2, dirs2 = run_scan(root_dir, "incr1", incremental_inventory=inv1, incremental_dirs_inventory=dirs1)

    with open(dirs2) as f:
        dirs_data = [json.loads(line) for line in f]

    # We should have exactly 3 dirs: ".", "sub1", "sub1/sub2"
    assert len(dirs_data) == 3

    d_map = {d["rel_path"]: d for d in dirs_data}

    # The root should not have inflated metrics due to double counting skipped "sub1"
    root_entry = d_map["."]
    # Base setup:
    # file1.txt (root)
    # sub1/file2.txt
    # sub1/sub2/file3.txt
    # Total files: 3
    assert root_entry["subtree_file_count"] == 3
    # Total dirs (excluding root): 2 ("sub1", "sub1/sub2")
    assert root_entry["subtree_dir_count"] == 2
