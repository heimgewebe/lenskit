from typing import Any, Dict, List, Optional

from merger.lenskit.core.lens_cards import produce_lens_card

KIND = "repolens.pr_delta_card"
VERSION = "1.0"
AUTHORITY = "navigation_index"
CANONICALITY = "derived"
SOURCE_KIND = "repolens.pr_schau.delta"

def produce_pr_delta_card(delta_context: Dict[str, Any], file_entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce a single PR Delta Card from a PR-Schau delta context and a file entry.
    """
    status = file_entry["status"]
    if status not in ("added", "changed", "removed"):
        raise ValueError(f"Invalid change_status: {status}")

    path = file_entry["path"]
    lens_card = produce_lens_card(path)

    card = {
        "kind": KIND,
        "version": VERSION,
        "authority": AUTHORITY,
        "canonicality": CANONICALITY,
        "delta_context": {
            "source_kind": SOURCE_KIND,
            "repo": delta_context["repo"],
            "generated_at": delta_context["generated_at"],
        },
        "path": lens_card["path"],
        "change_status": status,
        "primary_lens": lens_card["primary_lens"],
        "matched_rule": lens_card["matched_rule"],
        "facets": lens_card["facets"],
        "navigation_refs": lens_card["navigation_refs"],
        "does_not_establish": lens_card["does_not_establish"],
    }
    return card

def produce_pr_delta_cards(delta: Dict[str, Any], *, source_provenance: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Produce a batch of PR Delta Cards from a full PR-Schau delta payload.
    Validates summary counts and sorts output by path.
    """
    if not isinstance(delta, dict):
        raise TypeError("delta must be a dict")

    # Validate Summary
    summary = delta.get("summary", {})
    files = delta.get("files", [])
    
    counts = {"added": 0, "changed": 0, "removed": 0}
    for file_entry in files:
        if not isinstance(file_entry, dict):
            raise TypeError("file_entry must be a dict")
        status = file_entry.get("status")
        if status in counts:
            counts[status] += 1

    if counts["added"] != summary.get("added", -1) or \
       counts["changed"] != summary.get("changed", -1) or \
       counts["removed"] != summary.get("removed", -1):
        raise ValueError("Source summary counts do not match files array")

    delta_context = {
        "repo": delta.get("repo"),
        "generated_at": delta.get("generated_at"),
    }

    cards_by_path = {}
    for file_entry in files:
        path = file_entry.get("path")
        if path in cards_by_path:
            raise ValueError(f"Duplicate path in delta: {path}")

        card = produce_pr_delta_card(delta_context, file_entry)
        if source_provenance:
            card["source_provenance"] = source_provenance
            
        cards_by_path[path] = card

    # Output deterministically sorted by path
    return [cards_by_path[p] for p in sorted(cards_by_path.keys())]
