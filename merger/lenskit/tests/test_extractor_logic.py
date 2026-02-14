import json
import pytest
from pathlib import Path
from merger.lenskit.core import extractor
from merger.lenskit.core.extractor import _compute_sha256_with_size, generate_review_bundle

def test_compute_sha256_with_size_happy_path(tmp_path):
    """
    Verifies that _compute_sha256_with_size correctly computes hash and size
    for a normal file.
    """
    test_file = tmp_path / "test.txt"
    content = b"abc"
    test_file.write_bytes(content)

    # Expected SHA256 for "abc"
    expected_sha = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    sha, size, err_code = _compute_sha256_with_size(test_file)

    assert sha == expected_sha
    assert size == len(content)
    assert err_code is None

def test_compute_sha256_with_size_oserror_preserves_size(monkeypatch):
    """
    Verifies that if hashing fails with an OSError (e.g. PermissionError),
    the file size is still retrieved via best-effort stat().
    """
    test_path = Path("fake_file_for_test.txt")

    def mock_open(self, *args, **kwargs):
        raise PermissionError("Mocked Permission Error")

    class MockStat:
        def __init__(self):
            self.st_size = 9999

    def mock_stat(self):
        return MockStat()

    # Patch the concrete class of the instance (e.g. PosixPath) instead of Path factory
    cls = type(test_path)
    monkeypatch.setattr(cls, "open", mock_open, raising=True)
    monkeypatch.setattr(cls, "stat", mock_stat, raising=True)

    sha, size, err_code = _compute_sha256_with_size(test_path)

    assert sha is None
    assert size == 9999
    assert err_code == "permission"

def test_compute_sha256_with_size_full_failure(monkeypatch):
    """
    Verifies that if both hashing and stat() fail, it returns (None, 0).
    """
    test_path = Path("missing_file_for_test.txt")

    def mock_fail(self, *args, **kwargs):
        raise FileNotFoundError("File not found")

    cls = type(test_path)
    monkeypatch.setattr(cls, "open", mock_fail, raising=True)
    monkeypatch.setattr(cls, "stat", mock_fail, raising=True)

    sha, size, err_code = _compute_sha256_with_size(test_path)

    assert sha is None
    assert size == 0
    assert err_code == "missing"

def test_compute_sha256_with_size_generic_oserror(monkeypatch):
    """
    Verifies that generic OSErrors are classified as 'io_error'.
    """
    test_path = Path("generic_error.txt")

    def mock_fail(self, *args, **kwargs):
        raise OSError("Generic I/O Error")

    cls = type(test_path)
    monkeypatch.setattr(cls, "open", mock_fail, raising=True)
    monkeypatch.setattr(cls, "stat", mock_fail, raising=True)

    sha, size, err_code = _compute_sha256_with_size(test_path)

    assert sha is None
    assert err_code == "io_error"


def test_make_entry_logic_with_errors(tmp_path, monkeypatch):
    """
    Verifies that make_entry sets sha256_status based on err_code
    when sha256 is missing.
    """
    hub_dir = tmp_path / "hub"
    hub_dir.mkdir()

    old_repo = tmp_path / "old"
    old_repo.mkdir()

    new_repo = tmp_path / "new"
    new_repo.mkdir()

    # Create a file that will fail
    (new_repo / "secret.txt").write_text("secret")

    # Mock _compute_sha256_with_size to return error for secret.txt
    original_compute = extractor._compute_sha256_with_size

    def mock_compute(path):
        if path.name == "secret.txt":
            # Simulate a permission error
            return None, 999, "permission"
        # For other files (e.g. parts of the bundle), behave normally
        return original_compute(path)

    monkeypatch.setattr(extractor, "_compute_sha256_with_size", mock_compute)

    generate_review_bundle(old_repo, new_repo, "test-repo", hub_dir)

    # Check delta.json
    pr_schau_dir = hub_dir / ".repolens" / "pr-schau" / "test-repo"
    assert pr_schau_dir.exists()

    # Find the timestamp folder
    ts_folders = list(pr_schau_dir.iterdir())
    assert len(ts_folders) == 1
    bundle_dir = ts_folders[0]
    delta_json_path = bundle_dir / "delta.json"

    with open(delta_json_path) as f:
        delta = json.load(f)

    # Find the entry for secret.txt
    entry = next(e for e in delta["files"] if e["path"] == "secret.txt")

    assert entry["sha256_status"] == "permission"
    assert entry["sha256"] is None
    # ensure no sha256_error_class
    assert "sha256_error_class" not in entry
