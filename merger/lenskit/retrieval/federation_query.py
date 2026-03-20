import json
from pathlib import Path
from typing import Dict, Any, Optional

from .query_core import execute_query
from ..core.federation import validate_federation

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
    Executes a minimal federated query aggregation across local bundles referenced by a federation index.
    This is not a full federated ranking system, but a fan-out mechanism that collects results and sorts them globally.
    """
    if not federation_index_path.exists():
        raise FileNotFoundError(f"Federation index not found at: {federation_index_path.resolve().as_posix()}")

    # Diagnose-Gate: Validate structural integrity before accessing keys to avoid KeyErrors mid-flight.
    # This is a deliberate safety check for the minimal fan-out, not intended as a highly optimized performance model.
    validate_federation(federation_index_path)

    with federation_index_path.open("r", encoding="utf-8") as f:
        fed_data = json.load(f)

    bundles = fed_data.get("bundles", [])

    all_results = []
    bundle_traces = {}
    bundle_status = {}
    bundle_errors = {}

    queried_bundles_total = len(bundles)
    queried_bundles_effective = 0

    # repo-Filter wird auf Federation-Ebene angewendet und nicht an execute_query
    # weitergereicht, um doppelte Ausführung und Fehler zu vermeiden, falls lokale Repos
    # andere IDs verwenden. Andere Filter werden normal durchgereicht.
    local_filters = None
    if filters:
        local_filters = {k: v for k, v in filters.items() if k != "repo"}

    for b in bundles:
        repo_id = b["repo_id"]
        bundle_path_str = b["bundle_path"]

        if filters and filters.get("repo") and filters["repo"] != repo_id:
            bundle_status[repo_id] = "filtered_out"
            continue

        if "://" in bundle_path_str:
            bundle_status[repo_id] = "bundle_path_unsupported"
            continue

        bundle_path = Path(bundle_path_str)
        db_path = bundle_path / "chunk_index.index.sqlite"
        if not db_path.exists():
            bundle_status[repo_id] = "index_missing"
            continue

        try:
            res = execute_query(
                index_path=db_path,
                query_text=query_text,
                k=k,  # Fetch up to k from each bundle to ensure global top-k is accurate
                filters=local_filters,
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
            queried_bundles_effective += 1
            if trace and "query_trace" in res:
                bundle_traces[repo_id] = res["query_trace"]

        except Exception as e:
            bundle_status[repo_id] = "query_error"
            bundle_errors[repo_id] = str(e)

    # Global sort: final_score descending
    # Tie-breakers: federation_bundle asc, path asc, chunk_id asc to ensure deterministic tie ordering
    all_results.sort(key=lambda x: (
        -x.get("final_score", 0),
        x.get("federation_bundle", ""),
        x.get("path", ""),
        x.get("chunk_id", "")
    ))
    top_k = all_results[:k]

    # In a future expansion, it may be useful to separate `total_candidates_found` (across all bundles)
    # from `returned_results` (len(top_k)), but for now count reflects the final sliced result length.
    out = {
        "query": query_text,
        "k": k,
        "count": len(top_k),  # Refers to the returned top-k results after global slice, not total hits across all bundles
        "results": top_k,
        "federation_id": fed_data.get("federation_id", "<unknown>")
    }

    if trace:
        out["federation_trace"] = {
            "queried_bundles_total": queried_bundles_total,
            "queried_bundles_effective": queried_bundles_effective,
            "bundle_status": bundle_status,
            "bundle_errors": bundle_errors,
            "bundle_traces": bundle_traces
        }

    return out
