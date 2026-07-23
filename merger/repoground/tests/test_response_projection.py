"""Focused contract and size comparison tests for RepoGround compact vs full read responses."""
from __future__ import annotations

import json
from pathlib import Path

from merger.repoground.core import bundle_access, mcp_tools
from merger.repoground.core.response_projection import (
    compact_availability,
    compact_freshness,
    compact_role_gaps,
)
from merger.repoground.tests.test_call_navigation import _bundle


def test_compact_vs_full_json_size(tmp_path: Path):
    manifest = _bundle(tmp_path)

    # 1. search_symbol_index
    compact_sym = bundle_access.search_symbol_index(manifest, "target")
    full_sym = bundle_access.search_symbol_index(manifest, "target", verbose=True)

    compact_sym_bytes = len(json.dumps(compact_sym))
    full_sym_bytes = len(json.dumps(full_sym))

    assert compact_sym["mutation_boundary"]["ref"] == "repobrief.mutation_boundary.read_only_frontdoor.v1"
    assert "does_not_mutate" not in compact_sym["mutation_boundary"]
    assert full_sym["mutation_boundary"]["read_paths_do_not_refresh"] is True
    assert "does_not_mutate" in full_sym["mutation_boundary"]
    assert compact_sym_bytes < full_sym_bytes

    # 2. find_references
    compact_refs = bundle_access.find_references(manifest, "target")
    full_refs = bundle_access.find_references(manifest, "target", verbose=True)

    assert compact_refs["mutation_boundary"]["ref"] == "repobrief.mutation_boundary.read_only_frontdoor.v1"
    assert len(json.dumps(compact_refs)) < len(json.dumps(full_refs))

    # 3. mcp_tools.find_symbol
    mcp_compact = mcp_tools.find_symbol(bundle_manifest=manifest, name="target")
    mcp_full = mcp_tools.find_symbol(bundle_manifest=manifest, name="target", verbose=True)

    assert mcp_compact["mutation_boundary"]["ref"] == "repobrief.mutation_boundary.read_only_frontdoor.v1"
    assert "forbidden_operations" not in mcp_compact["mutation_boundary"]
    assert "forbidden_operations" in mcp_full["mutation_boundary"]
    assert len(json.dumps(mcp_compact)) < len(json.dumps(mcp_full))


def test_compact_projection_preserves_freshness_commit_and_non_fresh_reasons(tmp_path: Path):
    manifest = _bundle(tmp_path)
    full = bundle_access.search_symbol_index(manifest, "target", verbose=True)

    freshness = full.get("freshness") or {}
    compact_f = compact_freshness(freshness, manifest)

    assert compact_f["status"] == freshness.get("status", "unknown")
    assert "status" in compact_f

    # Test compact_availability
    availability_full = full.get("availability")
    compact_avail = compact_availability(availability_full, manifest)
    assert compact_avail["status"] == availability_full.get("status", "unknown")
    assert "gaps" in compact_avail

    # Stale/degraded freshness preserves reason & age_seconds
    stale_freshness = {"status": "stale", "reason": "snapshot_older_than_max_age", "age_seconds": 3600}
    compact_stale = compact_freshness(stale_freshness, manifest)
    assert compact_stale["status"] == "stale"
    assert compact_stale["reason"] == "snapshot_older_than_max_age"
    assert compact_stale["age_seconds"] == 3600


def test_compact_projection_preserves_explicit_gaps():
    artifacts = [
        {"role": "sqlite_index", "requirement": "required", "availability": "available"},
        {"role": "required_index", "requirement": "required", "availability": "missing", "reason": "not_generated"},
        {"role": "agent_reading_pack", "requirement": "recommended", "availability": "missing", "reason": "not_generated"},
        {"role": "optional_card", "requirement": "optional", "availability": "missing"},
        {"role": "corrupted_artifact", "requirement": "required", "availability": "invalid", "reason": "path_escapes_root"},
    ]

    gaps = compact_role_gaps(artifacts)
    gaps_roles = [g["role"] for g in gaps]

    assert "sqlite_index" not in gaps_roles
    assert "optional_card" not in gaps_roles
    assert "required_index" in gaps_roles
    assert "agent_reading_pack" in gaps_roles
    assert "corrupted_artifact" in gaps_roles


def test_compact_projection_preserves_errors_and_truncation(tmp_path: Path):
    manifest = _bundle(tmp_path)

    # Invalid search preserves error and error_code
    invalid_res = mcp_tools.find_symbol(bundle_manifest=manifest, name="target", kind="unknown_kind")
    assert invalid_res["status"] == "invalid"
    assert invalid_res["result"]["error_code"] == "kind_invalid"
    assert "error" in invalid_res["result"]

    # Truncated query preserves hit evidence and truncation flag
    refs = bundle_access.find_references(manifest, "target", k=1)
    assert refs["status"] == "available"
    assert refs["truncated"] is True
    assert len(refs["hits"]) == 1


def test_all_mcp_read_only_tools_support_verbose_opt_in(tmp_path: Path):
    manifest = _bundle(tmp_path)

    # test find_symbol
    fs_compact = mcp_tools.find_symbol(bundle_manifest=manifest, name="target")
    fs_verbose = mcp_tools.find_symbol(bundle_manifest=manifest, name="target", verbose=True)
    assert "ref" in fs_compact["mutation_boundary"]
    assert "forbidden_operations" in fs_verbose["mutation_boundary"]

    # test find_references
    fr_compact = mcp_tools.find_references(bundle_manifest=manifest, name="target")
    fr_verbose = mcp_tools.find_references(bundle_manifest=manifest, name="target", verbose=True)
    assert "ref" in fr_compact["mutation_boundary"]
    assert "forbidden_operations" in fr_verbose["mutation_boundary"]
