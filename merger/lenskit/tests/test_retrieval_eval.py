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

def test_parse_gold_queries(test_queries_file):
    queries = cmd_eval.parse_gold_queries(test_queries_file)
    assert len(queries) == 3

    q1 = queries[0]
    assert q1["query"] == "login"
    assert "src/auth.py" in q1["expected_paths"]
    assert q1["filters"]["layer"] == "core"

    q2 = queries[1]
    assert q2["query"] == "docs"
    assert "docs/" in q2["expected_paths"]

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

    # Recall: 2 out of 3 = 66.7%
    assert "Recall@10: 66.7%" in captured.out
    assert ret == 0

def test_run_eval_json(test_index_path, test_queries_file, capsys):
    args = MockArgs(index=test_index_path, queries=test_queries_file, emit="json")
    ret = cmd_eval.run_eval(args)

    captured = capsys.readouterr()
    # The JSON is printed at the end. Find the JSON block.
    # It might be mixed with progress prints if not suppressed, but run_eval prints table first then JSON.
    # The last part of output should be JSON.

    # Simple check for structure
    # With FTS missing, count is 0, hits 0. We mock index but no FTS?
    # Actually build_index enables FTS.

    # Ensure our captured output contains JSON.
    assert '"recall@10": 66.6' in captured.out or '"recall@10": 66.7' in captured.out
    assert '"total_queries": 3' in captured.out
    assert '"hits": 2' in captured.out
