from __future__ import annotations

import json
from pathlib import Path

TASK_ID = "TASK-GRAPH-RESOLUTION-LAYERS-001"

board_path = Path("docs/tasks/board.md")
board = board_path.read_text(encoding="utf-8")
if TASK_ID not in board:
    board_path.write_text(
        board.rstrip()
        + "\n| TASK-GRAPH-RESOLUTION-LAYERS-001 | Unique Local Import Resolution and Path Layers | done | `merger/lenskit/architecture/import_graph.py`, `merger/lenskit/tests/{test_architecture_import_graph,test_graph_quality_goldset}.py`, `docs/diagnostics/graph-quality-baseline.{md,v1.json}`, `docs/proofs/graph-local-resolution-layers-proof.md` | G4a resolves only uniquely mapped repository-relative Python modules, preserves ambiguous/external modules, and assigns conservative path-segment layers. Goldset: local 4/4, external 2/2, layers 6/6. No runtime-causality, graph-completeness, retrieval-benefit, or default-ranking claim. |\n",
        encoding="utf-8",
    )

index_path = Path("docs/tasks/index.json")
data = json.loads(index_path.read_text(encoding="utf-8"))
if not any(task.get("id") == TASK_ID for task in data["tasks"]):
    data["tasks"].append(
        {
            "id": TASK_ID,
            "title": "Unique Local Import Resolution and Path Layers",
            "status": "done",
            "description": "Implements measured G4a producer improvements: uniquely mapped repository-relative Python modules become local file edges, ambiguous and unavailable modules remain external, and deterministic path-segment layers cover test, cli, core and infrastructure files.",
            "evidence": [
                "merger/lenskit/architecture/import_graph.py",
                "merger/lenskit/tests/test_architecture_import_graph.py",
                "merger/lenskit/tests/fixtures/architecture_import_graph/expected.graph.json",
                "merger/lenskit/tests/test_graph_quality_goldset.py",
                "docs/diagnostics/graph-quality-baseline.v1.json",
                "docs/diagnostics/graph-quality-baseline.md",
                "docs/proofs/graph-local-resolution-layers-proof.md",
            ],
            "missing_evidence": [
                "The synthetic v1 goldset is not representative of all Python packaging layouts.",
                "src layouts, namespace packages and broader layer ontology require new falsifiable cases before implementation.",
                "No runtime import order, runtime causality, graph completeness, retrieval benefit, impact, test sufficiency or default-ranking claim is established.",
            ],
        }
    )
    index_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
