import pytest
import hashlib
from pathlib import Path
from merger.lenskit.core.extractor import _compute_sha256_with_size

def test_compute_sha256_with_size_happy_path(tmp_path):
    f = tmp_path / "test.txt"
    content = "hello world ü" # Unicode to test byte length
    f.write_text(content, encoding="utf-8")

    content_bytes = content.encode("utf-8")
    expected_sha = hashlib.sha256(content_bytes).hexdigest()
    sha, size, status = _compute_sha256_with_size(f)

    assert sha == expected_sha
    assert size == len(content_bytes)
    assert status == "ok"

def test_compute_sha256_with_size_missing(tmp_path):
    path = tmp_path / "does_not_exist_repolens"
    sha, size, status = _compute_sha256_with_size(path)

    assert sha is None
    assert size == 0
    assert status == "missing"

def test_compute_sha256_with_size_permission(tmp_path, monkeypatch):
    f = tmp_path / "perm.txt"
    f.write_text("no access", encoding="utf-8")

    cls = type(f)
    original_stat = cls.stat

    def mock_stat(self, *args, **kwargs):
        # Targeted patch: only fail for our specific test file
        if self.name == "perm.txt":
            raise PermissionError("Access denied")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(cls, "stat", mock_stat)

    sha, size, status = _compute_sha256_with_size(f)

    assert sha is None
    assert size == 0
    assert status == "permission"

def test_compute_sha256_with_size_open_error(tmp_path, monkeypatch):
    f = tmp_path / "open_err.txt"
    content = "can stat but not open"
    f.write_text(content, encoding="utf-8")
    content_bytes = content.encode("utf-8")

    # Targeted patch for open
    cls = type(f)
    original_open = cls.open

    def mock_open(self, *args, **kwargs):
        if self.name == "open_err.txt":
            raise OSError("Read error")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(cls, "open", mock_open)

    sha, size, status = _compute_sha256_with_size(f)

    assert sha is None
    assert size == len(content_bytes) # best-effort size from stat succeeded
    assert status == "io_error"
