from typing import Dict, Any, Optional
import copy

def project_output(result: Dict[str, Any], output_profile: Optional[str] = None) -> Dict[str, Any]:
    """
    Applies the output profile projection to the query result.
    If an output profile is specified and a context bundle exists, it returns the projected bundle.
    Otherwise, it returns the raw result.
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

        # Preserve query_trace if it existed in the top-level result
        if "query_trace" in res:
            bundle["query_trace"] = res["query_trace"]

        return bundle

    return res
