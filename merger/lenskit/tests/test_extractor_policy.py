import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import os
import sys

# Add the project root to sys.path if needed, although usually pytest handles it.
# We assume the test runner sets up PYTHONPATH correctly.

from merger.lenskit.core.extractor import _compute_sha256_with_size

def test_compute_sha256_success(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello", encoding="utf-8")

    sha, size, error = _compute_sha256_with_size(f)

    # echo -n "hello" | sha256sum
    # 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
    assert sha == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert size == 5
    assert error is None

def test_compute_sha256_missing(tmp_path):
    f = tmp_path / "missing.txt"

    sha, size, error = _compute_sha256_with_size(f)

    assert sha is None
    assert size == 0
    assert error == "missing"

def test_compute_sha256_permission(tmp_path):
    f = tmp_path / "locked.txt"
    f.write_text("secret", encoding="utf-8")

    # Mock open to raise PermissionError
    # We patch pathlib.Path.open. Note: depending on OS, Path might be PosixPath or WindowsPath
    # but patching Path usually works if inheritance is correct.

    with patch("pathlib.Path.open", side_effect=PermissionError("Permission denied")):
        sha, size, error = _compute_sha256_with_size(f)

    assert sha is None
    assert size == 0
    assert error == "permission"

def test_compute_sha256_io_error(tmp_path):
    f = tmp_path / "broken.txt"
    f.write_text("broken", encoding="utf-8")

    with patch("pathlib.Path.open", side_effect=OSError("IO Error")):
        sha, size, error = _compute_sha256_with_size(f)

    assert sha is None
    assert size == 0
    assert error == "io_error"

def test_compute_sha256_directory(tmp_path):
    d = tmp_path / "subdir"
    d.mkdir()

    # Opening a directory usually raises IsADirectoryError (subclass of OSError)
    sha, size, error = _compute_sha256_with_size(d)

    assert sha is None
    assert size == 0
    assert error == "io_error"
