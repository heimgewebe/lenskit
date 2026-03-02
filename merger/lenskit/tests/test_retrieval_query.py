import json
import sqlite3
import pytest
from merger.lenskit.retrieval import index_db
from merger.lenskit.retrieval import query_core

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
    res = query_core.execute_query(mini_index, query_text="", k=10, filters={"layer": "core"})
    assert res["count"] == 1
    assert res["results"][0]["chunk_id"] == "c1"

    # Filter by path substring
    res = query_core.execute_query(mini_index, query_text="", k=10, filters={"path": "test"})
    assert res["count"] == 1
    assert res["results"][0]["chunk_id"] == "c2"

    # Filter by extension
    res = query_core.execute_query(mini_index, query_text="", k=10, filters={"ext": "md"})
    assert res["count"] == 1
    assert res["results"][0]["chunk_id"] == "c3"

def test_query_fts_simple(mini_index):
    # FTS Search
    res = query_core.execute_query(mini_index, query_text="hello", k=10)
    assert res["count"] == 1
    assert res["results"][0]["chunk_id"] == "c1"

    # FTS Search no match
    res = query_core.execute_query(mini_index, query_text="zebra", k=10)
    assert res["count"] == 0

def test_query_fts_combined_filter(mini_index):
    # Match text but filter out by layer
    res = query_core.execute_query(mini_index, query_text="def", k=10, filters={"layer": "test"})
    # "def" is in both c1 (core) and c2 (test), should only find c2
    assert res["count"] == 1
    assert res["results"][0]["chunk_id"] == "c2"

def test_query_json_structure(mini_index):
    import jsonschema
    from pathlib import Path

    res = query_core.execute_query(mini_index, query_text="main", k=5, filters={"layer": "core"})
    assert "query" in res
    assert "k" in res
    assert "results" in res
    assert "engine" in res
    assert res["engine"] == "fts5"
    assert len(res["results"]) == 1

    schema_path = Path(__file__).parent.parent / "contracts" / "query-result.v1.schema.json"
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    jsonschema.validate(instance=res, schema=schema)

    hit = res["results"][0]
    assert "chunk_id" in hit
    assert "range" in hit
    assert "score" in hit
    assert "why" in hit
    assert "query_terms" in hit["why"]
    assert "applied_filter_keys" in hit["why"]
    assert "rank_features" in hit["why"]
    assert hit["why"]["query_terms"] == ["main"]
    assert hit["why"]["applied_filter_keys"] == ["layer"]
    assert "bm25" in hit["why"]["rank_features"]

    # We explicitly disabled range_ref emission because the database currently
    # stores repo-internal paths, which do not deterministically match the bundle
    # artifact paths required by the range_ref schema.
    assert "range_ref" not in hit

    res2 = query_core.execute_query(mini_index, query_text="test_main", k=5)
    assert len(res2["results"]) == 1
    assert "range_ref" not in res2["results"][0]

    res3 = query_core.execute_query(mini_index, query_text="Readme", k=5)
    assert len(res3["results"]) == 1
    assert "range_ref" not in res3["results"][0]

def _make_mock_conn(err_msg: str):
    class MockConn:
        row_factory = None
        def execute(self, sql, params=()):
            raise sqlite3.Error(err_msg)
        def close(self):
            pass
    return MockConn()

def test_query_no_fts_module_handling(mini_index, monkeypatch):
    monkeypatch.setattr(query_core.sqlite3, "connect", lambda x: _make_mock_conn("no such module: fts5"))

    with pytest.raises(RuntimeError) as excinfo:
        query_core.execute_query(mini_index, query_text="foo", k=10)

    assert "SQLite FTS5 extension missing" in str(excinfo.value)

def test_query_no_fts_table_handling(mini_index, monkeypatch):
    monkeypatch.setattr(query_core.sqlite3, "connect", lambda x: _make_mock_conn("no such table: chunks_fts"))

    with pytest.raises(RuntimeError) as excinfo:
        query_core.execute_query(mini_index, query_text="foo", k=10)

    assert "FTS table missing; likely old or corrupt index" in str(excinfo.value)

def test_query_no_bm25_function_handling(mini_index, monkeypatch):
    monkeypatch.setattr(query_core.sqlite3, "connect", lambda x: _make_mock_conn("no such function: bm25"))

    with pytest.raises(RuntimeError) as excinfo:
        query_core.execute_query(mini_index, query_text="foo", k=10)

    assert "SQLite FTS5 auxiliary function 'bm25' missing" in str(excinfo.value)

def test_query_unable_to_use_bm25_handling(mini_index, monkeypatch):
    monkeypatch.setattr(query_core.sqlite3, "connect", lambda x: _make_mock_conn("unable to use function bm25"))

    with pytest.raises(RuntimeError) as excinfo:
        query_core.execute_query(mini_index, query_text="foo", k=10)

    assert "SQLite FTS5 auxiliary function 'bm25' missing" in str(excinfo.value)
