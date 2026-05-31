"""Claim Evidence Map producer (claim-evidence-map v1).

This module derives a navigation/evidence index from docs/doc-freshness-registry.yml.
It links declared claims to declared evidence references without issuing truth verdicts.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from merger.lenskit.core.doc_freshness import (
    default_schema_path,
    load_registry,
    validate_registry,
)

TOP_LEVEL_DOES_NOT_ESTABLISH = [
    "truth",
    "sufficiency",
    "causality",
    "completeness",
    "freshness_beyond_last_verified",
]

CLAIM_DOES_NOT_ESTABLISH = [
    "truth",
    "sufficiency",
    "causality",
    "completeness",
]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _default_generated_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _effective_implies(evidence_ref: dict[str, Any]) -> str | None:
    explicit = evidence_ref.get("implies")
    if isinstance(explicit, str) and explicit:
        return explicit

    kind = evidence_ref.get("kind")
    if kind in {"symbol", "proof", "test"}:
        return "done"
    return None


def _to_claim_entry(entry: dict[str, Any]) -> dict[str, Any]:
    evidence_refs = []
    open_implies = False
    for evidence_ref in entry.get("evidence", []):
        if not isinstance(evidence_ref, dict):
            continue

        row = {
            "kind": evidence_ref.get("kind"),
            "target": evidence_ref.get("target"),
        }
        if "implies" in evidence_ref:
            row["implies"] = evidence_ref.get("implies")
        evidence_refs.append(row)

        if _effective_implies(evidence_ref) == "open":
            open_implies = True

    status = entry.get("status")
    requires_live_check = bool(status != "done" or open_implies)

    return {
        "id": entry.get("id"),
        "claim": entry.get("claim"),
        "doc": entry.get("doc"),
        "locator": entry.get("locator"),
        "status": status,
        "normative": bool(entry.get("normative", False)),
        "owner": entry.get("owner"),
        "last_verified": entry.get("last_verified"),
        "requires_live_check": requires_live_check,
        "evidence_refs": evidence_refs,
        "relation": "declared_evidence_ref",
        "does_not_establish": CLAIM_DOES_NOT_ESTABLISH,
    }


def build_claim_evidence_map(
    registry: dict[str, Any], *, registry_sha256: str, generated_at: str
) -> dict[str, Any]:
    entries = registry.get("entries")
    if not isinstance(entries, list):
        raise ValueError("doc-freshness registry must contain a list 'entries'")

    claims = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("doc-freshness registry entry must be a mapping")
        claims.append(_to_claim_entry(entry))

    claims.sort(key=lambda item: str(item.get("id", "")))

    return {
        "kind": "lenskit.claim_evidence_map",
        "version": "1.0",
        "authority": "navigation_index",
        "canonicality": "derived",
        "risk_class": "evidence_index",
        "source": {
            "registry_path": "docs/doc-freshness-registry.yml",
            "registry_sha256": registry_sha256,
            "generated_at": generated_at,
        },
        "does_not_establish": TOP_LEVEL_DOES_NOT_ESTABLISH,
        "claims": claims,
    }


def produce_claim_evidence_map(
    registry_path: str | Path,
    output_path: str | Path,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    registry_path = Path(registry_path)
    output_path = Path(output_path)

    registry = load_registry(registry_path)

    repo_root = registry_path.resolve().parents[1]
    schema_errors = validate_registry(registry, default_schema_path(repo_root))
    if schema_errors:
        raise ValueError(
            "doc-freshness registry validation failed: " + "; ".join(schema_errors)
        )

    claim_evidence_map = build_claim_evidence_map(
        registry,
        registry_sha256=_sha256_file(registry_path),
        generated_at=generated_at or _default_generated_at(),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(claim_evidence_map, indent=2, sort_keys=True) + "\n"
    output_path.write_text(payload, encoding="utf-8")
    return claim_evidence_map
