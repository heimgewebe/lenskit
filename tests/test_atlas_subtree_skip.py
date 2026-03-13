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

def run_scan(root_dir, prefix, current_hash="A", previous_hash="A", **kwargs):
    scanner = AtlasScanner(
        root=root_dir,
        snapshot_id=f"snap_{prefix}",
        enable_content_stats=True,
        current_scan_config_hash=current_hash,
        previous_scan_config_hash=previous_hash,
        **kwargs
    )
    inv = root_dir.parent / f"inv_{prefix}.jsonl"
    dirs = root_dir.parent / f"dirs_{prefix}.jsonl"
    res = scanner.scan(inventory_file=inv, dirs_inventory_file=dirs)
    return res, inv, dirs

def test_incremental_scan_subtree_skip_negative_mtime(tmp_path: Path):
    root_dir = setup_test_tree(tmp_path)
    res1, inv1, dirs1 = run_scan(root_dir, "base")

    old_mtime = (root_dir / "sub1").stat().st_mtime
    time.sleep(0.01) # to ensure mtime diff just in case
    new_mtime = old_mtime + 10.0
    os.utime(root_dir / "sub1", (new_mtime, new_mtime))

    res2, inv2, dirs2 = run_scan(root_dir, "incr1", incremental_inventory=inv1, incremental_dirs_inventory=dirs1)

    # We expect skipped_subtrees_count to be 1 for sub2, but 0 for sub1 since its mtime changed!
    # Ah, the root dir was not skipped, sub1 wasn't skipped, but sub2's mtime didn't change so IT was skipped!
    # Therefore, skipped_subtrees_count SHOULD be 1 (for sub2).
    # This proves it correctly prunes unmodified descendants even if parent is touched!
    assert res2["stats"]["incremental"]["skipped_subtrees_count"] == 1

    # And sub1 should have its reused_files_count incremented because its file didn't change
    assert res2["stats"]["incremental"]["reused_files_count"] >= 1

def test_incremental_scan_subtree_skip_negative_fingerprint(tmp_path: Path):
    root_dir = setup_test_tree(tmp_path)
    res1, inv1, dirs1 = run_scan(root_dir, "base")

    sub1 = root_dir / "sub1"
    (sub1 / "file2.txt").unlink()
    (sub1 / "file4.txt").write_bytes(b"sub4 file")

    with open(dirs1) as f:
        for line in f:
            d = json.loads(line)
            if d["rel_path"] == "sub1":
                orig_mtime_str = d["mtime"]
                break

    from datetime import datetime
    orig_ts = datetime.fromisoformat(orig_mtime_str.replace('Z', '+00:00')).timestamp()
    os.utime(sub1, (orig_ts, orig_ts))

    res2, inv2, dirs2 = run_scan(root_dir, "incr1", incremental_inventory=inv1, incremental_dirs_inventory=dirs1)

    # Sub1 fingerprint changed -> not skipped. Sub2 should be skipped!
    assert res2["stats"]["incremental"]["skipped_subtrees_count"] == 1

def test_incremental_scan_subtree_skip_config_changed(tmp_path: Path):
    root_dir = setup_test_tree(tmp_path)
    res1, inv1, dirs1 = run_scan(root_dir, "base", current_hash="A")
    res2, inv2, dirs2 = run_scan(root_dir, "incr1", current_hash="B", previous_hash="A", incremental_inventory=inv1, incremental_dirs_inventory=dirs1)
    assert res2["stats"]["incremental"]["skipped_subtrees_count"] == 0

def test_incremental_scan_subtree_skip_positive(tmp_path: Path):
    root_dir = setup_test_tree(tmp_path)
    res1, inv1, dirs1 = run_scan(root_dir, "base")
    res2, inv2, dirs2 = run_scan(root_dir, "incr1", incremental_inventory=inv1, incremental_dirs_inventory=dirs1)
    # sub1 will be skipped. Because it is skipped, it prunes sub2.
    # So skipped_subtrees_count should be exactly 1!
    assert res2["stats"]["incremental"]["skipped_subtrees_count"] == 1
