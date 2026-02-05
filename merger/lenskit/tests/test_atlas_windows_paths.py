from pathlib import Path
from merger.lenskit.adapters.atlas import AtlasScanner

def test_is_excluded_handles_backslashes():
    # Setup scanner with a pattern that expects forward slashes (standard internal rep)
    # Exclude "secret/file.txt"
    scanner = AtlasScanner(Path("."), exclude_globs=["**/secret/file.txt"])

    # Test path with backslash
    # "secret\file.txt" should match "**/secret/file.txt" after normalization
    assert scanner._is_excluded("secret\\file.txt") is True

    # Test path without backslash (control)
    assert scanner._is_excluded("secret/file.txt") is True

    # Test path that shouldn't match
    assert scanner._is_excluded("public\\file.txt") is False

def test_is_excluded_handles_mixed_slashes():
    scanner = AtlasScanner(Path("."), exclude_globs=["**/node_modules/**"])

    # Mixed slashes
    assert scanner._is_excluded("project\\node_modules/package.json") is True
