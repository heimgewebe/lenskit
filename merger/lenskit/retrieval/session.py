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
        # 1. Backwards compatible top-level repo_id
        if "repo_id" in hit and isinstance(hit["repo_id"], str):
            resolved_bundles.add(hit["repo_id"])
        # 2. Epistemics bundle_origin (Context-Bundle.v1 contract)
        elif "epistemics" in hit and isinstance(hit["epistemics"], dict):
            bundle_origin = hit["epistemics"].get("bundle_origin")
            if bundle_origin and isinstance(bundle_origin, str):
                resolved_bundles.add(bundle_origin)
        # 3. Explicit range_ref repo_id
        elif "range_ref" in hit and isinstance(hit["range_ref"], dict):
            repo_id = hit["range_ref"].get("repo_id")
            if repo_id and isinstance(repo_id, str):
                resolved_bundles.add(repo_id)

    # 4. Extract from federation_trace.v1 contract
    if "federation_trace" in result and "bundles" in result["federation_trace"]:
        for bundle in result["federation_trace"]["bundles"]:
            if bundle.get("status") == "ok" and "repo_id" in bundle and isinstance(bundle["repo_id"], str):
                resolved_bundles.add(bundle["repo_id"])

    warnings: List[str] = []
    if "warnings" in result:
        warnings = result["warnings"]

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
