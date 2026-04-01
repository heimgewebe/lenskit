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


def build_agent_query_session(
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
        A dict conforming to agent-query-session.v1.schema.json.
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
