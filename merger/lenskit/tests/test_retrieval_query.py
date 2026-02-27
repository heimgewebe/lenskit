import json
import sqlite3
import pytest
from merger.lenskit.retrieval import index_db
from merger.lenskit.cli import cmd_query

@pytest.fixture
def mini_index(tmp_path):
    # Setup paths
    dump_path = tmp_path / "dump.json"
    chunk_path = tmp_path / "chunks.jsonl"
    db_path = tmp_path / "index.sqlite"

    # Write chunks
    chunk_data = [
        {"chunk_id": "c1", "repo_id": "r1", "path": "src/main.py", "content": "def main(): print('hello world')", "start_line": 1, "end_line": 1, "layer": "core", "artifact_type": "code", "content_sha256": "h1"},
        {"chunk_id": "c2", "repo_id": "r1", "path": "tests/test_main.py", "content": "def test_main(): assert True", "start_line": 1, "end_line": 1, "layer": "test", "artifact_type": "code", "content_sha256": "h2"},
        {"chunk_id": "c3", "repo_id": "r1", "path": "docs/readme.md", "content": "# Readme\nThis is a doc.", "start_line": 1, "end_line": 2, "layer": "docs", "artifact_type": "doc", "content_sha256": "h3"},
    ]
    with chunk_path.open("w", encoding="utf-8") as f:
        for c in chunk_data:
            f.write(json.dumps(c) + "\n")

    dump_path.write_text(json.dumps({"dummy": "data"}), encoding="utf-8")

    index_db.build_index(dump_path, chunk_path, db_path)
    return db_path

def test_query_metadata_filter(mini_index):
    # Filter by layer
    res = cmd_query.execute_query(mini_index, query_text="", k=10, filters={"layer": "core"})
    assert res["count"] == 1
    assert res["results"][0]["chunk_id"] == "c1"

    # Filter by path substring
    res = cmd_query.execute_query(mini_index, query_text="", k=10, filters={"path": "test"})
    assert res["count"] == 1
    assert res["results"][0]["chunk_id"] == "c2"

    # Filter by extension
    res = cmd_query.execute_query(mini_index, query_text="", k=10, filters={"ext": "md"})
    assert res["count"] == 1
    assert res["results"][0]["chunk_id"] == "c3"

def test_query_fts_simple(mini_index):
    # FTS Search
    res = cmd_query.execute_query(mini_index, query_text="hello", k=10)
    assert res["count"] == 1
    assert res["results"][0]["chunk_id"] == "c1"

    # FTS Search no match
    res = cmd_query.execute_query(mini_index, query_text="zebra", k=10)
    assert res["count"] == 0

def test_query_fts_combined_filter(mini_index):
    # Match text but filter out by layer
    res = cmd_query.execute_query(mini_index, query_text="def", k=10, filters={"layer": "test"})
    # "def" is in both c1 (core) and c2 (test), should only find c2
    assert res["count"] == 1
    assert res["results"][0]["chunk_id"] == "c2"

def test_query_json_structure(mini_index):
    res = cmd_query.execute_query(mini_index, query_text="main", k=5, filters={"layer": "core"})
    assert "query" in res
    assert "results" in res
    assert "engine" in res
    assert res["engine"] == "fts5"
    assert len(res["results"]) == 1

    hit = res["results"][0]
    assert "chunk_id" in hit
    assert "range" in hit
    assert "score" in hit

def test_query_no_fts_module_handling(mini_index, monkeypatch):
    """
    Integration test-like check to ensure that if sqlite3 raises an error about missing FTS5,
    it is correctly wrapped as a RuntimeError.
    We mock sqlite3.connect to return a cursor that raises specific OperationalError.
    """

    # Mock connection and cursor
    class MockCursor:
        def execute(self, sql, params=()):
            raise sqlite3.Error("no such module: fts5")
        def fetchall(self):
            return []
        def close(self):
            pass

    class MockConn:
        row_factory = None
        def execute(self, sql, params=()):
            # The code calls conn.execute(), which returns a cursor.
            # We return a cursor, but the cursor's methods will fail if called?
            # Or does execute() itself fail?
            # In sqlite3, conn.execute() is a shortcut that creates a cursor and calls execute.
            # So let's make it raise immediately for the shortcut case,
            # OR return a cursor that raises.
            # The actual code: `cursor = conn.execute(base_sql, params)`
            # So we can raise here directly.
            raise sqlite3.Error("no such module: fts5")

        def close(self):
            pass

    # Patch the sqlite3 module AS IMPORTED by cmd_query
    monkeypatch.setattr(cmd_query.sqlite3, "connect", lambda x: MockConn())

    with pytest.raises(RuntimeError) as excinfo:
        cmd_query.execute_query(mini_index, query_text="foo", k=10)

    assert "SQLite FTS5 extension missing" in str(excinfo.value)
