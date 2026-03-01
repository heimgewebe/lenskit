import json
import pytest
from pathlib import Path

import jsonschema
from merger.lenskit.tests._test_constants import TEST_CONFIG_SHA256, TEST_ARTIFACT_SHA256

@pytest.fixture
def schema():
    schema_path = Path(__file__).parent.parent / "contracts" / "bundle-manifest.v1.schema.json"
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_valid_bundle_manifest(schema):
    valid_data = {
        "kind": "repolens.bundle.manifest",
        "version": "1.0",
        "run_id": "test-run-1234",
        "created_at": "2023-10-12T10:00:00Z",
        "generator": {
            "name": "lenskit-test",
            "version": "v1.2.3",
            "config_sha256": TEST_CONFIG_SHA256
        },
        "artifacts": [
            {
                "role": "canonical_md",
                "path": "output.md",
                "content_type": "text/markdown",
                "bytes": 1024,
                "sha256": TEST_ARTIFACT_SHA256,
                "interpretation": {"mode": "role_only"}
            },
            {
                "role": "index_sidecar_json",
                "path": "sidecar.json",
                "content_type": "application/json",
                "bytes": 2048,
                "sha256": TEST_ARTIFACT_SHA256,
                "contract": {
                    "id": "repolens-agent",
                    "version": "v2"
                },
                "interpretation": {"mode": "contract"}
            }
        ],
        "links": {
            "canonical_dump_index_sha256": TEST_ARTIFACT_SHA256
        },
        "capabilities": {
            "fts5_bm25": True
        }
    }
    jsonschema.validate(instance=valid_data, schema=schema)


def test_invalid_bundle_manifest_role_only_with_contract(schema):
    invalid_data = {
        "kind": "repolens.bundle.manifest",
        "version": "1.0",
        "run_id": "test-run-1234",
        "created_at": "2023-10-12T10:00:00Z",
        "generator": {
            "name": "lenskit-test",
            "version": "v1.2.3",
            "config_sha256": TEST_CONFIG_SHA256
        },
        "artifacts": [
            {
                "role": "canonical_md",
                "path": "output.md",
                "content_type": "text/markdown",
                "bytes": 1024,
                "sha256": TEST_ARTIFACT_SHA256,
                "interpretation": {"mode": "role_only"},
                "contract": {"id": "foo", "version": "1.0"}
            }
        ],
        "links": {},
        "capabilities": {}
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_data, schema=schema)


def test_invalid_bundle_manifest_contract_missing_interpretation(schema):
    invalid_data = {
        "kind": "repolens.bundle.manifest",
        "version": "1.0",
        "run_id": "test-run-1234",
        "created_at": "2023-10-12T10:00:00Z",
        "generator": {
            "name": "lenskit-test",
            "version": "v1.2.3",
            "config_sha256": TEST_CONFIG_SHA256
        },
        "artifacts": [
            {
                "role": "index_sidecar_json",
                "path": "sidecar.json",
                "content_type": "application/json",
                "bytes": 2048,
                "sha256": TEST_ARTIFACT_SHA256,
                "contract": {
                    "id": "repolens-agent",
                    "version": "v2"
                }
            }
        ],
        "links": {},
        "capabilities": {}
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_data, schema=schema)


def test_invalid_bundle_manifest_interpretation_contract_without_contract(schema):
    invalid_data = {
        "kind": "repolens.bundle.manifest",
        "version": "1.0",
        "run_id": "test-run-1234",
        "created_at": "2023-10-12T10:00:00Z",
        "generator": {
            "name": "lenskit-test",
            "version": "v1.2.3",
            "config_sha256": TEST_CONFIG_SHA256
        },
        "artifacts": [
            {
                "role": "canonical_md",
                "path": "output.md",
                "content_type": "text/markdown",
                "bytes": 1024,
                "sha256": TEST_ARTIFACT_SHA256,
                "interpretation": {"mode": "contract"}
            }
        ],
        "links": {},
        "capabilities": {}
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_data, schema=schema)


def test_invalid_bundle_manifest_missing_required(schema):
    invalid_data = {
        "kind": "repolens.bundle.manifest",
        "version": "1.0"
        # missing run_id, created_at, generator, artifacts, links, capabilities
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_data, schema=schema)


def test_invalid_bundle_manifest_bad_role(schema):
    invalid_data = {
        "kind": "repolens.bundle.manifest",
        "version": "1.0",
        "run_id": "test-run-1234",
        "created_at": "2023-10-12T10:00:00Z",
        "generator": {
            "name": "lenskit-test",
            "version": "v1.2.3",
            "config_sha256": TEST_CONFIG_SHA256
        },
        "artifacts": [
            {
                "role": "invalid_role_not_in_enum",
                "path": "output.md",
                "content_type": "text/markdown",
                "bytes": 1024,
                "sha256": TEST_ARTIFACT_SHA256
            }
        ],
        "links": {},
        "capabilities": {}
    }
    with pytest.raises(jsonschema.ValidationError) as exc:
        jsonschema.validate(instance=invalid_data, schema=schema)
    assert exc.value.validator == "enum"
    assert exc.value.instance == "invalid_role_not_in_enum"
