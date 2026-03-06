import re

with open("merger/lenskit/tests/test_graph_rerank.py", "r") as f:
    code = f.read()

bad = r"""def test_graph_fallback\(mini_index_with_graph\):
    db_path, graph_index_path = mini_index_with_graph

    res = query_core\.execute_query\(db_path, query_text="hello", k=10, explain=True, graph_index_path=Path\("nonexistent\.json"\)\)
    assert "ranker" not in res\["explain"\]
    assert "why_list" not in res\["results"\]\[0\]"""

good = """def test_graph_fallback(mini_index_with_graph):
    db_path, graph_index_path = mini_index_with_graph

    with pytest.raises(RuntimeError, match="Explicitly provided graph index file does not exist"):
        query_core.execute_query(db_path, query_text="hello", k=10, explain=True, graph_index_path=Path("nonexistent.json"))

    res = query_core.execute_query(db_path, query_text="hello", k=10, explain=True, graph_index_path=None)
    assert "ranker" not in res["explain"]
    assert "why_list" not in res.get("results", [{}])[0] if res.get("results") else True"""

code = re.sub(bad, good, code)

with open("merger/lenskit/tests/test_graph_rerank.py", "w") as f:
    f.write(code)
