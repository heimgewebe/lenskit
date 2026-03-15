import json
from pathlib import Path
from unittest.mock import patch

from merger.lenskit.adapters.atlas import AtlasScanner

def test_detect_mime_type_with_enable_content_stats(tmp_path: Path):
    """
    Test that mime_type is correctly identified and recorded when enable_content_stats is True.
    """
    test_dir = tmp_path / "test_mime"
    test_dir.mkdir()

    # Create various types of files

    # 1. Plain text file with extension
    text_file = test_dir / "text_file.txt"
    text_file.write_text("Hello World!")

    # 2. PDF file with correct magic bytes but no extension
    pdf_file = test_dir / "pdf_no_ext"
    with pdf_file.open("wb") as f:
        f.write(b"%PDF-1.4\n...")

    # 3. Binary file without recognized magic bytes
    bin_file = test_dir / "random.dat"
    with bin_file.open("wb") as f:
        f.write(b"\x00\x01\x02\x03\x04\x05")

    # 4. Unknown text file (no extension, text content)
    unknown_text = test_dir / "unknown_text"
    unknown_text.write_text("This is just some text content.")

    inv_file = tmp_path / "inventory.jsonl"

    scanner = AtlasScanner(
        root=test_dir,
        snapshot_id="test_snap",
        enable_content_stats=True
    )
    scanner.scan(inventory_file=inv_file)

    assert inv_file.exists()

    # Parse inventory
    results = {}
    with inv_file.open("r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            results[entry["name"]] = entry["mime_type"]

    assert results["text_file.txt"] == "text/plain"
    assert results["pdf_no_ext"] == "application/pdf"
    assert results["random.dat"] == "application/octet-stream"
    assert results["unknown_text"] == "text/plain"

def test_no_mime_type_when_content_stats_disabled(tmp_path: Path):
    """
    Test that mime_type is omitted when enable_content_stats is False.
    """
    test_dir = tmp_path / "test_no_mime"
    test_dir.mkdir()

    text_file = test_dir / "file.txt"
    text_file.write_text("Hello")

    inv_file = tmp_path / "inventory.jsonl"

    scanner = AtlasScanner(
        root=test_dir,
        snapshot_id="test_snap",
        enable_content_stats=False
    )
    scanner.scan(inventory_file=inv_file)

    with inv_file.open("r", encoding="utf-8") as f:
        entry = json.loads(f.readline())
        assert "mime_type" not in entry

def test_incremental_mime_reuse(tmp_path: Path):
    """
    Test that mime_type is reused during incremental scans.
    """
    test_dir = tmp_path / "test_incremental"
    test_dir.mkdir()

    text_file = test_dir / "file.txt"
    text_file.write_text("Data")

    inv_file1 = tmp_path / "inventory1.jsonl"
    scanner1 = AtlasScanner(root=test_dir, snapshot_id="snap1", enable_content_stats=True)
    scanner1.scan(inventory_file=inv_file1)

    # Scan again with incremental reuse
    inv_file2 = tmp_path / "inventory2.jsonl"
    scanner2 = AtlasScanner(
        root=test_dir,
        snapshot_id="snap2",
        enable_content_stats=True,
        incremental_inventory=inv_file1,
        previous_scan_config_hash="hash1",
        current_scan_config_hash="hash1"
    )
    scanner2.scan(inventory_file=inv_file2)

    with inv_file2.open("r", encoding="utf-8") as f:
        entry = json.loads(f.readline())
        assert entry["mime_type"] == "text/plain"

    # Assert reuse stats
    assert scanner2.stats["incremental"]["reused_files_count"] == 1

def test_mime_type_not_calculated_when_stats_disabled(tmp_path: Path):
    """
    Test that detect_mime_type is not even called when enable_content_stats=False,
    saving unnecessary computation.
    """
    test_dir = tmp_path / "test_no_calc"
    test_dir.mkdir()
    (test_dir / "file.txt").write_text("Hello")

    scanner = AtlasScanner(
        root=test_dir,
        snapshot_id="test_snap",
        enable_content_stats=False
    )

    with patch("merger.lenskit.adapters.atlas.detect_mime_type") as mock_detect:
        scanner.scan(inventory_file=tmp_path / "inv.jsonl")

    # Assert that the function was never called
    mock_detect.assert_not_called()

def test_no_mime_type_incremental_when_stats_disabled(tmp_path: Path):
    """
    Test that even if incremental inventory has mime_type, it is not emitted if enable_content_stats=False.
    """
    test_dir = tmp_path / "test_incremental_disabled"
    test_dir.mkdir()

    text_file = test_dir / "file.txt"
    text_file.write_text("Data")

    # Force a previous inventory that HAS content stats
    inv_file1 = tmp_path / "inventory1.jsonl"
    scanner1 = AtlasScanner(root=test_dir, snapshot_id="snap1", enable_content_stats=True)
    scanner1.scan(inventory_file=inv_file1)

    with inv_file1.open("r", encoding="utf-8") as f:
        entry = json.loads(f.readline())
        assert "mime_type" in entry

    # Scan again with incremental reuse, but content stats DISABLED
    inv_file2 = tmp_path / "inventory2.jsonl"
    scanner2 = AtlasScanner(
        root=test_dir,
        snapshot_id="snap2",
        enable_content_stats=False,
        incremental_inventory=inv_file1,
        previous_scan_config_hash="hash1",
        current_scan_config_hash="hash1"
    )
    scanner2.scan(inventory_file=inv_file2)

    with inv_file2.open("r", encoding="utf-8") as f:
        entry = json.loads(f.readline())
        assert "mime_type" not in entry

    # The file itself should be counted as reused in terms of base file metadata
    assert scanner2.stats["incremental"]["reused_files_count"] == 1
