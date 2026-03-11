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
    assert "matched_terms" in hit["why"]
    assert "filter_pass" in hit["why"]
    assert "rank_features" in hit["why"]
    assert hit["why"]["matched_terms"] == ["main"]
    assert hit["why"]["filter_pass"] == ["layer"]
    assert "bm25" in hit["why"]["rank_features"]

    # Explicit range_ref should only exist if explicitly stored (it's not here)
    assert "range_ref" not in hit

    # Because `mini_index` uses chunks without genuine byte ranges, the DB defaults to start_byte=0, end_byte=0.
    # Since end_byte is not > start_byte, the query_core logic correctly refuses to emit derived_range_ref.
    assert "derived_range_ref" not in hit

    res2 = query_core.execute_query(mini_index, query_text="test_main", k=5)
    assert len(res2["results"]) == 1
    assert "range_ref" not in res2["results"][0]
    assert "derived_range_ref" not in res2["results"][0]

    res3 = query_core.execute_query(mini_index, query_text="Readme", k=5)
    assert len(res3["results"]) == 1
    assert "range_ref" not in res3["results"][0]
    assert "derived_range_ref" not in res3["results"][0]

def test_query_range_ref(tmp_path):
    from merger.lenskit.retrieval import index_db
    import json

    db_path = tmp_path / "index.sqlite"
    dump_path = tmp_path / "dump.json"
    chunk_path = tmp_path / "chunks.jsonl"

    ref_obj = {
        "artifact_role": "canonical_md",
        "repo_id": "r1",
        "file_path": "merged.md",
        "start_byte": 0,
        "end_byte": 10,
        "start_line": 1,
        "end_line": 1,
        "content_sha256": "h1"
    }

    chunk_data = [
        {
            "chunk_id": "c1", "repo_id": "r1", "path": "src/main.py", "content": "def main(): print('hello')",
            "start_line": 1, "end_line": 1, "layer": "core", "artifact_type": "code", "content_sha256": "h1",
            "content_range_ref": ref_obj,
            "start_byte": 0, "end_byte": 10, "source_file": "src/main.py"
        }
    ]
    with chunk_path.open("w", encoding="utf-8") as f:
        for c in chunk_data:
            f.write(json.dumps(c) + "\n")

    dump_path.write_text(json.dumps({"dummy": "data"}))
    index_db.build_index(dump_path, chunk_path, db_path)

    res = query_core.execute_query(db_path, query_text="hello", k=1)
    hit = res["results"][0]

    assert "range_ref" in hit
    assert hit["range_ref"] == ref_obj

def test_query_semantic_markers(mini_index):
    policy = {
        "model_name": "test-model",
        "provider": "api",
        "fallback_behavior": "ignore",
        "similarity_metric": "cosine",
        "dimensions": 128
    }

    res = query_core.execute_query(mini_index, query_text="def", k=2, embedding_policy=policy)

    assert res["engine"] == "fts5+semantic_requested"
    assert res["count"] == 2 # Should find c1 and c2

    # Check diagnostic markers
    hit = res["results"][0]
    assert "diagnostics" in hit["why"]
    semantic_diag = hit["why"]["diagnostics"]["semantic"]
    assert semantic_diag["enabled"] is False
    assert semantic_diag["fallback_behavior"] == "ignore"
    assert "not implemented" in semantic_diag["error"]
    assert semantic_diag["candidate_k"] == 50  # Overfetch logic triggers
    assert semantic_diag["provider"] == "api"
    assert semantic_diag["model_name"] == "test-model"

def test_query_explain(mini_index):
    res = query_core.execute_query(mini_index, query_text="hello", k=10, explain=True)
    assert "explain" in res
    explain = res["explain"]
    assert "fts_query" in explain
    assert explain["fts_query"] == "hello"
    assert "top_k_scoring" in explain
    assert len(explain["top_k_scoring"]) == 1
    assert explain["top_k_scoring"][0]["chunk_id"] == "c1"

def test_query_explain_zero_hits(mini_index):
    res = query_core.execute_query(mini_index, query_text="zebra", k=10, filters={"layer": "core"}, explain=True)
    assert "explain" in res
    explain = res["explain"]
    assert "fts_query" in explain
    assert explain["filters"]["layer"] == "core"
    assert "why_zero" in explain
    assert explain["why_zero"] == query_core.WHY_ZERO_TOKENS

def test_query_semantic_fallback_fail(mini_index):
    policy = {
        "model_name": "test-model",
        "provider": "api",
        "fallback_behavior": "fail",
        "similarity_metric": "cosine",
        "dimensions": 128
    }

    with pytest.raises(RuntimeError) as excinfo:
        query_core.execute_query(mini_index, query_text="def", k=2, embedding_policy=policy)

    assert "Semantic re-ranking provider 'api' is not yet implemented (fallback_behavior=fail)" in str(excinfo.value)


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

def test_explain_json_stable_order(mini_index):
    """
    Golden Test: Ensure Explain JSON output has a stable prefix order (fts_query, filters) and required keys present.
    Dictionaries in Python 3.7+ maintain insertion order. We enforce the required schema fields
    to ensure the output matches expected 'Golden' prefix ordering.
    """
    res = query_core.execute_query(
        index_path=mini_index,
        query_text="hello",
        k=5,
        filters={"layer": "core"},
        explain=True
    )

    assert "explain" in res
    explain = res["explain"]

    actual_keys = list(explain.keys())

    assert actual_keys[:2] == ["fts_query", "filters"], f"Prefix order mismatch: {actual_keys[:2]} != ['fts_query', 'filters']"
    assert "top_k_scoring" in actual_keys, "Missing 'top_k_scoring'"

    # For zero results
    res_zero = query_core.execute_query(
        index_path=mini_index,
        query_text="zebra",
        k=5,
        filters={"layer": "core"},
        explain=True
    )

    explain_zero = res_zero["explain"]
    actual_zero_keys = list(explain_zero.keys())

    assert actual_zero_keys[:2] == ["fts_query", "filters"], f"Prefix order mismatch: {actual_zero_keys[:2]} != ['fts_query', 'filters']"
    assert "why_zero" in actual_zero_keys, "Missing 'why_zero'"

def test_cmd_query_json_emit(mini_index, capsys):
    from merger.lenskit.cli import cmd_query
    import argparse

    args = argparse.Namespace(
        index=str(mini_index),
        q="hello",
        k=10,
        repo=None, path=None, ext=None, layer=None, artifact_type=None,
        emit="json",
        stale_policy="ignore",
        embedding_policy=None,
        explain=True,
        graph_index=None,
        graph_weights=None,
        test_penalty=0.75
    )
    ret = cmd_query.run_query(args)
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.err == "", f"Expected empty stderr, got: {captured.err}"
    parsed = json.loads(captured.out)
    assert isinstance(parsed, dict)
    assert "results" in parsed
    assert "explain" in parsed

def test_query_semantic_reranking(mini_index, monkeypatch):
    # Create a mock semantic model that produces deterministic vectors
    class MockSemanticModel:
        def encode(self, texts):
            # If input is string, make it list-like for uniform processing
            is_single = isinstance(texts, str)
            if is_single: texts = [texts]

            embeddings = []
            for t in texts:
                t = t.lower()
                # Determine mock vectors based on content to force order
                if "test_main" in t:
                    embeddings.append([1.0, 0.0])
                elif "print" in t:
                    embeddings.append([0.0, 1.0])
                elif t == "def":
                    # query returns [1.0, 0.0], matching test_main best
                    embeddings.append([1.0, 0.0])
                else:
                    embeddings.append([0.5, 0.5])

            return embeddings[0] if is_single else embeddings

    def mock_get_semantic_model(name):
        return MockSemanticModel()

    monkeypatch.setattr("merger.lenskit.retrieval.query_core._get_semantic_model", mock_get_semantic_model)

    policy = {
        "model_name": "mock-model",
        "provider": "local",
        "fallback_behavior": "fail",
        "similarity_metric": "cosine",
        "dimensions": 2
    }

    # Baseline: both matches have 'def'. The SQLite query will return them in DB order.
    res_base = query_core.execute_query(mini_index, query_text="def", k=2, explain=True)
    assert res_base["count"] == 2
    base_order = [h["path"] for h in res_base["results"]]

    # We query "def", which matches both chunks lexically.
    # The mock semantic model encodes "def" as [1.0, 0.0].
    # It encodes the content of "tests/test_main.py" (containing "test_main") as [1.0, 0.0].
    # It encodes the content of "src/main.py" (containing "print") as [0.0, 1.0].
    # This forces the semantic similarity to be 1.0 for test_main and 0.0 for main,
    # effectively reranking test_main to the top regardless of baseline DB tie-breaking.

    res_sem = query_core.execute_query(mini_index, query_text="def", k=2, embedding_policy=policy, explain=True)

    assert res_sem["count"] == 2
    sem_order = [h["path"] for h in res_sem["results"]]
    top_hit = res_sem["results"][0]
    second_hit = res_sem["results"][1]

    # Explicitly assert that the semantic reranking altered the order compared to baseline.
    assert base_order != sem_order, "Semantic reranking failed to change the baseline FTS DB order."

    # Assert deterministic ranking outcome
    assert top_hit["path"] == "tests/test_main.py"
    assert second_hit["path"] == "src/main.py"

    # Assert presence of required metrics in explain/why block
    assert "semantic_score" in top_hit["why"]["rank_features"]
    assert "original_bm25" in top_hit["why"]["rank_features"]

    # Assert semantic score logic is correctly calculated by the mock fallback
    assert top_hit["why"]["rank_features"]["semantic_score"] > second_hit["why"]["rank_features"]["semantic_score"]

def test_graph_schema_validation(tmp_path):
    from merger.lenskit.architecture.graph_index import load_graph_index
    graph_path = tmp_path / "bad_graph.json"

    # Missing required field 'version'
    bad_data = {
        "kind": "lenskit.architecture.graph_index",
        "run_id": "r1",
        "canonical_dump_index_sha256": "a" * 64,
        "distances": {},
        "metrics": {"entrypoint_count": 0, "nodes_reachable": 0, "unreachable_nodes": 0}
    }
    graph_path.write_text(json.dumps(bad_data))

    res = load_graph_index(graph_path)
    assert res["status"] == "invalid_schema"
    assert res["graph"] is None

def test_graph_loader_normalizes_and_rejects_invalid(tmp_path):
    from merger.lenskit.architecture.graph_index import load_graph_index

    # Missing file
    res = load_graph_index(tmp_path / "missing.json")
    assert res["status"] == "not_found"
    assert res["graph"] is None

    # Invalid JSON
    bad_json_path = tmp_path / "bad.json"
    bad_json_path.write_text("{bad json")
    res = load_graph_index(bad_json_path)
    assert res["status"] == "invalid_json"
    assert res["graph"] is None

def test_missing_graph_is_explicitly_reported(mini_index, tmp_path):
    res = query_core.execute_query(
        mini_index,
        query_text="def",
        k=2,
        graph_index_path=tmp_path / "missing_graph.json",
        explain=True
    )

    hit = res["results"][0]
    assert "graph_explain" in hit["why"]
    assert hit["why"]["graph_explain"]["graph_used"] is False
    assert hit["why"]["graph_explain"]["graph_status"] == "not_found"

def test_query_explain_graph_fields_match_scoring(mini_index, tmp_path):
    valid_graph = {
        "kind": "lenskit.architecture.graph_index",
        "version": "1.0",
        "run_id": "r1",
        "canonical_dump_index_sha256": "a" * 64,
        "distances": {"file:src/main.py": 0, "file:tests/test_main.py": 1},
        "metrics": {"entrypoint_count": 1, "nodes_reachable": 2, "unreachable_nodes": 0}
    }
    graph_path = tmp_path / "valid_graph.json"
    graph_path.write_text(json.dumps(valid_graph))

    res = query_core.execute_query(
        mini_index,
        query_text="def",
        k=2,
        graph_index_path=graph_path,
        explain=True
    )

    # "def" matches both. test_main.py gets test penalty, main.py gets entrypoint boost
    assert res["count"] == 2

    for hit in res["results"]:
        assert "graph_explain" in hit["why"]
        assert hit["why"]["graph_explain"]["graph_used"] is True
        assert hit["why"]["graph_explain"]["graph_status"] == "ok"

        if hit["path"] == "src/main.py":
            assert hit["why"]["graph_explain"]["distance"] == 0
            assert hit["why"]["graph_explain"]["graph_bonus"] > 0
            assert "near_entry" in hit["why_list"]
            assert "entrypoint_boost" in hit["why_list"]
        elif hit["path"] == "tests/test_main.py":
            assert hit["why"]["graph_explain"]["distance"] == 1
            assert "near_entry" in hit["why_list"]

def test_graph_staleness_marker(mini_index, tmp_path):
    valid_graph = {
        "kind": "lenskit.architecture.graph_index",
        "version": "1.0",
        "run_id": "r1",
        "canonical_dump_index_sha256": "a" * 64,
        "distances": {"file:src/main.py": 0},
        "metrics": {"entrypoint_count": 1, "nodes_reachable": 1, "unreachable_nodes": 0}
    }
    graph_path = tmp_path / "valid_graph.json"
    graph_path.write_text(json.dumps(valid_graph))

    res = query_core.execute_query(
        mini_index,
        query_text="def",
        k=2,
        graph_index_path=graph_path,
        expected_graph_sha256="b" * 64,  # mismatched sha256
        explain=True
    )

    hit = res["results"][0]
    assert hit["why"]["graph_explain"]["graph_status"] == "stale_or_mismatched"

def test_graph_bonus_is_bounded(mini_index, tmp_path):
    valid_graph = {
        "kind": "lenskit.architecture.graph_index",
        "version": "1.0",
        "run_id": "r1",
        "canonical_dump_index_sha256": "a" * 64,
        "distances": {"file:src/main.py": 0},
        "metrics": {"entrypoint_count": 1, "nodes_reachable": 1, "unreachable_nodes": 0}
    }
    graph_path = tmp_path / "valid_graph.json"
    graph_path.write_text(json.dumps(valid_graph))

    res = query_core.execute_query(
        mini_index,
        query_text="def",
        k=2,
        graph_index_path=graph_path,
        explain=True
    )

    hit = res["results"][0]
    if hit["path"] == "src/main.py":
        rf = hit["why"]["rank_features"]
        # The graph bonus must be bounded by the cap
        assert rf["graph_bonus"] <= (0.5 * rf["bm25_norm"] + 0.001)
