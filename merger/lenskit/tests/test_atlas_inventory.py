import json
from merger.lenskit.adapters.atlas import AtlasScanner

def test_atlas_inventory_includes_all_titles(tmp_path):
    # Setup: Create folder structure
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "file1.txt").write_text("content", encoding="utf-8")
    # Use a binary file with null byte to ensure detection works
    (tmp_path / "subdir" / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")
    (tmp_path / "root.md").write_text("# Root", encoding="utf-8")

    # .git should be excluded by default
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x", encoding="utf-8")

    inventory_file = tmp_path / "atlas.inventory.jsonl"

    scanner = AtlasScanner(tmp_path, inventory_strict=False)
    scanner.scan(inventory_file=inventory_file)

    assert inventory_file.exists()

    lines = inventory_file.read_text(encoding="utf-8").strip().splitlines()
    items = [json.loads(line) for line in lines]

    paths = {item["rel_path"] for item in items}

    # Check inclusions
    assert "subdir/file1.txt" in paths
    assert "subdir/image.png" in paths
    assert "root.md" in paths

    # Check exclusions
    assert ".git/config" not in paths

    # Check fields
    file1 = next(i for i in items if i["rel_path"] == "subdir/file1.txt")
    assert file1["name"] == "file1.txt"
    assert file1["ext"] == ".txt"
    assert file1["is_text"] is True
    assert "size_bytes" in file1
    assert "mtime" in file1

    img = next(i for i in items if i["rel_path"] == "subdir/image.png")
    assert img["is_text"] is False

def test_atlas_inventory_strict_mode(tmp_path):
    # Test strict mode (minimal excludes)
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.json").write_text("{}", encoding="utf-8")

    inventory_file = tmp_path / "atlas.inventory_strict.jsonl"

    # With inventory_strict=True, node_modules should be included
    # (Default strict excludes are only .git and .venv)
    scanner = AtlasScanner(tmp_path, inventory_strict=True)
    scanner.scan(inventory_file=inventory_file)

    lines = inventory_file.read_text(encoding="utf-8").strip().splitlines()
    items = [json.loads(line) for line in lines]
    paths = {item["rel_path"] for item in items}

    assert "node_modules/pkg.json" in paths

def test_atlas_truncation(tmp_path):
    # Test truncation stats
    for i in range(10):
        (tmp_path / f"file{i}.txt").write_text("x")

    scanner = AtlasScanner(tmp_path, max_entries=5)
    result = scanner.scan()

    assert result["stats"]["truncated"]["hit"] is True
    assert result["stats"]["truncated"]["reason"] == "max_entries"
    # Adjusted assertion to match new behavior:
    # "files_seen" is capped at max_entries when truncation occurs.
    assert result["stats"]["truncated"]["files_seen"] == 5

def test_atlas_dirs_inventory(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a/sub").mkdir()

    dirs_file = tmp_path / "dirs.jsonl"
    scanner = AtlasScanner(tmp_path)
    scanner.scan(dirs_inventory_file=dirs_file)

    assert dirs_file.exists()
    lines = dirs_file.read_text(encoding="utf-8").strip().splitlines()
    items = [json.loads(line) for line in lines]
    paths = {item["rel_path"] for item in items}

    assert "a" in paths
    assert "b" in paths
    assert "a/sub" in paths

def test_exclude_pattern_robustness(tmp_path):
    # Test that excluding "myexclude" correctly excludes "myexclude" folder AND "myexclude/file"
    # even if pattern was just "**/myexclude"

    (tmp_path / "keep").mkdir()
    (tmp_path / "keep" / "ok.txt").write_text("ok")

    (tmp_path / "myexclude").mkdir()
    (tmp_path / "myexclude" / "bad.txt").write_text("bad")

    # Explicit custom exclude
    scanner = AtlasScanner(tmp_path, exclude_globs=["**/myexclude"])

    inventory_file = tmp_path / "inv.jsonl"
    scanner.scan(inventory_file=inventory_file)

    lines = inventory_file.read_text(encoding="utf-8").strip().splitlines()
    items = [json.loads(line) for line in lines]
    paths = {item["rel_path"] for item in items}

    assert "keep/ok.txt" in paths
    assert "myexclude/bad.txt" not in paths

def test_atlas_dirs_inventory_excludes_files(tmp_path):
    (tmp_path / "mixed").mkdir()
    (tmp_path / "mixed" / "ok.txt").write_text("ok")
    (tmp_path / "mixed" / "ignore.me").write_text("ignore")

    dirs_file = tmp_path / "dirs.jsonl"
    scanner = AtlasScanner(tmp_path, exclude_globs=["**/ignore.me"])
    scanner.scan(dirs_inventory_file=dirs_file)

    lines = dirs_file.read_text(encoding="utf-8").strip().splitlines()
    items = [json.loads(line) for line in lines]

    mixed_dir = next(i for i in items if i["rel_path"] == "mixed")
    assert mixed_dir["n_files"] == 1
