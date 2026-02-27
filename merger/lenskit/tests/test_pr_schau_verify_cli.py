"""
Tests for the PR-Schau Verify CLI tool (merger.lenskit.cli.pr_schau_verify).
"""

import json
import pytest
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

from merger.lenskit.cli.pr_schau_verify import verify_basic, verify_full, _fail, _pass

# Mocking sys.exit and print to capture output/failures
@pytest.fixture
def mock_fail():
    with patch("merger.lenskit.cli.pr_schau_verify._fail") as m:
        m.side_effect = Exception("FAIL")
        yield m

@pytest.fixture
def mock_pass():
    with patch("merger.lenskit.cli.pr_schau_verify._pass") as m:
        yield m

def test_verify_basic_missing_parts(tmp_path, mock_fail, mock_pass):
    bundle_path = tmp_path / "bundle.json"
    data = {"completeness": {"parts": []}}
    schema = {} # Mock schema

    with pytest.raises(Exception, match="FAIL"):
        verify_basic(bundle_path, data, schema)

    mock_fail.assert_called_with("No parts listed (completeness.parts is empty or missing).")

def test_verify_basic_missing_file(tmp_path, mock_fail, mock_pass):
    bundle_path = tmp_path / "bundle.json"
    data = {"completeness": {"parts": ["missing.md"]}}
    schema = {}

    with pytest.raises(Exception, match="FAIL"):
        verify_basic(bundle_path, data, schema)

    mock_fail.assert_called_with("Missing part file: missing.md")

def test_verify_basic_success(tmp_path, mock_fail, mock_pass):
    bundle_path = tmp_path / "bundle.json"
    (tmp_path / "exists.md").touch()
    data = {"completeness": {"parts": ["exists.md"]}}
    schema = {}

    verify_basic(bundle_path, data, schema)
    mock_pass.assert_any_call("All 1 parts exist on disk")

def test_verify_full_integrity_primary(tmp_path, mock_fail, mock_pass):
    bundle_path = tmp_path / "bundle.json"
    data = {
        "completeness": {
            "parts": ["a.md"],
            "primary_part": "b.md"
        },
        "artifacts": []
    }

    with pytest.raises(Exception, match="FAIL"):
        verify_full(bundle_path, data)

    mock_fail.assert_called_with("primary_part 'b.md' is not listed in parts ['a.md']")

def compute_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def test_verify_full_expected_bytes_zero(tmp_path, mock_fail, mock_pass):
    # Case: expected_bytes = 0, parts exist.
    bundle_path = tmp_path / "bundle.json"
    part_file = tmp_path / "a.md"
    content = "content"
    part_file.write_text(content, encoding="utf-8") # 7 bytes
    sha = compute_sha256(content)

    data = {
        "completeness": {
            "parts": ["a.md"],
            "primary_part": "a.md",
            "is_complete": True,
            "expected_bytes": 0,
            "emitted_bytes": 7
        },
        "artifacts": [{"basename": "a.md", "role": "part_md", "sha256": sha}]
    }

    # This should pass because expected=0 is allowed, and overhead (7) < 64KB
    verify_full(bundle_path, data)
    mock_pass.assert_called()

def test_verify_full_expected_bytes_negative(tmp_path, mock_fail, mock_pass):
    # Case: expected_bytes = -1
    bundle_path = tmp_path / "bundle.json"
    part_file = tmp_path / "a.md"
    content = "content"
    part_file.write_text(content, encoding="utf-8")
    sha = compute_sha256(content)

    data = {
        "completeness": {
            "parts": ["a.md"],
            "primary_part": "a.md",
            "is_complete": True,
            "expected_bytes": -1,
            "emitted_bytes": 7
        },
        "artifacts": [{"basename": "a.md", "role": "part_md", "sha256": sha}]
    }

    with pytest.raises(Exception, match="FAIL"):
        verify_full(bundle_path, data)

    mock_fail.assert_called_with("Invalid expected_bytes for complete bundle: expected_bytes=-1")
