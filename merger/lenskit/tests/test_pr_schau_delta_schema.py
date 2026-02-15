import pytest
import json
import jsonschema
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "contracts" / "pr-schau-delta.v1.schema.json"

@pytest.fixture
def schema():
    if not SCHEMA_PATH.exists():
        pytest.skip("Schema file not found")
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

def validate(data, schema):
    jsonschema.validate(instance=data, schema=schema)

def test_valid_delta(schema):
    data = {
        "kind": "repolens.pr_schau.delta",
        "version": 1,
        "repo": "test-repo",
        "generated_at": "2024-02-14T12:00:00Z",
        "summary": {
            "added": 1,
            "changed": 1,
            "removed": 1
        },
        "files": [
            {
                "path": "added.py",
                "status": "added",
                "size_bytes": 100,
                "sha256": "a" * 64,
                "sha256_status": "ok"
            },
            {
                "path": "changed.py",
                "status": "changed",
                "size_bytes": 200,
                "sha256": None,
                "sha256_status": "missing"
            },
            {
                "path": "removed.py",
                "status": "removed",
                "size_bytes": 50,
                "sha256": None,
                "sha256_status": "skipped"
            }
        ]
    }
    validate(data, schema)

def test_invalid_removed_with_sha(schema):
    data = {
        "kind": "repolens.pr_schau.delta",
        "version": 1,
        "repo": "test-repo",
        "generated_at": "2024-02-14T12:00:00Z",
        "summary": {"added": 0, "changed": 0, "removed": 1},
        "files": [
            {
                "path": "removed.py",
                "status": "removed",
                "size_bytes": 50,
                "sha256": "a" * 64, # SHOULD BE NULL
                "sha256_status": "skipped"
            }
        ]
    }
    with pytest.raises(jsonschema.ValidationError):
        validate(data, schema)

def test_invalid_added_with_skipped(schema):
    data = {
        "kind": "repolens.pr_schau.delta",
        "version": 1,
        "repo": "test-repo",
        "generated_at": "2024-02-14T12:00:00Z",
        "summary": {"added": 1, "changed": 0, "removed": 0},
        "files": [
            {
                "path": "added.py",
                "status": "added",
                "size_bytes": 100,
                "sha256": None,
                "sha256_status": "skipped" # SHOULD NOT BE SKIPPED
            }
        ]
    }
    with pytest.raises(jsonschema.ValidationError):
        validate(data, schema)

def test_additional_properties_forbidden(schema):
    data = {
        "kind": "repolens.pr_schau.delta",
        "version": 1,
        "repo": "test-repo",
        "generated_at": "2024-02-14T12:00:00Z",
        "summary": {"added": 0, "changed": 0, "removed": 0},
        "files": [],
        "extra": "junk" # FORBIDDEN
    }
    with pytest.raises(jsonschema.ValidationError):
        validate(data, schema)
