import json
import pytest
from pathlib import Path

from merger.lenskit.retrieval.session import build_agent_query_session

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

def test_build_agent_query_session_creates_valid_contract():
    try:
        _require_module()
    except RuntimeError:
        pytest.skip("jsonschema not installed")

    schema_path = Path(__file__).parent.parent / "contracts" / "agent-query-session.v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    # 1. Mock inputs
    mock_request = {"q": "search term", "k": 5}
    mock_result = {
        "results": [
            {"repo_id": "r1", "path": "file1.py"},
            {"repo_id": "r2", "path": "file2.py"},
            {"repo_id": "r1", "path": "file3.py"}
        ],
        "warnings": ["Low evidence density"]
    }

    # 2. Build session
    session = build_agent_query_session(
        request_contract=mock_request,
        result=mock_result,
        query_trace_ref="query_trace.json",
        context_bundle_ref="bundle.json",
        diagnostics_ref=None
    )

    # 3. Assertions
    assert "r1" in session["resolved_bundles"]
    assert "r2" in session["resolved_bundles"]
    assert len(session["resolved_bundles"]) == 2  # Unique repo_ids

    assert session["refs"]["query_trace_ref"] == "query_trace.json"
    assert session["refs"]["context_bundle_ref"] == "bundle.json"
    assert session["refs"]["diagnostics_ref"] is None

    assert session["warnings"] == ["Low evidence density"]

    # 4. Validates against schema
    jsonschema.validate(instance=session, schema=schema)


def test_build_agent_query_session_from_projected_context():
    try:
        _require_module()
    except RuntimeError:
        pytest.skip("jsonschema not installed")

    schema_path = Path(__file__).parent.parent / "contracts" / "agent-query-session.v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    mock_request = {"q": "proj test"}
    mock_result = {
        "context_bundle": {
            "hits": [
                {"repo_id": "proj-r1", "path": "test.txt"}
            ]
        }
    }

    session = build_agent_query_session(
        request_contract=mock_request,
        result=mock_result,
        query_trace_ref=None,
        context_bundle_ref=None,
        diagnostics_ref=None
    )

    assert session["resolved_bundles"] == ["proj-r1"]
    assert session["refs"]["query_trace_ref"] is None
    jsonschema.validate(instance=session, schema=schema)
