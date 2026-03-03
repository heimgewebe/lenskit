import json
from pathlib import Path
import pytest
import jsonschema

SCHEMA_PATH = Path(__file__).parent.parent / "contracts" / "embedding-policy.v1.schema.json"

@pytest.fixture(scope="module")
def schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def test_valid_policy(schema):
    """Test that a fully populated and minimally populated policy is valid."""
    # Full policy
    valid_full = {
        "model_name": "text-embedding-3-small",
        "dimensions": 1536,
        "provider": "api",
        "similarity_metric": "cosine",
        "fallback_behavior": "fail",
        "max_tokens": 8192
    }
    jsonschema.validate(instance=valid_full, schema=schema)

    # Minimal policy (only required fields)
    valid_minimal = {
        "model_name": "all-MiniLM-L6-v2",
        "dimensions": 384,
        "provider": "local",
        "similarity_metric": "dot_product"
    }
    jsonschema.validate(instance=valid_minimal, schema=schema)

def test_invalid_policy_missing_model_name(schema):
    """Test that missing required 'model_name' raises a ValidationError."""
    invalid = {
        "dimensions": 1536,
        "provider": "api",
        "similarity_metric": "cosine"
    }
    with pytest.raises(jsonschema.ValidationError) as exc_info:
        jsonschema.validate(instance=invalid, schema=schema)
    assert "model_name" in exc_info.value.message

def test_invalid_policy_invalid_provider(schema):
    """Test that an invalid provider enum value raises a ValidationError."""
    invalid = {
        "model_name": "text-embedding-3-small",
        "dimensions": 1536,
        "provider": "magic_provider",  # Invalid enum
        "similarity_metric": "cosine"
    }
    with pytest.raises(jsonschema.ValidationError) as exc_info:
        jsonschema.validate(instance=invalid, schema=schema)
    assert exc_info.value.validator == "enum"
    assert "magic_provider" in exc_info.value.message
