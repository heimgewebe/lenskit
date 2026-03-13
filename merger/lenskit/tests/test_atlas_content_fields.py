import json
from pathlib import Path
from merger.lenskit.adapters.atlas import AtlasScanner

def test_atlas_mode_dependent_content_fields(tmp_path: Path):
    """
    Test F - content fields (mime_type, encoding, line_count) are populated
    and dependent on the scan mode (enable_content_stats).
    """
    (tmp_path / "content").mkdir()

    # 1. Text file
    txt_file = tmp_path / "content" / "hello.txt"
    txt_file.write_text("hello\nworld\n", encoding="utf-8")

    # 2. Binary file (png)
    png_file = tmp_path / "content" / "image.png"
    png_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")

    # Scan 1: without content_stats
    inv_no_content = tmp_path / "inv_no_content.jsonl"
    scanner1 = AtlasScanner(tmp_path, snapshot_id="snap1", enable_content_stats=False)
    scanner1.scan(inventory_file=inv_no_content)

    with open(inv_no_content, "r", encoding="utf-8") as f:
        lines1 = [json.loads(line) for line in f]

    txt1 = next(item for item in lines1 if item["name"] == "hello.txt")
    png1 = next(item for item in lines1 if item["name"] == "image.png")

    # mime_type is always generated (cheap, extension based)
    assert "mime_type" in txt1
    assert txt1["mime_type"] == "text/plain"
    assert "mime_type" in png1
    assert png1["mime_type"] == "image/png"

    # is_text, encoding and line_count should NOT be present (mode dependent)
    assert "is_text" not in txt1
    assert "encoding" not in txt1
    assert "line_count" not in txt1
    assert "is_text" not in png1

    # Scan 2: with content_stats
    inv_with_content = tmp_path / "inv_with_content.jsonl"
    scanner2 = AtlasScanner(tmp_path, snapshot_id="snap2", enable_content_stats=True)
    scanner2.scan(inventory_file=inv_with_content)

    with open(inv_with_content, "r", encoding="utf-8") as f:
        lines2 = [json.loads(line) for line in f]

    txt2 = next(item for item in lines2 if item["name"] == "hello.txt")
    png2 = next(item for item in lines2 if item["name"] == "image.png")

    # Text file should have encoding and line_count
    assert "mime_type" in txt2
    assert "is_text" in txt2
    assert txt2["is_text"] is True
    assert "encoding" in txt2
    assert txt2["encoding"] == "utf-8"
    assert "line_count" in txt2
    assert txt2["line_count"] == 2

    # Binary file should NOT have encoding and line_count, but should have is_text=False
    assert "mime_type" in png2
    assert "is_text" in png2
    assert png2["is_text"] is False
    assert "encoding" not in png2
    assert "line_count" not in png2
