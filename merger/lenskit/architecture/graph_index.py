import json
from pathlib import Path
from typing import Dict, Any, Set, List
import logging

logger = logging.getLogger(__name__)

def compile_graph_index(graph_path: Path, entrypoints_path: Path) -> Dict[str, Any]:
    with graph_path.open() as f:
        graph = json.load(f)

    with entrypoints_path.open() as f:
        entrypoints = json.load(f)

    index = {
        "kind": "lenskit.architecture.graph_index",
        "version": "1.0",
        "run_id": graph.get("run_id", ""),
        "canonical_dump_index_sha256": graph.get("canonical_dump_index_sha256", ""),
        "distances": {},
        "metrics": {
            "entrypoint_count": 0,
            "nodes_reachable": 0,
            "unreachable_nodes": 0
        }
    }

    adjacency = {}
    nodes_by_path = {}

    for n in graph.get("nodes", []):
        node_id = n["node_id"]
        adjacency[node_id] = []
        path = n.get("path")
        if path:
            nodes_by_path[path] = node_id

    for e in graph.get("edges", []):
        src = e["src"]
        dst = e["dst"]
        if src in adjacency:
            adjacency[src].append(dst)

    entrypoint_nodes = set()
    for ep in entrypoints.get("entrypoints", []):
        path = ep.get("path")
        if path and path in nodes_by_path:
            entrypoint_nodes.add(nodes_by_path[path])

    index["metrics"]["entrypoint_count"] = len(entrypoint_nodes)

    distances = {}
    queue = []

    for ep in entrypoint_nodes:
        distances[ep] = 0
        queue.append(ep)

    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1

        current_dist = distances[current]

        for neighbor in adjacency.get(current, []):
            if neighbor not in distances:
                distances[neighbor] = current_dist + 1
                queue.append(neighbor)

    for node_id in adjacency.keys():
        index["distances"][node_id] = distances.get(node_id, -1)

    reachable = sum(1 for d in index["distances"].values() if d != -1)
    unreachable = len(adjacency) - reachable

    index["metrics"]["nodes_reachable"] = reachable
    index["metrics"]["unreachable_nodes"] = unreachable

    return index
