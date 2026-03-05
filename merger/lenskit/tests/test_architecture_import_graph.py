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

    # 2. Assert values against Golden Snapshot
    expected_path = Path(__file__).parent / "fixtures" / "architecture_import_graph" / "expected.graph.json"
    with open(expected_path, "r", encoding="utf-8") as f:
        expected = json.load(f)

    # Mask variable fields before equality check
    doc["generated_at"] = "2024-01-01T00:00:00Z"
    expected["run_id"] = "test_run_123"

    assert doc == expected
