import json
import pytest
from pathlib import Path
from merger.lenskit.cli import cmd_eval
from merger.lenskit.retrieval import index_db, eval_core

@pytest.fixture
def mini_index_for_eval(tmp_path):
    # Setup paths
    dump_path = tmp_path / "dump.json"
    chunk_path = tmp_path / "chunks.jsonl"
    db_path = tmp_path / "index.sqlite"

    # Write chunks covering typical targets
    chunk_data = [
        {"chunk_id": "c1", "repo_id": "r1", "path": "src/auth/login.py", "content": "def login(): pass", "start_line": 1, "end_line": 1, "layer": "core", "artifact_type": "code"},
        {"chunk_id": "c2", "repo_id": "r1", "path": "src/config/settings.py", "content": "SECRET_KEY = 'xyz'", "start_line": 1, "end_line": 1, "layer": "core", "artifact_type": "code"},
        {"chunk_id": "c3", "repo_id": "r1", "path": "docs/api.md", "content": "# API Docs", "start_line": 1, "end_line": 1, "layer": "docs", "artifact_type": "doc"},
    ]
    with chunk_path.open("w", encoding="utf-8") as f:
        for c in chunk_data:
            f.write(json.dumps(c) + "\n")

    dump_path.write_text(json.dumps({"dummy": "data"}), encoding="utf-8")
    index_db.build_index(dump_path, chunk_path, db_path)
    return db_path

def test_parse_gold_queries_basic(tmp_path):
    md_file = tmp_path / "queries.md"
    md_content = """
# Test Queries

1. **"find auth"**
   *Intent:* Check login.
   *Expected:* `login.py`, `auth/`
   *Filter:* `layer=core`

2. **"find settings"**
   *Expected:* `settings.py`
"""
    md_file.write_text(md_content, encoding="utf-8")

    queries = eval_core.parse_gold_queries(md_file)
    assert len(queries) == 2

    q1 = queries[0]
    assert q1["query"] == "find auth"
    assert "login.py" in q1["expected_paths"]
    assert "auth/" in q1["expected_paths"]
    assert q1["filters"]["layer"] == "core"

    q2 = queries[1]
    assert q2["query"] == "find settings"
    assert "settings.py" in q2["expected_paths"]

def test_parse_gold_queries_robustness(tmp_path):
    # Test weird formatting
    md_file = tmp_path / "messy.md"
    md_content = """
10. **"weird query"**
   - Expected: `foo`
   * Filter: `ext=py` `repo=main`
"""
    md_file.write_text(md_content, encoding="utf-8")

    queries = eval_core.parse_gold_queries(md_file)
    assert len(queries) == 1
    q = queries[0]
    assert q["query"] == "weird query"
    assert "foo" in q["expected_paths"]
    assert q["filters"]["ext"] == "py"
    assert q["filters"]["repo"] == "main"

def test_run_eval_integration(mini_index_for_eval, tmp_path, capsys):
    # Create a query file that matches the mini index
    queries_md = tmp_path / "eval_queries.md"
    queries_md.write_text("""
1. **"login"**
   *Expected:* `login.py`

2. **"missing thing"**
   *Expected:* `unicorn.py`
""", encoding="utf-8")

    # Mock args
    class Args:
        index = str(mini_index_for_eval)
        queries = str(queries_md)
        k = 5
        emit = "json"

    # Run Eval
    ret_code = cmd_eval.run_eval(Args())
    assert ret_code == 0

    # Capture JSON output
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert "metrics" in output
    metrics = output["metrics"]
    assert metrics["total_queries"] == 2
    assert metrics["hits"] == 1
    assert metrics["recall@5"] == 50.0

    details = output["details"]
    assert len(details) == 2

    # Check hit
    hit = details[0]
    assert hit["query"] == "login"
    assert hit["is_relevant"] is True
    assert "login.py" in hit["hit_path"]

    # Check miss
    miss = details[1]
    assert miss["query"] == "missing thing"
    assert miss["is_relevant"] is False

def test_schema_smoke():
    """
    Minimal contract check: Ensure output structure matches key expectations
    without full JSON schema validation lib.
    """
    # Resolve schema path relative to this test file for robustness
    # structure: merger/lenskit/tests/test_retrieval_eval.py
    # target: merger/lenskit/contracts/retrieval-eval.v1.schema.json
    # ../../contracts/

    base_dir = Path(__file__).resolve().parent.parent
    schema_path = base_dir / "contracts" / "retrieval-eval.v1.schema.json"

    assert schema_path.exists(), f"Schema file missing at expected path: {schema_path}"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert "metrics" in schema["properties"]
    assert "details" in schema["properties"]

def test_parse_gold_queries_json(tmp_path):
    json_file = tmp_path / "queries.json"
    json_content = [
        {
            "query": "find auth",
            "expected_patterns": ["login.py", "auth/"],
            "filters": {"layer": "core"},
            "accept_criteria": {"recall_at_10": 0.5}
        }
    ]
    json_file.write_text(json.dumps(json_content), encoding="utf-8")

    queries = eval_core.parse_gold_queries(json_file)
    assert len(queries) == 1
    q1 = queries[0]
    assert q1["query"] == "find auth"
    assert "login.py" in q1["expected_paths"]
    assert q1["filters"]["layer"] == "core"
    assert q1["accept_criteria"]["recall_at_10"] == 0.5

def test_run_eval_integration_json(mini_index_for_eval, tmp_path, capsys):
    queries_json = tmp_path / "eval_queries.json"
    queries_json.write_text(json.dumps([
        {
            "query": "login",
            "expected_patterns": ["login.py"],
            "accept_criteria": {"recall_at_5": 0.5}
        },
        {
            "query": "missing thing",
            "expected_patterns": ["unicorn.py"],
            "accept_criteria": {"recall_at_5": 0.5}
        }
    ]), encoding="utf-8")

    class Args:
        index = str(mini_index_for_eval)
        queries = str(queries_json)
        k = 5
        emit = "json"

    # Run Eval
    ret_code = cmd_eval.run_eval(Args())
    assert ret_code == 0

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["metrics"]["recall@5"] == 50.0

    # Test why-Propagation for hits
    details = output["details"]
    login_hit = next(d for d in details if d["query"] == "login")
    assert login_hit["is_relevant"] is True
    assert "why" in login_hit
    why = login_hit["why"]
    assert "matched_terms" in why
    assert "filter_pass" in why
    assert "rank_features" in why

def test_run_eval_gate_failure(mini_index_for_eval, tmp_path, capsys):
    queries_json = tmp_path / "eval_queries.json"
    queries_json.write_text(json.dumps([
        {
            "query": "missing thing",
            "expected_patterns": ["unicorn.py"],
            "accept_criteria": {"recall_at_5": 0.8}
        }
    ]), encoding="utf-8")

    class Args:
        index = str(mini_index_for_eval)
        queries = str(queries_json)
        k = 5
        emit = "json"

    # Should fail due to accept criteria gate
    ret_code = cmd_eval.run_eval(Args())
    assert ret_code == 1

def test_run_eval_conflicting_thresholds_fails(mini_index_for_eval, tmp_path, capsys):
    queries_json = tmp_path / "eval_queries.json"
    queries_json.write_text(json.dumps([
        {
            "query": "login",
            "expected_patterns": ["login.py"],
            "accept_criteria": {"recall_at_5": 0.5}
        },
        {
            "query": "missing thing",
            "expected_patterns": ["unicorn.py"],
            "accept_criteria": {"recall_at_5": 0.6}
        }
    ]), encoding="utf-8")

    class Args:
        index = str(mini_index_for_eval)
        queries = str(queries_json)
        k = 5
        emit = "json"

    ret_code = cmd_eval.run_eval(Args())
    assert ret_code == 1
    captured = capsys.readouterr()
    assert "Error: Multiple conflicting recall_at_5 thresholds found in queries" in captured.err

def test_run_eval_invalid_threshold_fails(mini_index_for_eval, tmp_path, capsys):
    queries_json = tmp_path / "eval_queries.json"
    queries_json.write_text(json.dumps([
        {
            "query": "login",
            "expected_patterns": ["login.py"],
            "accept_criteria": {"recall_at_5": 80.0}
        }
    ]), encoding="utf-8")

    class Args:
        index = str(mini_index_for_eval)
        queries = str(queries_json)
        k = 5
        emit = "json"

    ret_code = cmd_eval.run_eval(Args())
    assert ret_code == 1
    captured = capsys.readouterr()
    assert "Error: Invalid recall_at_5 threshold (80.0). accept_criteria must use a ratio between 0.0 and 1.0." in captured.err
