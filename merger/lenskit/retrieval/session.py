from typing import Dict, Any, List, Optional

def build_agent_query_session(
    request_contract: Dict[str, Any],
    result: Dict[str, Any],
    query_trace_ref: Optional[str] = None,
    context_bundle_ref: Optional[str] = None,
    diagnostics_ref: Optional[str] = None
) -> Dict[str, Any]:
    """
    Builds the formal agent_query_session.json artifact from query execution results.

    This function adheres to the agent_query_session.v1 contract and strictly extracts
    resolved bundles and warnings from the provided result without inventing references.
    """
    # 1. Extract resolved bundles (unique repo_ids from the results)
    resolved_bundles = set()

    # Depending on whether we're dealing with a raw result or a projected context_bundle
    hits = []
    if "context_bundle" in result and "hits" in result["context_bundle"]:
        hits = result["context_bundle"]["hits"]
    elif "hits" in result:
        # Projected directly to bundle
        hits = result["hits"]
    elif "results" in result:
        # Raw execute_query output
        hits = result["results"]

    for hit in hits:
        if "repo_id" in hit:
            resolved_bundles.add(hit["repo_id"])

    # Also check if it's a federated trace containing resolved bundles info
    if "federation_trace" in result and "queried_bundles" in result["federation_trace"]:
        for bundle in result["federation_trace"]["queried_bundles"]:
            if bundle.get("status") == "resolved" and "repo_id" in bundle:
                resolved_bundles.add(bundle["repo_id"])

    # 2. Extract warnings
    warnings: List[str] = []
    if "warnings" in result:
        warnings = result["warnings"]

    # 3. Assemble contract
    session = {
        "request": request_contract,
        "resolved_bundles": sorted(list(resolved_bundles)),
        "refs": {
            "query_trace_ref": query_trace_ref,
            "context_bundle_ref": context_bundle_ref,
            "diagnostics_ref": diagnostics_ref
        },
        "warnings": warnings
    }

    return session
