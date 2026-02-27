import json
import sqlite3
import pytest
from pathlib import Path
from merger.lenskit.retrieval import index_db
from merger.lenskit.cli import cmd_query

@pytest.fixture
def test_index_path(tmp_path):
    dump_path = tmp_path / "dump.json"
    chunk_path = tmp_path / "chunks.jsonl"
    db_path = tmp_path / "index.sqlite"

    chunk_data = [
        {
            "chunk_id": "c1", "repo_id": "repo1", "path": "src/auth.py",
            "content": "def login(): pass", "start_line": 1, "end_line": 10,
            "layer": "core", "artifact_type": "code", "language": "python",
            "start_byte": 0, "end_byte": 10, "size_bytes": 10, "sha256": "h1"
        },
        {
            "chunk_id": "c2", "repo_id": "repo1", "path": "src/utils.py",
            "content": "def helper(): pass", "start_line": 1, "end_line": 5,
            "layer": "core", "artifact_type": "code", "language": "python",
             "start_byte": 0, "end_byte": 10, "size_bytes": 10, "sha256": "h2"
        },
        {
            "chunk_id": "c3", "repo_id": "repo2", "path": "docs/api.md",
            "content": "# API Docs", "start_line": 1, "end_line": 100,
            "layer": "doc", "artifact_type": "doc", "language": "markdown",
             "start_byte": 0, "end_byte": 10, "size_bytes": 10, "sha256": "h3"
        },
    ]
    with chunk_path.open("w") as f:
        for c in chunk_data:
            f.write(json.dumps(c) + "\n")

    dump_path.write_text("{}")

    index_db.build_index(dump_path, chunk_path, db_path)
    return db_path

class MockArgs:
    def __init__(self, index, q="", k=10, repo=None, path=None, ext=None, layer=None, artifact_type=None, emit="text"):
        self.index = str(index)
        self.q = q
        self.k = k
        self.repo = repo
        self.path = path
        self.ext = ext
        self.layer = layer
        self.artifact_type = artifact_type
        self.emit = emit

def test_query_fts_match(test_index_path, capsys):
    args = MockArgs(index=test_index_path, q="login")
    ret = cmd_query.run_query(args)

    captured = capsys.readouterr()
    assert "src/auth.py" in captured.out
    assert "Found 1 chunks" in captured.out
    assert ret == 0

def test_query_filter_repo(test_index_path, capsys):
    args = MockArgs(index=test_index_path, repo="repo2")
    ret = cmd_query.run_query(args)

    captured = capsys.readouterr()
    assert "docs/api.md" in captured.out
    assert "repo1" not in captured.out
    assert ret == 0

def test_query_filter_layer(test_index_path, capsys):
    args = MockArgs(index=test_index_path, layer="core")
    ret = cmd_query.run_query(args)

    captured = capsys.readouterr()
    assert "src/auth.py" in captured.out
    assert "src/utils.py" in captured.out
    assert "docs/api.md" not in captured.out
    assert ret == 0

def test_query_filter_artifact_type(test_index_path, capsys):
    args = MockArgs(index=test_index_path, artifact_type="code")
    ret = cmd_query.run_query(args)

    captured = capsys.readouterr()
    assert "src/auth.py" in captured.out
    assert "src/utils.py" in captured.out
    assert "docs/api.md" not in captured.out
    assert ret == 0

    args = MockArgs(index=test_index_path, artifact_type="doc")
    ret = cmd_query.run_query(args)
    captured = capsys.readouterr()
    assert "src/auth.py" not in captured.out
    assert "docs/api.md" in captured.out
    assert ret == 0

def test_query_json_output(test_index_path, capsys):
    args = MockArgs(index=test_index_path, q="login", emit="json")
    ret = cmd_query.run_query(args)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["query"] == "login"
    assert output["count"] == 1
    assert output["engine"] == "fts5"
    assert output["query_mode"] == "fts"
    assert output["applied_filters"]["repo"] is None
    assert output["results"][0]["path"] == "src/auth.py"
    assert ret == 0
