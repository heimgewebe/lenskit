import json
import hashlib
from unittest.mock import patch

import pytest

from merger.lenskit.cli.pr_schau_verify import (
    load_schema,
    _compute_sha256,
    _fail,
    _pass,
)

def test_compute_sha256(tmp_path):
    """Verify _compute_sha256 correctly computes SHA256 of a file."""
    content = b"hello world"
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(content)

    expected_hash = hashlib.sha256(content).hexdigest()
    assert _compute_sha256(file_path) == expected_hash

def test_fail(capsys):
    """Verify _fail prints to stderr and exits with code 1."""
    with pytest.raises(SystemExit) as excinfo:
        _fail("test error")

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "❌ FAIL: test error" in captured.err

def test_pass(capsys):
    """Verify _pass prints to stdout."""
    _pass("test success")
    captured = capsys.readouterr()
    assert "✅ PASS: test success" in captured.out

def test_load_schema_success(tmp_path):
    """Verify load_schema returns the correct dictionary on success."""
    schema_content = {"type": "object", "properties": {"foo": {"type": "string"}}}
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps(schema_content), encoding="utf-8")

    # We patch candidates inside load_schema by patching SCHEMA_PATH which is used to initialize it
    with patch("merger.lenskit.cli.pr_schau_verify.SCHEMA_PATH", schema_file):
        assert load_schema() == schema_content

def test_load_schema_missing_file(tmp_path):
    """Verify load_schema calls _fail (exits) when the schema file is missing."""
    missing_file = tmp_path / "missing.json"

    with patch("merger.lenskit.cli.pr_schau_verify.SCHEMA_PATH", missing_file):
        with pytest.raises(SystemExit) as excinfo:
            load_schema()
        assert excinfo.value.code == 1

def test_load_schema_invalid_json(tmp_path):
    """Verify load_schema calls _fail (exits) when the schema file contains invalid JSON."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("not json", encoding="utf-8")

    with patch("merger.lenskit.cli.pr_schau_verify.SCHEMA_PATH", invalid_file):
        with pytest.raises(SystemExit) as excinfo:
            load_schema()
        assert excinfo.value.code == 1
