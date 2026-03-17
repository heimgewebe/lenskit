import json
from pathlib import Path
from typing import Dict, Any, Optional

from .query_core import execute_query

def execute_federated_query(
    federation_index_path: Path,
    query_text: str,
    k: int = 10,
    filters: Optional[Dict[str, Optional[str]]] = None,
    embedding_policy: Optional[Dict[str, Any]] = None,
    explain: bool = False,
    trace: bool = False,
    build_context: bool = False
) -> Dict[str, Any]:
    """
    Executes a query across all bundles defined in a federation index.
    Results are globally sorted.
    """
    if not federation_index_path.exists():
        raise FileNotFoundError(f"Federation index not found at: {federation_index_path.resolve().as_posix()}")

    with federation_index_path.open("r", encoding="utf-8") as f:
        fed_data = json.load(f)

    bundles = fed_data.get("bundles", [])

    all_results = []
    bundle_traces = {}
    bundle_status = {}

    for b in bundles:
        repo_id = b["repo_id"]
        bundle_path = Path(b["bundle_path"])

        # Optional: apply repo filter early
        if filters and filters.get("repo") and filters["repo"] != repo_id:
            continue

        db_path = bundle_path / "chunk_index.index.sqlite"
        if not db_path.exists():
            bundle_status[repo_id] = "index_missing"
            continue

        try:
            # We don't want to pass `repo` filter to execute_query if we already filtered
            # by bundle, as it might conflict if the query_core expects it to match `c.repo_id`.
            # But the chunk index typically has the correct repo_id anyway.
            # However, if `repo_id` in chunk index differs from `repo_id` in federation, it might break.
            # Assuming they match or the filter is safe:
            res = execute_query(
                index_path=db_path,
                query_text=query_text,
                k=k,  # Fetch up to k from each bundle to ensure global top-k is accurate
                filters=filters,
                embedding_policy=embedding_policy,
                explain=explain,
                trace=trace,
                build_context=build_context
            )

            # Tag results with bundle origin (Provenance)
            for hit in res.get("results", []):
                hit["federation_bundle"] = repo_id
                all_results.append(hit)

            bundle_status[repo_id] = "ok"
            if trace and "query_trace" in res:
                bundle_traces[repo_id] = res["query_trace"]

        except Exception as e:
            bundle_status[repo_id] = f"error: {str(e)}"

    # Global sort: final_score descending
    all_results.sort(key=lambda x: (-x.get("final_score", 0), x.get("path", "")))
    top_k = all_results[:k]

    out = {
        "query": query_text,
        "k": k,
        "count": len(top_k),
        "results": top_k,
        "federation_id": fed_data.get("federation_id", "<unknown>")
    }

    if trace:
        out["federation_trace"] = {
            "bundle_status": bundle_status,
            "bundle_traces": bundle_traces
        }

    return out
