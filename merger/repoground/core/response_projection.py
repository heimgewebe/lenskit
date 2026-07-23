"""Compact-by-default projection for RepoGround read-only frontdoor responses.

Symbol lookup, call navigation and retrieval all embed the same snapshot-wide
diagnostics on every call: a full per-role availability inventory, graph
availability internals, and fixed forbidden-operation / non-claim catalogs.
None of that varies with the query, so repeating it in full on every hit
overfetches. This module keeps the compaction in one place: the fail-closed
evidence a caller actually needs by default -- freshness status, commit
identity, and any role/graph gap that is not simply "fine" -- stays visible,
while the full inventory stays reachable (not deleted) behind ``verbose``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MUTATION_BOUNDARY_REF = "repobrief.mutation_boundary.read_only_frontdoor.v1"
DOES_NOT_ESTABLISH_REF = "repobrief.does_not_establish.default.v1"

# Role availability values that are normal/expected per call; anything
# else (missing_required, invalid, blocked_by_*, degraded, or a "missing"
# recommended artifact) is a gap and stays visible even in compact mode.
_GOOD_ROLE_AVAILABILITY = {"available", "not_applicable", "profile_excluded"}
_RECOMMENDED = "recommended"
_GOOD_GRAPH_STATUS = {"available", "not_generated", "profile_excluded"}


def _read_manifest(manifest_path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def commit_identity(manifest_path: Path) -> dict[str, Any] | None:
    """The bundle's source commit, if the manifest records one present repo.

    Returns ``None`` rather than a fabricated identity when provenance is
    absent or no repository is recorded as present.
    """
    manifest = _read_manifest(manifest_path)
    if manifest is None:
        return None
    provenance = manifest.get("snapshot_provenance")
    repos = provenance.get("repositories") if isinstance(provenance, dict) else None
    if not isinstance(repos, list):
        return None
    for repo in repos:
        if (
            isinstance(repo, dict)
            and repo.get("provenance_status") == "present"
            and isinstance(repo.get("git_commit"), str)
            and repo.get("git_commit")
        ):
            identity: dict[str, Any] = {"git_commit": repo["git_commit"]}
            name = repo.get("repo") or repo.get("name") or repo.get("path")
            if isinstance(name, str) and name:
                identity["repo"] = name
            return identity
    return None


def compact_freshness(freshness: Any, manifest_path: Path) -> dict[str, Any]:
    """Freshness status + commit identity. Never silences a non-fresh status."""
    status = freshness.get("status") if isinstance(freshness, dict) else None
    status = status if isinstance(status, str) else "unknown"
    commit = None
    if isinstance(freshness, dict):
        commit = freshness.get("commit") or freshness.get("git_commit")
    if commit is None:
        commit = commit_identity(manifest_path)
    compact: dict[str, Any] = {"status": status, "commit": commit}
    if status != "fresh" and isinstance(freshness, dict):
        if freshness.get("reason") is not None:
            compact["reason"] = freshness["reason"]
        if freshness.get("age_seconds") is not None:
            compact["age_seconds"] = freshness["age_seconds"]
    return compact


def compact_graph_availability(graph_model: Any) -> dict[str, Any]:
    status = graph_model.get("status") if isinstance(graph_model, dict) else None
    status = status if isinstance(status, str) else "unknown"
    compact: dict[str, Any] = {"status": status}
    if status not in _GOOD_GRAPH_STATUS and isinstance(graph_model, dict) and graph_model.get("reason"):
        compact["reason"] = graph_model["reason"]
    return compact


def compact_role_gaps(artifacts: Any) -> list[dict[str, Any]]:
    """Only the roles whose availability is not simply fine.

    Drops the always-repeated full per-role inventory (every role, every
    call) while keeping any explicit gap -- a missing required artifact, an
    invalid path, a missing recommended artifact, or a degraded/blocked
    validation -- visible by default.
    """
    if not isinstance(artifacts, list):
        return []
    gaps = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        availability = artifact.get("availability")
        requirement = artifact.get("requirement")
        if availability in _GOOD_ROLE_AVAILABILITY:
            continue
        # Missing required and recommended artifacts are both actionable gaps.
        # Missing optional artifacts are intentionally omitted from the compact view.
        if availability == "missing" and requirement not in {"required", _RECOMMENDED}:
            continue
        gaps.append({
            "role": artifact.get("role"),
            "availability": availability,
            "reason": artifact.get("reason"),
        })
    return gaps


def compact_availability(availability_model: Any, manifest_path: Path) -> dict[str, Any]:
    if not isinstance(availability_model, dict):
        return {
            "status": "unknown",
            "freshness": compact_freshness(None, manifest_path),
            "graph_availability": {"status": "unknown"},
            "gaps": [],
        }
    compact: dict[str, Any] = {
        "status": availability_model.get("status", "unknown"),
        "freshness": compact_freshness(availability_model.get("freshness"), manifest_path),
        "graph_availability": compact_graph_availability(availability_model.get("graph_availability")),
        "gaps": compact_role_gaps(availability_model.get("artifacts")),
    }
    if availability_model.get("error") is not None:
        compact["error"] = availability_model["error"]
    if availability_model.get("error_code") is not None:
        compact["error_code"] = availability_model["error_code"]
    if availability_model.get("reason") is not None:
        compact["reason"] = availability_model["reason"]
    return compact


def compact_mutation_boundary(boundary: Any) -> dict[str, Any]:
    """Keep the fail-closed fact (what this call writes) visible; drop the catalog."""
    writes = boundary.get("writes") if isinstance(boundary, dict) else []
    ref = boundary.get("ref") if isinstance(boundary, dict) and boundary.get("ref") else MUTATION_BOUNDARY_REF
    return {"ref": ref, "writes": list(writes) if isinstance(writes, list) else []}


def compact_does_not_establish(items: Any) -> dict[str, Any]:
    if isinstance(items, dict) and "ref" in items and "count" in items:
        return items
    count = len(items) if isinstance(items, (list, tuple)) else 0
    return {"ref": DOES_NOT_ESTABLISH_REF, "count": count}


def project_read_result(
    result: dict[str, Any],
    manifest_path: Path,
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    """Project a read-only frontdoor result to its compact default shape.

    ``verbose=True`` returns ``result`` unchanged -- the full diagnostic
    inventory, reproducible on demand rather than deleted. ``verbose=False``
    (the default) leaves hits, status, error detail, and truncation
    untouched, and collapses the availability/mutation/non-claim inventories
    -- which repeat unchanged across calls -- to their compact form.
    """
    if verbose or not isinstance(result, dict):
        return result
    projected = dict(result)
    if "availability" in projected:
        projected["availability"] = compact_availability(projected.get("availability"), manifest_path)
    if "freshness" in projected:
        availability = projected.get("availability")
        if isinstance(availability, dict) and "freshness" in availability:
            projected["freshness"] = availability["freshness"]
        else:
            projected["freshness"] = compact_freshness(projected.get("freshness"), manifest_path)
    if "mutation_boundary" in projected:
        projected["mutation_boundary"] = compact_mutation_boundary(projected.get("mutation_boundary"))
    if "does_not_establish" in projected:
        projected["does_not_establish"] = compact_does_not_establish(projected.get("does_not_establish"))
    return projected
