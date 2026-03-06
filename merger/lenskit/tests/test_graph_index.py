import json
from pathlib import Path
from merger.lenskit.architecture.graph_index import compile_graph_index

def test_compile_graph_index(tmp_path):
    graph = {
        "run_id": "test",
        "canonical_dump_index_sha256": "0"*64,
        "nodes": [
            {"node_id": "ep1", "path": "main.py"},
            {"node_id": "util", "path": "util.py"},
            {"node_id": "unreach", "path": "unreach.py"}
        ],
        "edges": [
            {"src": "ep1", "dst": "util"}
        ]
    }

    entrypoints = {
        "entrypoints": [
            {"path": "main.py"}
        ]
    }

    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph))

    eps_path = tmp_path / "entrypoints.json"
    eps_path.write_text(json.dumps(entrypoints))

    idx = compile_graph_index(graph_path, eps_path)

    assert idx["metrics"]["entrypoint_count"] == 1
    assert idx["distances"]["ep1"] == 0
    assert idx["distances"]["util"] == 1
    assert idx["distances"]["unreach"] == -1
