from typing import Dict, Any, Optional
import copy

def project_output(result: Dict[str, Any], output_profile: Optional[str] = None) -> Dict[str, Any]:
    """
    Applies the output profile projection to the query result.

    Response Contracts (enforced here and documented in docs/architecture/api_query_contracts.md):
    - Fall 1 (No Profile): Returns the raw result object (contains 'results' list, not 'hits').
    - Fall 2 (Profile specified, e.g. 'agent_minimal'): Returns the canonical Context-Bundle
      structure directly at the top level (contains 'hits' array).
    - Fall 3 (Profile + Trace): Returns a wrapper {"context_bundle": ..., "query_trace": ...}
      to ensure the strict Context-Bundle schema is not violated by the trace object.

    Args:
        result: The raw evaluation result from `execute_query`.
        output_profile: The desired projection form (e.g. "agent_minimal", "ui_navigation").

    Returns:
        The projected response dict conforming to the contract.
    """
    res = copy.deepcopy(result)

    if output_profile and "context_bundle" in res:
        bundle = res["context_bundle"]
        if output_profile == "agent_minimal":
            # Agent minimal strips explain blocks from individual hits and returns only essentials
            for hit in bundle.get("hits", []):
                hit.pop("explain", None)
                hit.pop("graph_context", None)
                if "surrounding_context" in hit and hit["surrounding_context"] is None:
                    hit.pop("surrounding_context", None)
        elif output_profile == "ui_navigation":
            # Include download links or identifiers for ui
            pass # Structure already ui-ready based on chunk_id/file

        # If trace is returned, we must not violate the bundle schema (which forbids additional properties).
        # We return a wrapper.
        if "query_trace" in res:
            return {
                "context_bundle": bundle,
                "query_trace": res["query_trace"]
            }

        return bundle

    return res
