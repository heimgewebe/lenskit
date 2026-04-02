from pathlib import Path
"""
Agent query session builder.

Builds a structured session object from a query result, combining information
from a projected context_bundle and/or a federation_trace.

Design notes:
- resolved_bundles is extracted from context_bundle.hits[*].epistemics.bundle_origin
  (a string, never an object — confirmed by query-context-bundle.v1.schema.json and
  query_core.py:build_context_bundle()).
- federation_trace.bundle_status is a dict {repo_id: status_str}; there is no
  queried_bundles list. Successfully queried bundles have status "ok" or "stale"
  (stale bundles still ran the query against their potentially outdated index).
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Bundle status values that mean the query actually executed against that bundle.
_SUCCESSFUL_BUNDLE_STATUSES = frozenset({"ok", "stale"})


def build_agent_query_session_v2(
    query: str,
    context_bundle: Optional[Dict[str, Any]] = None,
    federation_trace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Builds a minimal agent query session from a query result.

    Extracts resolved_bundles — the unique set of bundle/repo identifiers that
    contributed hits or were successfully queried — from the two canonical sources:

    1. context_bundle.hits[*].epistemics.bundle_origin (string) for projected results.
    2. federation_trace.bundle_status keys where status is "ok" or "stale".

    Args:
        query: The original query text.
        context_bundle: Optional projected context bundle (from execute_query /
            execute_federated_query with build_context=True).
        federation_trace: Optional federation execution trace (from
            execute_federated_query with trace=True).

    Returns:
        A dict conforming to agent-query-session.v2.schema.json.
    """
    resolved: List[str] = []

    # Source 1: bundle origins from context bundle hits.
    # epistemics.bundle_origin is a string set by build_context_bundle():
    #   "bundle_origin": hit.get("repo_id", "local")
    if context_bundle is not None:
        for hit in context_bundle.get("hits", []):
            origin = hit.get("epistemics", {}).get("bundle_origin")
            if origin and isinstance(origin, str):
                resolved.append(origin)

    # Source 2: successfully queried bundles from the federation trace.
    # federation_trace.bundle_status is a dict {repo_id: status_str}.
    # "ok" = query ran and returned results (possibly empty).
    # "stale" = query ran against an outdated index — still counts as resolved.
    if federation_trace is not None:
        bundle_status = federation_trace.get("bundle_status", {})
        if not isinstance(bundle_status, dict):
            logger.warning(
                "federation_trace.bundle_status is not a dict (got %s); skipping",
                type(bundle_status).__name__,
            )
        else:
            for repo_id, status in bundle_status.items():
                if status in _SUCCESSFUL_BUNDLE_STATUSES and isinstance(repo_id, str) and repo_id:
                    resolved.append(repo_id)

    # Deduplicate and sort for determinism.
    resolved_bundles = sorted(set(resolved))

    # Determine context source for observability.
    has_projected = context_bundle is not None
    has_federated = federation_trace is not None
    if has_projected and has_federated:
        context_source = "both"
    elif has_projected:
        context_source = "projected"
    elif has_federated:
        context_source = "federated"
    else:
        context_source = "none"

    hits_count = len(context_bundle.get("hits", [])) if context_bundle is not None else 0

    session_meta: Dict[str, Any] = {"context_source": context_source}
    if federation_trace is not None:
        session_meta["federation_bundle_count"] = federation_trace.get("queried_bundles_total")
        session_meta["federation_effective_count"] = federation_trace.get("queried_bundles_effective")
    else:
        session_meta["federation_bundle_count"] = None
        session_meta["federation_effective_count"] = None

    return {
        "query": query,
        "resolved_bundles": resolved_bundles,
        "hits_count": hits_count,
        "session_meta": session_meta,
    }


def build_agent_query_session(
    request_contract: Dict[str, Any],
    result: Dict[str, Any],
    query_trace_ref: Optional[str] = None,
    context_bundle_ref: Optional[str] = None,
    diagnostics_ref: Optional[str] = None,
    out_dir: Optional[Path] = None,
    index_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Builds the formal agent_query_session.json artifact from query execution results.

    This function adheres to the agent_query_session.v1 contract and strictly extracts
    resolved bundles and warnings from the provided result without inventing references.

    DEPRECATED: Use build_agent_query_session_v2 for the v2 schema.
    """
    import importlib.metadata
    from datetime import datetime, timezone
    import hashlib

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

    # Calculate integrity hashes
    integrity = {
        "query_trace_sha256": None,
        "context_bundle_sha256": None
    }

    base_dir = out_dir if out_dir else Path.cwd()

    if query_trace_ref:
        trace_path = base_dir / query_trace_ref
        try:
            if trace_path.exists():
                integrity["query_trace_sha256"] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
        except OSError:
            pass

    if context_bundle_ref:
        bundle_path = base_dir / context_bundle_ref
        try:
            if bundle_path.exists():
                integrity["context_bundle_sha256"] = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
        except OSError:
            pass

    try:
        lenskit_version = importlib.metadata.version("lenskit")
    except importlib.metadata.PackageNotFoundError:
        lenskit_version = "unknown"

    environment = {
        "lenskit_version": lenskit_version,
        "index_path": index_path,
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }

    session = {
        "request": request_contract,
        "resolved_bundles": sorted(list(resolved_bundles)),
        "refs": {
            "query_trace_ref": query_trace_ref,
            "context_bundle_ref": context_bundle_ref,
            "diagnostics_ref": diagnostics_ref,
            "integrity": integrity
        },
        "warnings": warnings,
        "environment": environment
    }

    return session
