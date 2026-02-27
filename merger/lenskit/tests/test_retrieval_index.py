import json
import sqlite3
import pytest
from pathlib import Path
from merger.lenskit.retrieval import index_db

@pytest.fixture
def mini_artifacts(tmp_path):
    # Setup paths
    dump_path = tmp_path / "dump.json"
    chunk_path = tmp_path / "chunks.jsonl"

    # Write chunks
    chunk_data = [
        {"chunk_id": "c1", "repo_id": "r1", "path": "src/main.py", "content": "def main(): pass", "start_line": 1, "end_line": 1, "layer": "core"},
        {"chunk_id": "c2", "repo_id": "r1", "path": "tests/test_main.py", "content": "def test_main(): assert True", "start_line": 1, "end_line": 1, "layer": "test"},
    ]
    with chunk_path.open("w") as f:
        for c in chunk_data:
            f.write(json.dumps(c) + "\n")

    # Write dump
    dump_data = {"dummy": "data"}
    dump_path.write_text(json.dumps(dump_data))

    return dump_path, chunk_path

def test_index_build_counts(mini_artifacts, tmp_path):
    dump_path, chunk_path = mini_artifacts
    db_path = tmp_path / "index.sqlite"

    index_db.build_index(dump_path, chunk_path, db_path)

    assert db_path.exists()

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    # Check chunks table count
    count = c.execute("SELECT count(*) FROM chunks").fetchone()[0]
    assert count == 2

    # Check FTS table count
    fts_count = c.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
    assert fts_count == 2

    conn.close()

def test_index_metadata_integrity(mini_artifacts, tmp_path):
    dump_path, chunk_path = mini_artifacts
    db_path = tmp_path / "index.sqlite"

    index_db.build_index(dump_path, chunk_path, db_path)

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    row = c.execute("SELECT value FROM index_meta WHERE key='schema_version'").fetchone()
    assert row[0] == index_db.INDEX_SCHEMA_VERSION

    conn.close()

def test_stale_index_detection(mini_artifacts, tmp_path):
    dump_path, chunk_path = mini_artifacts
    db_path = tmp_path / "index.sqlite"

    # Build initial
    index_db.build_index(dump_path, chunk_path, db_path)
    assert index_db.verify_index(db_path, dump_path, chunk_path) is True

    # Mutate dump file
    dump_path.write_text("modified content")

    # Check stale
    assert index_db.verify_index(db_path, dump_path, chunk_path) is False
