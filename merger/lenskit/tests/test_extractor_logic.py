
import pytest
from pathlib import Path
from merger.lenskit.core.extractor import _compute_sha256_with_size

def test_compute_sha256_with_size_oserror_preserves_size(monkeypatch):
    """
    Verifies that if hashing fails with an OSError (e.g. PermissionError),
    the file size is still retrieved via best-effort stat().
    """
    test_path = Path("fake_file_for_test.txt")

    def mock_open(self, *args, **kwargs):
        raise OSError("Mocked Permission Error")

    class MockStat:
        def __init__(self):
            self.st_size = 9999

    def mock_stat(self):
        return MockStat()

    monkeypatch.setattr(Path, "open", mock_open)
    monkeypatch.setattr(Path, "stat", mock_stat)

    sha, size = _compute_sha256_with_size(test_path)

    assert sha is None
    assert size == 9999

def test_compute_sha256_with_size_full_failure(monkeypatch):
    """
    Verifies that if both hashing and stat() fail, it returns (None, 0).
    """
    test_path = Path("missing_file_for_test.txt")

    def mock_fail(self, *args, **kwargs):
        raise OSError("File not found")

    monkeypatch.setattr(Path, "open", mock_fail)
    monkeypatch.setattr(Path, "stat", mock_fail)

    sha, size = _compute_sha256_with_size(test_path)

    assert sha is None
    assert size == 0
