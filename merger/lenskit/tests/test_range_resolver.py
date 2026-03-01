import json
import hashlib
from pathlib import Path
import pytest
from merger.lenskit.core.range_resolver import resolve_range_ref
from merger.lenskit.core.constants import ArtifactRole

@pytest.fixture
def manifest_env(tmp_path):
    # Setup dummy manifest and artifact
    manifest_path = tmp_path / "bundle.manifest.json"
    artifact_path = tmp_path / "code.md"

    content = b"Line 1\nLine 2\nLine 3\n"
    artifact_path.write_bytes(content)

    # We want to target "Line 2\n" -> bytes 7 to 14
    start_byte = 7
    end_byte = 14
    expected_sha256 = hashlib.sha256(content[start_byte:end_byte]).hexdigest()

    manifest_data = {
        "kind": "repolens.bundle.manifest",
        "run_id": "test-run",
        "generator": {
            "config_sha256": "dummy-config-hash"
        },
        "artifacts": [
            {
                "role": "canonical_md",
                "path": "code.md"
            }
        ]
    }

    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    return {
        "manifest_path": manifest_path,
        "artifact_path": artifact_path,
        "content": content,
        "start_byte": start_byte,
        "end_byte": end_byte,
        "expected_sha256": expected_sha256
    }

def test_valid_range_returns_exact_content(manifest_env):
    ref = {
        "artifact_role": "canonical_md",
        "repo_id": "test-repo",
        "file_path": "code.md",
        "start_byte": manifest_env["start_byte"],
        "end_byte": manifest_env["end_byte"],
        "start_line": 2,
        "end_line": 2,
        "content_sha256": manifest_env["expected_sha256"]
    }

    result = resolve_range_ref(manifest_env["manifest_path"], ref)
    assert result["text"] == "Line 2\n"
    assert result["sha256"] == manifest_env["expected_sha256"]
    assert result["bytes"] == 7

def test_wrong_sha256_raises_error(manifest_env):
    ref = {
        "artifact_role": "canonical_md",
        "repo_id": "test-repo",
        "file_path": "code.md",
        "start_byte": manifest_env["start_byte"],
        "end_byte": manifest_env["end_byte"],
        "start_line": 2,
        "end_line": 2,
        "content_sha256": "b"*64
    }
    with pytest.raises(ValueError, match="Hash mismatch"):
        resolve_range_ref(manifest_env["manifest_path"], ref)

def test_unknown_role_raises_error(manifest_env):
    ref = {
        "artifact_role": "invalid_role",
        "repo_id": "test-repo",
        "file_path": "code.md",
        "start_byte": 0,
        "end_byte": 5,
        "start_line": 1,
        "end_line": 2,
        "content_sha256": "c"*64
    }
    with pytest.raises(ValueError, match="range_ref failed schema"):
        resolve_range_ref(manifest_env["manifest_path"], ref)

def test_out_of_bounds_range_fails(manifest_env):
    ref = {
        "artifact_role": "canonical_md",
        "repo_id": "test-repo",
        "file_path": "code.md",
        "start_byte": 100,
        "end_byte": 200,
        "start_line": 1,
        "end_line": 2,
        "content_sha256": "a"*64
    }
    with pytest.raises(ValueError, match="out of bounds"):
        resolve_range_ref(manifest_env["manifest_path"], ref)

def test_missing_role_in_manifest(manifest_env):
    ref = {
        "artifact_role": "index_sidecar_json",
        "repo_id": "test-repo",
        "file_path": "code.md",
        "start_byte": 0,
        "end_byte": 5,
        "start_line": 1,
        "end_line": 2,
        "content_sha256": "a"*64
    }
    with pytest.raises(ValueError, match="not found in manifest"):
        resolve_range_ref(manifest_env["manifest_path"], ref)

def test_cli_json_output_structure_valid(manifest_env, tmp_path, monkeypatch, capsys):
    from merger.lenskit.cli.main import main

    ref = {
        "artifact_role": "canonical_md",
        "repo_id": "test-repo",
        "file_path": "code.md",
        "start_byte": manifest_env["start_byte"],
        "end_byte": manifest_env["end_byte"],
        "start_line": 2,
        "end_line": 2,
        "content_sha256": manifest_env["expected_sha256"]
    }
    ref_path = tmp_path / "ref.json"
    ref_path.write_text(json.dumps(ref), encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["lenskit", "range", "get", "--manifest", str(manifest_env["manifest_path"]), "--ref", str(ref_path), "--format", "json"])

    ret = main()
    assert ret == 0

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert "text" in output
    assert "sha256" in output
    assert "bytes" in output
    assert "lines" in output
    assert "provenance" in output

    assert output["text"] == "Line 2\n"
    assert output["sha256"] == manifest_env["expected_sha256"]
    assert output["provenance"]["artifact_role"] == "canonical_md"

def test_schema_validation_passes(manifest_env):
    ref = {
        "artifact_role": "canonical_md",
        "repo_id": "test-repo",
        "file_path": "code.md",
        "start_byte": manifest_env["start_byte"],
        "end_byte": manifest_env["end_byte"],
        "start_line": 2,
        "end_line": 2,
        "content_sha256": manifest_env["expected_sha256"]
    }

    # Valid ref
    result = resolve_range_ref(manifest_env["manifest_path"], ref)
    assert result["text"] == "Line 2\n"

    # Invalid ref missing required field
    ref_invalid = ref.copy()
    del ref_invalid["repo_id"]
    with pytest.raises(ValueError, match="range_ref failed schema"):
        resolve_range_ref(manifest_env["manifest_path"], ref_invalid)
