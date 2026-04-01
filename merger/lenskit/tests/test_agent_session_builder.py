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

    # 1. Mock inputs using raw query results output (repo_id at top level)
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

    # Mocking actual context-bundle.v1 schema structure where repo_id is NOT top level
    mock_result = {
        "context_bundle": {
            "hits": [
                {
                    "epistemics": {"bundle_origin": "proj-r1", "provenance_type": "explicit"},
                    "range_ref": {"repo_id": "proj-r1", "file_path": "test.txt", "start_byte": 0}
                }
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


def test_build_agent_query_session_full_projection():
    """
    Tests that a fully projected API response (wrapper with bundle, warnings, federation)
    is correctly parsed by the builder against the verified schema forms.
    """
    try:
        _require_module()
    except RuntimeError:
        pytest.skip("jsonschema not installed")

    schema_path = Path(__file__).parent.parent / "contracts" / "agent-query-session.v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    mock_request = {"q": "federation query", "k": 10, "output_profile": "agent_minimal"}

    # Mocking against actual query-context-bundle.v1 and federation-trace.v1 schemas
    mock_result = {
        "context_bundle": {
            "hits": [
                {
                    "epistemics": {"bundle_origin": "primary-repo", "provenance_type": "derived"}
                }
            ]
        },
        "federation_trace": {
            "bundles": [
                {"repo_id": "remote-repo-1", "status": "ok"},
                {"repo_id": "remote-repo-2", "status": "missing"},
                {"repo_id": "remote-repo-3", "status": "error"}
            ]
        },
        "warnings": ["Cross repo identity collision", "Low evidence density"]
    }

    session = build_agent_query_session(
        request_contract=mock_request,
        result=mock_result,
        query_trace_ref="qt.json",
        context_bundle_ref="cb.json",
        diagnostics_ref="diag.json"
    )

    # Must contain both the primary hit and the successfully resolved remote
    assert "primary-repo" in session["resolved_bundles"]
    assert "remote-repo-1" in session["resolved_bundles"]
    # Must NOT contain the missing/error ones
    assert "remote-repo-2" not in session["resolved_bundles"]
    assert "remote-repo-3" not in session["resolved_bundles"]

    assert len(session["resolved_bundles"]) == 2

    assert session["refs"]["query_trace_ref"] == "qt.json"
    assert session["refs"]["context_bundle_ref"] == "cb.json"
    assert session["refs"]["diagnostics_ref"] == "diag.json"

    assert len(session["warnings"]) == 2

    jsonschema.validate(instance=session, schema=schema)
