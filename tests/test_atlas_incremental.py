import os
import json
import time
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
    current_mtime = file1.stat().st_mtime
    os.utime(file1, (current_mtime + 10.0, current_mtime + 10.0))

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
