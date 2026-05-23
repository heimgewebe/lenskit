"""
Agent export gate for bundle-facing export profiles (roadmap PR A5).

This module enforces a small, explicit export gate for agent-facing profiles:
- post_emit_health must be available and pass on the final bundle surface,
- redaction policy must be acceptable for the requested profile,
- output_health.verdict is observation-only and never sufficient evidence.

Design constraints:
- No manifest mutation.
- No global truth verdicts (no safe/unsafe/agent_ready semantics).
- Deterministic machine-readable result shape.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .clock import now_utc
from .post_emit_health import derive_post_health_path

KIND = "lenskit.agent_export_gate"
VERSION = "1.0"

_BUNDLE_KIND = "repolens.bundle.manifest"
_POST_STATUSES = {"pass", "warn", "fail", "blocked"}
_AGENT_FACING_PROFILES = {
    "agent_minimal",
    "agent_facing",
    "agent",
}

_DOES_NOT_MEAN = [
    "repo_understood",
    "answer_safe_without_citations",
    "claims_true",
]


def _now_iso() -> str:
    ts = now_utc()
    if isinstance(ts, str):
        return ts if ts.endswith("Z") else ts + "Z"
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


def _load_json(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path.exists() or not path.is_file():
        return None, "file not found"
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return None, str(e)
    if not isinstance(data, dict):
        return None, "JSON root must be an object"
    return data, None


def _is_agent_facing(profile: Optional[str]) -> bool:
    if not profile:
        return False
    return profile in _AGENT_FACING_PROFILES


def _find_output_health_verdict(manifest: Dict[str, Any], manifest_dir: Path) -> Optional[str]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return None

    output_entry = None
    for art in artifacts:
        if not isinstance(art, dict):
            continue
        if art.get("role") == "output_health":
            output_entry = art
            break

    if not isinstance(output_entry, dict):
        return None
    rel_path = output_entry.get("path")
    if not isinstance(rel_path, str) or not rel_path:
        return None

    output_path = (manifest_dir / rel_path).resolve()
    output_doc, _ = _load_json(output_path)
    if not isinstance(output_doc, dict):
        return None

    verdict = output_doc.get("verdict")
    if isinstance(verdict, str):
        return verdict
    return None


def evaluate_agent_export_gate(
    manifest_path: str,
    post_health_path: Optional[str] = None,
    profile: Optional[str] = None,
    require_redaction: bool = True,
) -> Dict[str, Any]:
    """
    Evaluate whether export is permitted for the requested profile.

    Returns a deterministic machine-readable gate report.
    """
    errors: list[str] = []
    warnings: list[str] = []

    resolved_manifest = _resolve_path(manifest_path)

    manifest, manifest_err = _load_json(resolved_manifest)
    if manifest is None:
        return {
            "kind": KIND,
            "version": VERSION,
            "status": "blocked",
            "profile": profile,
            "agent_facing": _is_agent_facing(profile),
            "checked_at": _now_iso(),
            "bundle_manifest_path": str(resolved_manifest),
            "post_emit_health_status": None,
            "output_health_verdict_observed": None,
            "redaction_required": bool(require_redaction and _is_agent_facing(profile)),
            "redaction_enabled": None,
            "errors": [f"cannot read bundle manifest: {manifest_err}"],
            "warnings": [],
            "does_not_mean": list(_DOES_NOT_MEAN),
        }

    if manifest.get("kind") != _BUNDLE_KIND:
        return {
            "kind": KIND,
            "version": VERSION,
            "status": "blocked",
            "profile": profile,
            "agent_facing": _is_agent_facing(profile),
            "checked_at": _now_iso(),
            "bundle_manifest_path": str(resolved_manifest),
            "post_emit_health_status": None,
            "output_health_verdict_observed": None,
            "redaction_required": bool(require_redaction and _is_agent_facing(profile)),
            "redaction_enabled": None,
            "errors": ["manifest is not a repolens.bundle.manifest"],
            "warnings": [],
            "does_not_mean": list(_DOES_NOT_MEAN),
        }

    manifest_dir = resolved_manifest.parent
    agent_facing = _is_agent_facing(profile)
    redaction_required = bool(require_redaction and agent_facing)

    capabilities = manifest.get("capabilities") if isinstance(manifest.get("capabilities"), dict) else {}
    redaction_value = capabilities.get("redaction")
    redaction_enabled = redaction_value if isinstance(redaction_value, bool) else None

    output_health_verdict_observed: Optional[str] = _find_output_health_verdict(manifest, manifest_dir)

    if post_health_path:
        resolved_post_health = _resolve_path(post_health_path)
    else:
        resolved_post_health = derive_post_health_path(resolved_manifest)

    post_doc, post_err = _load_json(resolved_post_health)
    post_emit_health_status: Optional[str] = None
    if isinstance(post_doc, dict):
        raw_status = post_doc.get("status")
        if isinstance(raw_status, str) and raw_status in _POST_STATUSES:
            post_emit_health_status = raw_status
        else:
            warnings.append("post_emit_health report has no recognized status")
        observed = post_doc.get("output_health_verdict")
        if isinstance(observed, str):
            output_health_verdict_observed = observed
    else:
        if post_err is not None:
            warnings.append(f"post_emit_health unavailable: {post_err}")

    status = "pass"

    if agent_facing:
        if post_doc is None:
            status = "blocked"
            errors.append("agent-facing export requires readable post_emit_health")
        elif post_emit_health_status == "blocked":
            status = "blocked"
            errors.append("post_emit_health status is blocked")
        elif post_emit_health_status == "fail":
            status = "fail"
            errors.append("post_emit_health status is fail")
        elif post_emit_health_status != "pass":
            status = "fail"
            errors.append("agent-facing export requires post_emit_health status pass")

        if redaction_required and redaction_enabled is not True:
            status = "fail" if status != "blocked" else status
            errors.append("agent-facing export requires capabilities.redaction=true")
    else:
        if profile is None:
            warnings.append("no profile provided; treated as non-agent-facing")
        elif profile not in _AGENT_FACING_PROFILES and profile not in {
            "human_review",
            "ui_navigation",
            "lookup_minimal",
            "review_context",
            "local",
        }:
            warnings.append(f"unknown profile '{profile}' treated as non-agent-facing")

        warnings.append(
            "non-agent-facing profile result does not certify agent-surface export"
        )

    if output_health_verdict_observed == "pass" and (
        post_doc is None or post_emit_health_status != "pass"
    ):
        warnings.append(
            "output_health.verdict=pass observed but not sufficient for export gate"
        )

    return {
        "kind": KIND,
        "version": VERSION,
        "status": status,
        "profile": profile,
        "agent_facing": agent_facing,
        "checked_at": _now_iso(),
        "bundle_manifest_path": str(resolved_manifest),
        "post_emit_health_status": post_emit_health_status,
        "output_health_verdict_observed": output_health_verdict_observed,
        "redaction_required": redaction_required,
        "redaction_enabled": redaction_enabled,
        "errors": errors,
        "warnings": warnings,
        "does_not_mean": list(_DOES_NOT_MEAN),
    }