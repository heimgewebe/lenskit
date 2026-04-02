from typing import Dict, Any, Optional
import copy

def project_output(result: Dict[str, Any], output_profile: Optional[str] = None) -> Dict[str, Any]:
    """
    Applies the output profile projection to the query result.

    Response Contracts (enforced here and documented in docs/architecture/api_query_contracts.md):
    - Case 1 (No Profile): Returns the raw result object (contains 'results' list, not 'hits').
    - Case 2 (Profile specified, e.g. 'agent_minimal'): Returns the canonical Context-Bundle
      structure directly at the top level (contains 'hits' array).
    - Case 3 (Profile + Diagnostics/Guardrails): Returns a wrapper {"context_bundle": ..., ...}
      to ensure the strict Context-Bundle schema is not violated.
      Wrapper is created if at least one applies:
        - trace vorhanden ('query_trace' in result)
        - federation_conflicts nicht leer
        - warnings nicht leer

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
        elif output_profile == "lookup_minimal":
            for hit in bundle.get("hits", []):
                hit.pop("explain", None)
                hit.pop("graph_context", None)
                hit.pop("surrounding_context", None)
        elif output_profile == "review_context":
            for hit in bundle.get("hits", []):
                hit.pop("graph_context", None)
                if "surrounding_context" in hit and hit["surrounding_context"] is None:
                    hit.pop("surrounding_context", None)
        elif output_profile == "ui_navigation":
            # Include download links or identifiers for ui
            pass # Structure already ui-ready based on chunk_id/file

        # The bundle schema forbids additional top-level properties.
        # Wrapper is created if at least one applies:
        # - trace vorhanden ('query_trace' in result)
        # - federation_conflicts nicht leer
        # - warnings nicht leer
        wrapper = {"context_bundle": bundle}
        needs_wrapper = False

        if "query_trace" in res:
            wrapper["query_trace"] = res["query_trace"]
            needs_wrapper = True

        if res.get("federation_conflicts"):
            wrapper["federation_conflicts"] = res["federation_conflicts"]
            needs_wrapper = True

        if res.get("warnings"):
            wrapper["warnings"] = res["warnings"]
            needs_wrapper = True

        if needs_wrapper:
            return wrapper

        return bundle

    return res
