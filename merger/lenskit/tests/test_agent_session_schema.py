import json
import pytest
from pathlib import Path

# Use the strict degradation pattern according to epistemic limits in memory
try:
    import jsonschema
    from jsonschema import ValidationError
except ImportError:
    jsonschema = None
    ValidationError = None

def _require_module():
    if jsonschema is None:
        raise RuntimeError("jsonschema not installed")

def test_agent_session_schema_valid():
    try:
        _require_module()
    except RuntimeError:
        pytest.skip("jsonschema not installed")

    schema_path = Path(__file__).parent.parent / "contracts" / "agent-query-session.v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    # Simulate a valid query session
    mock_session = {
        "request": {
            "query": "hello world",
            "k": 10,
            "output_profile": "agent_minimal",
            "explain": True
        },
        "resolved_bundles": ["r1", "r2"],
        "refs": {
            "query_trace_ref": "traces/trace_123.json",
            "context_bundle_ref": "bundles/bundle_123.json",
            "diagnostics_ref": None
        },
        "warnings": ["Low evidence density"]
    }

    # Should not raise
    jsonschema.validate(instance=mock_session, schema=schema)


def test_agent_session_schema_invalid_missing_ref():
    try:
        _require_module()
    except RuntimeError:
        pytest.skip("jsonschema not installed")

    schema_path = Path(__file__).parent.parent / "contracts" / "agent-query-session.v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    mock_session = {
        "request": {"query": "hello"},
        "resolved_bundles": [],
        "refs": {
            "query_trace_ref": "traces/123.json"
            # Missing context_bundle_ref
        },
        "warnings": []
    }

    with pytest.raises(ValidationError):
        jsonschema.validate(instance=mock_session, schema=schema)
