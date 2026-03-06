import json
from pathlib import Path
from merger.lenskit.architecture.import_graph import generate_import_graph_document

repo_root = Path("merger/lenskit/tests/fixtures/architecture_import_graph")
run_id = "test_run_123"
canonical_sha256 = "0" * 64

doc = generate_import_graph_document(repo_root, run_id, canonical_sha256)
doc["generated_at"] = "2024-01-01T00:00:00Z"

expected_path = repo_root / "expected.graph.json"
with open(expected_path, "w", encoding="utf-8") as f:
    json.dump(doc, f, indent=2)

print("Snapshot updated!")
