import os
import json
from datetime import datetime, timezone
from pathlib import Path
from merger.lenskit.adapters.atlas import AtlasScanner

def test_incremental_scan_reuses_unchanged_files(tmp_path: Path):
    # Setup test directory
    root_dir = tmp_path / "test_root"
    root_dir.mkdir()

    file1 = root_dir / "file1.txt"
    file1.write_text("Hello World!")

    file2 = root_dir / "file2.txt"
    file2.write_text("Unchanged content")

    inventory_file1 = tmp_path / "inventory1.jsonl"

    # Run baseline scan
    scanner1 = AtlasScanner(
        root=root_dir,
        snapshot_id="snap1",
        enable_content_stats=True
    )
    result1 = scanner1.scan(inventory_file=inventory_file1)
    stats1 = result1["stats"]

    assert stats1["incremental"]["reused_files_count"] == 0
    assert stats1["total_files"] == 2

    # Modify one file, leave the other
    file1.write_text("Hello Incremental World!")

    # Explicitly set a newer mtime to ensure the heuristic correctly catches it
    old_mtime = file1.stat().st_mtime
    os.utime(file1, (old_mtime + 10.0, old_mtime + 10.0))

    new_mtime = file1.stat().st_mtime
    assert new_mtime > old_mtime, "mtime must be strictly newer for heuristic test"

    # Add a new file
    file3 = root_dir / "file3.txt"
    file3.write_text("New file")

    # Run incremental scan
    inventory_file2 = tmp_path / "inventory2.jsonl"
    scanner2 = AtlasScanner(
        root=root_dir,
        snapshot_id="snap2",
        enable_content_stats=True,
        incremental_inventory=inventory_file1
    )
    result2 = scanner2.scan(inventory_file=inventory_file2)
    stats2 = result2["stats"]

    assert stats2["total_files"] == 3

    # file2 should be reused
    assert stats2["incremental"]["reused_files_count"] == 1

    # file1 was modified, file3 is new -> so 2 files analysed, 1 skipped.
    assert stats2["incremental"]["skipped_analysis_count"] == 1

    # Verify the new inventory file
    inv_data = {}
    with inventory_file2.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            item = json.loads(line)
            inv_data[item["rel_path"]] = item

    assert "file1.txt" in inv_data
    assert "file2.txt" in inv_data
    assert "file3.txt" in inv_data

    # Ensure inode and device are captured
    assert "inode" in inv_data["file1.txt"]
    assert "device" in inv_data["file1.txt"]

def test_incremental_scan_dict_input(tmp_path: Path):
    root_dir = tmp_path / "test_root_dict"
    root_dir.mkdir()

    file1 = root_dir / "dict_file.txt"
    file1.write_text("Some dict content")

    # Manually construct fake prior inventory dict
    stat = file1.stat()
    mtime_iso = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace('+00:00', 'Z')
    fake_inv = {
        "dict_file.txt": {
            "rel_path": "dict_file.txt",
            "size_bytes": stat.st_size,
            "mtime": mtime_iso,
            "is_text": True
        }
    }

    inventory_file = tmp_path / "inventory_dict.jsonl"
    scanner = AtlasScanner(
        root=root_dir,
        snapshot_id="snap_dict",
        enable_content_stats=True,
        incremental_inventory=fake_inv
    )
    result = scanner.scan(inventory_file=inventory_file)

    # The file exactly matches our fake dictionary entry
    assert result["stats"]["incremental"]["reused_files_count"] == 1

def test_incremental_scan_handles_malformed_jsonl(tmp_path: Path):
    root_dir = tmp_path / "test_root_malformed"
    root_dir.mkdir()

    # Create the valid file we expect to be reused
    file_valid = root_dir / "valid_file.txt"
    file_valid.write_text("Valid content")

    # Get current stats to spoof the JSONL entry
    stat = file_valid.stat()
    mtime_iso = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace('+00:00', 'Z')

    # Create a malformed incremental_inventory.jsonl
    inventory_file = tmp_path / "malformed_inventory.jsonl"
    with inventory_file.open("w", encoding="utf-8") as f:
        # Line 1: Completely broken JSON
        f.write("{ broken json line \n")

        # Line 2: Valid JSON, missing rel_path
        f.write('{"name": "missing_rel_path.txt", "size_bytes": 100}\n')

        # Line 3: Valid JSON with rel_path (the one we want reused)
        valid_entry = {
            "rel_path": "valid_file.txt",
            "size_bytes": stat.st_size,
            "mtime": mtime_iso,
            "is_text": True
        }
        f.write(json.dumps(valid_entry) + "\n")

        # Line 4: Wrong type for rel_path
        f.write('{"rel_path": 123, "size_bytes": 100}\n')

    # Run the scanner
    out_inventory_file = tmp_path / "out_inventory.jsonl"
    scanner = AtlasScanner(
        root=root_dir,
        snapshot_id="snap_malformed",
        enable_content_stats=True,
        incremental_inventory=inventory_file
    )

    result = scanner.scan(inventory_file=out_inventory_file)
    stats = result["stats"]

    # The scanner should not have crashed.
    # It should have successfully parsed the valid entry and reused the file.
    assert stats["total_files"] == 1
    assert stats["incremental"]["reused_files_count"] == 1

    # Verify the internal dictionary state of the scanner
    assert "valid_file.txt" in scanner.incremental_inventory
    assert len(scanner.incremental_inventory) == 1

def test_incremental_scan_config_hash_invalidation(tmp_path: Path):
    root_dir = tmp_path / "test_root_config"
    root_dir.mkdir()

    file1 = root_dir / "config_file.txt"
    file1.write_text("Hello Config Hash!")

    inventory_file1 = tmp_path / "inventory_cfg1.jsonl"

    # Scan 1 with config_hash_A
    scanner1 = AtlasScanner(
        root=root_dir,
        snapshot_id="snap1",
        enable_content_stats=True,
        current_scan_config_hash="hash_A"
    )
    res1 = scanner1.scan(inventory_file=inventory_file1)

    assert res1["stats"]["total_files"] == 1

    # Read the inventory to verify `is_text` is present
    with inventory_file1.open("r", encoding="utf-8") as f:
        inv1_data = json.loads(f.read().strip())
    assert inv1_data["is_text"] is True

    inventory_file2 = tmp_path / "inventory_cfg2.jsonl"

    # Scan 2 with config_hash_B
    scanner2 = AtlasScanner(
        root=root_dir,
        snapshot_id="snap2",
        enable_content_stats=True,
        incremental_inventory=inventory_file1,
        previous_scan_config_hash="hash_A",
        current_scan_config_hash="hash_B"
    )
    res2 = scanner2.scan(inventory_file=inventory_file2)
    stats2 = res2["stats"]

    # Because config hash changed, `is_text` cache must be invalidated.
    # Therefore skipped_analysis_count should be 0 despite file being reused.
    assert stats2["incremental"]["reused_files_count"] == 1
    assert stats2["incremental"]["skipped_analysis_count"] == 0

def test_incremental_scan_quick_hash_reuse(tmp_path: Path):
    root_dir = tmp_path / "test_root_quick_hash"
    root_dir.mkdir()

    file1 = root_dir / "hash_file.txt"
    file1.write_text("Hello Quick Hash!")

    inventory_file1 = tmp_path / "inventory_hash1.jsonl"

    # Scan 1 to establish baseline and quick_hash
    scanner1 = AtlasScanner(
        root=root_dir,
        snapshot_id="snap1",
        enable_content_stats=True
    )
    scanner1.scan(inventory_file=inventory_file1)

    with inventory_file1.open("r", encoding="utf-8") as f:
        inv1_data = json.loads(f.read().strip())

    assert "quick_hash" in inv1_data

    # Touch the file to bump mtime, keeping size and content identical
    old_mtime = file1.stat().st_mtime
    new_mtime = old_mtime + 10.0
    os.utime(file1, (new_mtime, new_mtime))

    assert file1.stat().st_mtime > old_mtime

    inventory_file2 = tmp_path / "inventory_hash2.jsonl"

    # Scan 2: Should use quick_hash because mtime changed but size matched
    scanner2 = AtlasScanner(
        root=root_dir,
        snapshot_id="snap2",
        enable_content_stats=True,
        incremental_inventory=inventory_file1
    )
    res2 = scanner2.scan(inventory_file=inventory_file2)
    stats2 = res2["stats"]

    # It should correctly identify it as reused and skip analysis
    assert stats2["incremental"]["reused_files_count"] == 1
    assert stats2["incremental"]["skipped_analysis_count"] == 1

    with inventory_file2.open("r", encoding="utf-8") as f:
        inv2_data = json.loads(f.read().strip())

    # Check that quick_hash persists and matches
    assert "quick_hash" in inv2_data
    assert inv1_data["quick_hash"] == inv2_data["quick_hash"]

def test_incremental_scan_directory_aggregates_rollup(tmp_path: Path):
    root_dir = tmp_path / "test_root_rollup"
    root_dir.mkdir()

    # Create structure:
    # root/
    #   file_a.txt (size 10)
    #   child_dir/
    #     file_b.txt (size 20)
    #     grandchild_dir/
    #       file_c.txt (size 30)

    file_a = root_dir / "file_a.txt"
    file_a.write_bytes(b"0123456789")

    child_dir = root_dir / "child_dir"
    child_dir.mkdir()
    file_b = child_dir / "file_b.txt"
    file_b.write_bytes(b"01234567890123456789")

    grandchild_dir = child_dir / "grandchild_dir"
    grandchild_dir.mkdir()
    file_c = grandchild_dir / "file_c.txt"
    file_c.write_bytes(b"012345678901234567890123456789")

    # Give file_c an explicitly newer mtime than the rest to verify propagation
    base_mtime = file_a.stat().st_mtime
    os.utime(file_c, (base_mtime + 100.0, base_mtime + 100.0))
    expected_max_mtime = datetime.fromtimestamp(file_c.stat().st_mtime, timezone.utc).isoformat().replace('+00:00', 'Z')

    dirs_file = tmp_path / "dirs.jsonl"
    scanner = AtlasScanner(
        root=root_dir,
        snapshot_id="snap_rollup"
    )
    scanner.scan(dirs_inventory_file=dirs_file)

    dirs_data = {}
    with dirs_file.open("r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            dirs_data[item["rel_path"]] = item

    # Verify Grandchild
    gc = dirs_data["child_dir/grandchild_dir"]
    assert gc["n_files"] == 1
    assert gc["subtree_file_count"] == 1
    assert gc["subtree_dir_count"] == 0
    assert gc["subtree_total_bytes"] == 30
    assert gc["max_descendant_mtime"] == expected_max_mtime

    # Verify Child
    cd = dirs_data["child_dir"]
    assert cd["n_files"] == 1
    assert cd["n_dirs"] == 1
    assert cd["subtree_file_count"] == 2
    assert cd["subtree_dir_count"] == 1
    assert cd["subtree_total_bytes"] == 50
    assert cd["max_descendant_mtime"] == expected_max_mtime

    # Verify Root
    rd = dirs_data["."]
    assert rd["n_files"] == 1
    assert rd["n_dirs"] == 1
    assert rd["subtree_file_count"] == 3
    assert rd["subtree_dir_count"] == 2
    assert rd["subtree_total_bytes"] == 60
    assert rd["max_descendant_mtime"] == expected_max_mtime
