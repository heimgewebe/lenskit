import json
import pytest
from pathlib import Path
from merger.lenskit.cli import cmd_eval
from merger.lenskit.retrieval import index_db

@pytest.fixture
def test_queries_file(tmp_path):
    f = tmp_path / "queries.md"
    f.write_text("""
# Gold Queries

1. **"login"**
   * *Intent:* Login
   * *Expected:* `src/auth.py`
   * *Filter:* `layer=core`

2. **"docs"**
   * *Intent:* Documentation
   * *Expected:* `docs/`

3. **"nothing"**
   * *Intent:* Non-existent
   * *Expected:* `missing.py`

4. **"complex filter"**
   * *Intent:* Filter with special chars
   * *Expected:* `foo.py`
   * *Filter:* `repo=my-repo`, `ext=.py`, `path=src/core`
    """, encoding="utf-8")
    return f

@pytest.fixture
def test_index_path(tmp_path):
    dump_path = tmp_path / "dump.json"
    chunk_path = tmp_path / "chunks.jsonl"
    db_path = tmp_path / "index.sqlite"

    chunk_data = [
        {
            "chunk_id": "c1", "repo_id": "r1", "path": "src/auth.py",
            "content": "def login(): pass", "start_line": 1, "end_line": 10,
            "layer": "core", "artifact_type": "code"
        },
        {
            "chunk_id": "c2", "repo_id": "r1", "path": "docs/readme.md",
            "content": "# Docs", "start_line": 1, "end_line": 10,
            "layer": "doc", "artifact_type": "doc"
        }
    ]
    with chunk_path.open("w") as f:
        for c in chunk_data:
            f.write(json.dumps(c) + "\n")

    dump_path.write_text("{}")
    index_db.build_index(dump_path, chunk_path, db_path)
    return db_path

class MockArgs:
    def __init__(self, index, queries, k=10, emit="text"):
        self.index = str(index)
        self.queries = str(queries)
        self.k = k
        self.emit = emit

def test_parse_gold_queries_complex(test_queries_file):
    queries = cmd_eval.parse_gold_queries(test_queries_file)
    assert len(queries) == 4

    q4 = queries[3]
    assert q4["query"] == "complex filter"
    assert q4["filters"]["repo"] == "my-repo"
    assert q4["filters"]["ext"] == ".py"
    assert q4["filters"]["path"] == "src/core"

def test_run_eval_flow(test_index_path, test_queries_file, capsys):
    args = MockArgs(index=test_index_path, queries=test_queries_file)
    ret = cmd_eval.run_eval(args)

    captured = capsys.readouterr()

    # Query 1: "login" should match src/auth.py
    assert "login" in captured.out
    assert "✅" in captured.out

    # Query 2: "docs" should match docs/readme.md (contains "docs/")
    assert "docs" in captured.out
    assert "✅" in captured.out

    # Query 3: "nothing" should fail
    assert "nothing" in captured.out
    assert "❌" in captured.out

    # Metrics printed in text mode
    # 2 out of 4 = 50.0%
    assert "Recall@10: 50.0%" in captured.out
    assert ret == 0

def test_run_eval_json_purity(test_index_path, test_queries_file, capsys):
    args = MockArgs(index=test_index_path, queries=test_queries_file, emit="json")
    ret = cmd_eval.run_eval(args)

    captured = capsys.readouterr()

    # stdout should be PURE JSON
    try:
        output = json.loads(captured.out)
    except json.JSONDecodeError:
        pytest.fail("Output is not valid JSON: " + captured.out)

    assert output["metrics"]["total_queries"] == 4
    assert output["metrics"]["hits"] == 2
    # Check details presence
    assert len(output["details"]) == 4

    # Ensure no table artifacts in stdout
    assert "|" not in captured.out
    assert "Recall@" not in captured.out  # Metric label shouldn't be in text

def test_run_eval_query_error(test_index_path, tmp_path, capsys):
    # Setup a query file with an invalid query (e.g. invalid FTS syntax or mocking failure)
    # Using invalid FTS syntax "AND OR" usually triggers syntax error
    f = tmp_path / "error_queries.md"
    f.write_text("""
# Error Queries
1. **"syntax error AND OR"**
   * *Intent:* Broken
   * *Expected:* `none`
    """, encoding="utf-8")

    args = MockArgs(index=test_index_path, queries=f, emit="json")
    ret = cmd_eval.run_eval(args)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["metrics"]["total_queries"] == 1
    assert output["metrics"]["hits"] == 0
    assert output["metrics"]["recall@10"] == 0.0

    detail = output["details"][0]
    assert "error" in detail
    assert detail["is_relevant"] is False
    assert detail["found_count"] == 0
