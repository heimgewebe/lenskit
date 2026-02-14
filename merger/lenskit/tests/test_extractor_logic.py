import pytest
import hashlib
from pathlib import Path
from merger.lenskit.core.extractor import _compute_sha256_with_size

def test_compute_sha256_with_size_happy_path(tmp_path):
    f = tmp_path / "test.txt"
    content = "hello world"
    f.write_text(content, encoding="utf-8")

    expected_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    sha, size, status = _compute_sha256_with_size(f)

    assert sha == expected_sha
    assert size == len(content)
    assert status == "ok"

def test_compute_sha256_with_size_missing():
    path = Path("/tmp/non_existent_file_repolens")
    sha, size, status = _compute_sha256_with_size(path)

    assert sha is None
    assert size == 0
    assert status == "missing"

def test_compute_sha256_with_size_permission(tmp_path, monkeypatch):
    f = tmp_path / "perm.txt"
    f.write_text("no access", encoding="utf-8")

    def mock_stat(*args, **kwargs):
        raise PermissionError("Access denied")

    monkeypatch.setattr(Path, "stat", mock_stat)

    sha, size, status = _compute_sha256_with_size(f)

    assert sha is None
    assert size == 0
    assert status == "permission"

def test_compute_sha256_with_size_open_error(tmp_path, monkeypatch):
    f = tmp_path / "open_err.txt"
    content = "can stat but not open"
    f.write_text(content, encoding="utf-8")

    # We want stat to succeed but open to fail
    original_stat = Path.stat
    def mock_stat(self, *args, **kwargs):
        if self.name == "open_err.txt":
            return original_stat(self, *args, **kwargs)
        return original_stat(self, *args, **kwargs)

    def mock_open(self, *args, **kwargs):
        if "open_err.txt" in str(self):
            raise OSError("Read error")
        return open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", mock_stat)
    # Using a different way to patch open since Path.open is often used
    monkeypatch.setattr("pathlib.Path.open", mock_open)

    sha, size, status = _compute_sha256_with_size(f)

    assert sha is None
    assert size == len(content) # best-effort size from stat
    assert status == "io_error"
