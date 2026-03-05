import ast
import os
import logging
from typing import TypedDict, List, Dict, Optional, Literal, Set
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class Evidence(TypedDict, total=False):
    source_path: str
    start_line: int
    end_line: int
    extract: str

class Edge(TypedDict):
    src: str
    dst: str
    edge_type: Literal["import", "require", "config-link", "string-ref", "call-heuristic"]
    evidence_level: Literal["S0", "S1", "S2"]
    evidence: Evidence

class Node(TypedDict, total=False):
    node_id: str
    kind: Literal["file", "package", "module", "external"]
    path: str
    repo: str
    language: str
    layer: str
    is_test: bool
    size_bytes: int

class Coverage(TypedDict):
    files_seen: int
    files_parsed: int
    edge_counts_by_type: Dict[str, int]
    unknown_layer_share: float

class GraphDocument(TypedDict, total=False):
    kind: Literal["lenskit.architecture.graph"]
    version: Literal["1.0"]
    run_id: str
    canonical_dump_index_sha256: str
    generated_at: str
    granularity: str
    nodes: List[Node]
    edges: List[Edge]
    coverage: Coverage


def _is_test_file(path: str) -> bool:
    name = Path(path).name
    return name.startswith("test_") or name.endswith("_test.py")

def _get_module_id(import_name: str) -> str:
    """Returns a deterministic node_id for an imported module."""
    # E.g. 'os.path' -> 'external:os.path' for external modules.
    # In a simple MVP, we treat all imported modules as external or local.
    # For simplicity in this graph MVP, we prefix with 'module:'
    return f"module:{import_name}"


def generate_import_graph_document(
    repo_root: Path,
    run_id: str,
    canonical_dump_index_sha256: str
) -> GraphDocument:
    """
    Parses Python files in the given repository root via AST to build an import graph.
    Returns a JSON-serializable dict conforming to architecture.graph.v1.schema.json.
    """
    nodes: Dict[str, Node] = {}
    edges: List[Edge] = []

    files_seen = 0
    files_parsed = 0

    # We will build up nodes and edges while traversing.
    for root, dirs, files in os.walk(repo_root):
        # Exclude common directories to ignore
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'venv', 'env', 'node_modules')]

        for file in files:
            if file.endswith('.py'):
                files_seen += 1
                file_path = Path(root) / file
                rel_path = file_path.relative_to(repo_root).as_posix()

                try:
                    content = file_path.read_text(encoding='utf-8')
                    tree = ast.parse(content, filename=rel_path)
                    files_parsed += 1
                except Exception as e:
                    logger.warning(f"Could not parse AST for {rel_path}: {e}")
                    continue

                # Register the file as a node
                node_id = f"file:{rel_path}"
                stat = file_path.stat()
                is_test = _is_test_file(rel_path)

                if node_id not in nodes:
                    nodes[node_id] = {
                        "node_id": node_id,
                        "kind": "file",
                        "path": rel_path,
                        "repo": "",  # In a full run, this is injected
                        "language": "python",
                        "layer": "unknown",
                        "is_test": is_test,
                        "size_bytes": stat.st_size
                    }

                # Find imports
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            dst_module = alias.name
                            dst_id = _get_module_id(dst_module)

                            # Add dst node if it doesn't exist
                            if dst_id not in nodes:
                                nodes[dst_id] = {
                                    "node_id": dst_id,
                                    "kind": "external",
                                    "path": "",
                                    "repo": "",
                                    "language": "python",
                                    "layer": "unknown",
                                    "is_test": False,
                                    "size_bytes": 0
                                }

                            evidence: Evidence = {
                                "source_path": rel_path,
                            }
                            if hasattr(node, 'lineno'):
                                evidence["start_line"] = node.lineno
                                evidence["end_line"] = getattr(node, 'end_lineno', node.lineno)

                            edges.append({
                                "src": node_id,
                                "dst": dst_id,
                                "edge_type": "import",
                                "evidence_level": "S1",
                                "evidence": evidence
                            })

                    elif isinstance(node, ast.ImportFrom):
                        # For relative imports (node.level > 0), we prefix dots for relative imports.
                        if node.module is not None:
                            dst_module = node.module
                            if node.level > 0:
                                dst_module = "." * node.level + dst_module
                        else:
                            # It's an import like `from . import b`, so the module names are in names
                            if node.level > 0:
                                dst_module = "." * node.level
                            else:
                                continue # Should not happen

                        # If we have a single module resolution, let's treat it as dst.
                        # For `from . import b, c`, the names list contains b and c.
                        # For `from os import path`, module is 'os'.
                        # Let's collect destinations:
                        destinations = []
                        if node.module is not None:
                            destinations.append(dst_module)
                        else:
                            for alias in node.names:
                                destinations.append(dst_module + alias.name)

                        for dest in destinations:
                            dst_id = _get_module_id(dest)

                            if dst_id not in nodes:
                                nodes[dst_id] = {
                                    "node_id": dst_id,
                                    "kind": "external",
                                    "path": "",
                                    "repo": "",
                                    "language": "python",
                                    "layer": "unknown",
                                    "is_test": False,
                                    "size_bytes": 0
                                }

                            evidence: Evidence = {
                                "source_path": rel_path,
                            }
                            if hasattr(node, 'lineno'):
                                evidence["start_line"] = node.lineno
                                evidence["end_line"] = getattr(node, 'end_lineno', node.lineno)

                            edges.append({
                                "src": node_id,
                                "dst": dst_id,
                                "edge_type": "import",
                                "evidence_level": "S1",
                                "evidence": evidence
                            })

    # Determinism: sort nodes and edges
    sorted_nodes = sorted(nodes.values(), key=lambda n: n["node_id"])
    sorted_edges = sorted(edges, key=lambda e: (e["src"], e["dst"], e["evidence"].get("start_line", 0)))

    # Coverage
    unknown_layer_count = sum(1 for n in sorted_nodes if n.get("layer") == "unknown")
    unknown_layer_share = (unknown_layer_count / len(sorted_nodes)) if sorted_nodes else 0.0

    edge_counts_by_type = {}
    for e in sorted_edges:
        edge_counts_by_type[e["edge_type"]] = edge_counts_by_type.get(e["edge_type"], 0) + 1

    coverage: Coverage = {
        "files_seen": files_seen,
        "files_parsed": files_parsed,
        "edge_counts_by_type": edge_counts_by_type,
        "unknown_layer_share": unknown_layer_share
    }

    if files_seen > 0 and files_parsed / files_seen < 0.5:
        logger.warning("Low AST parsing coverage: %.2f%%", (files_parsed / files_seen) * 100)

    doc: GraphDocument = {
        "kind": "lenskit.architecture.graph",
        "version": "1.0",
        "run_id": run_id,
        "canonical_dump_index_sha256": canonical_dump_index_sha256,
        "generated_at": datetime.now(timezone.utc).isoformat()[:19] + "Z",
        "granularity": "file",
        "nodes": sorted_nodes,
        "edges": sorted_edges,
        "coverage": coverage
    }

    return doc
