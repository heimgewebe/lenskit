import json
from pathlib import Path
import jsonschema

from merger.lenskit.architecture.import_graph import generate_import_graph_document

def test_import_graph_generator():
    repo_root = Path(__file__).parent / "fixtures" / "architecture_import_graph"
    run_id = "test_run_123"
    canonical_sha256 = "0" * 64

    doc = generate_import_graph_document(repo_root, run_id, canonical_sha256)

    # 1. Validate structure against schema
    schema_path = Path(__file__).parent.parent / "contracts" / "architecture.graph.v1.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    jsonschema.validate(instance=doc, schema=schema)

    # 2. Assert values
    assert doc["kind"] == "lenskit.architecture.graph"
    assert doc["granularity"] == "file"

    # Coverage
    assert doc["coverage"]["files_seen"] == 2
    assert doc["coverage"]["files_parsed"] == 2

    # Nodes (a.py, b.py + external modules: os, sys, typing, json, logging)
    node_ids = [n["node_id"] for n in doc["nodes"]]
    assert "file:a.py" in node_ids
    assert "file:b.py" in node_ids
    assert "module:os" in node_ids
    assert "module:sys" in node_ids
    assert "module:typing" in node_ids
    assert "module:json" in node_ids
    assert "module:logging" in node_ids
    assert "module:.b" in node_ids

    # Determinism
    assert doc["nodes"] == sorted(doc["nodes"], key=lambda n: n["node_id"])
    assert doc["edges"] == sorted(doc["edges"], key=lambda e: (e["src"], e["dst"], e["evidence"].get("start_line", 0)))

    # Specific edges for a.py
    edges_from_a = [e for e in doc["edges"] if e["src"] == "file:a.py"]
    assert len(edges_from_a) == 5
    edge_a_os = next(e for e in edges_from_a if e["dst"] == "module:os")
    assert edge_a_os["evidence_level"] == "S1"
    assert edge_a_os["evidence"]["source_path"] == "a.py"
    assert edge_a_os["evidence"]["start_line"] == 1

    edge_a_b = next(e for e in edges_from_a if e["dst"] == "module:.b")
    assert edge_a_b["evidence"]["start_line"] == 3
