from pathlib import Path
import json
from merger.lenskit.adapters.atlas import AtlasScanner

def test_is_excluded_handles_backslashes():
    # Use simpler pattern to test normalization logic specifically
    # Exclude "secret/file.txt"
    scanner = AtlasScanner(Path("."), exclude_globs=["secret/file.txt"])

    # Test path with backslash - should be normalized to match "secret/file.txt"
    assert scanner._is_excluded("secret\\file.txt") is True

    # Control case
    assert scanner._is_excluded("secret/file.txt") is True

    # Should not match
    assert scanner._is_excluded("public\\file.txt") is False

def test_is_excluded_handles_mixed_slashes_glob():
    # Test normalization with standard glob
    scanner = AtlasScanner(Path("."), exclude_globs=["**/node_modules/**"])

    assert scanner._is_excluded("project\\node_modules/package.json") is True

def test_scan_integration_excludes(tmp_path):
    # Setup temp directory structure
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "ok.txt").touch()

    (tmp_path / "secret").mkdir()
    (tmp_path / "secret" / "hidden.txt").touch()

    # Initialize scanner excluding "secret" folder
    # Using relative path pattern
    scanner = AtlasScanner(tmp_path, exclude_globs=["secret/**"])

    inventory_file = tmp_path / "inventory.jsonl"
    scanner.scan(inventory_file=inventory_file)

    # Read inventory
    paths = []
    with inventory_file.open() as f:
        for line in f:
            entry = json.loads(line)
            paths.append(entry["rel_path"])

    # Verification
    # "public/ok.txt" should be present
    assert "public/ok.txt" in paths
    # "secret/hidden.txt" should be excluded
    assert "secret/hidden.txt" not in paths
