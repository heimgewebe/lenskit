import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging
try:
    import jsonschema
except ImportError:
    jsonschema = None

logger = logging.getLogger(__name__)

def load_graph_index(path: Path, expected_sha256: Optional[str] = None) -> Dict[str, Any]:
    """
    Loads and validates a graph index.
    Returns a dict with 'status' (ok, not_found, invalid_json, invalid_schema, stale_or_mismatched, unreadable)
    and 'graph' (the loaded dict, if successful).
    """
    if not path.exists():
        return {"status": "not_found", "graph": None}

    try:
        with path.open() as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return {"status": "invalid_json", "graph": None}
    except OSError as e:
        logger.warning("Graph index file unreadable: %s", e)
        return {"status": "unreadable", "graph": None}

    # Validate against schema
    schema_path = Path(__file__).parent.parent / "contracts" / "architecture.graph_index.v1.schema.json"
    if schema_path.exists():
        if jsonschema is None:
            logger.warning("Schema validation skipped because jsonschema is unavailable in this environment.")
        else:
            try:
                with schema_path.open() as f:
                    schema = json.load(f)
                jsonschema.validate(instance=data, schema=schema)
            except jsonschema.ValidationError as e:
                logger.warning("Graph index schema validation failed: %s", e)
                return {"status": "invalid_schema", "graph": None}
            except Exception as e:
                logger.error("Error reading/validating graph schema: %s", e)
                return {"status": "invalid_schema", "graph": None}

    # Check staleness if expected_sha256 is provided
    if expected_sha256:
        graph_sha = data.get("canonical_dump_index_sha256")
        if not graph_sha or graph_sha != expected_sha256:
            return {"status": "stale_or_mismatched", "graph": data}

    return {"status": "ok", "graph": data}

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
    node_meta_by_id = {}

    for n in graph.get("nodes", []):
        node_id = n["node_id"]
        adjacency[node_id] = []
        node_meta_by_id[node_id] = n
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

    # Calculate reachable and unreachable metrics based only on real graph nodes
    reachable_nodes = sum(1 for node_id in adjacency.keys() if distances.get(node_id, -1) != -1)
    unreachable_nodes = len(adjacency) - reachable_nodes

    # Populate output dictionary
    for node_id in adjacency.keys():
        dist = distances.get(node_id, -1)
        index["distances"][node_id] = dist

        # Inject an alias 'file:<path>' mapped to the same distance if it differs from node_id.
        # This bridges the format between the generic architecture graph and the query_core consumer.
        path = node_meta_by_id.get(node_id, {}).get("path")
        if path:
            file_key = f"file:{path}"
            if file_key != node_id:
                index["distances"][file_key] = dist

    reachable = reachable_nodes
    unreachable = unreachable_nodes

    index["metrics"]["nodes_reachable"] = reachable
    index["metrics"]["unreachable_nodes"] = unreachable

    return index
