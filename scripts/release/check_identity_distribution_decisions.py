#!/usr/bin/env python3
"""Fail-closed checks for RepoGround identity and distribution decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = Path("docs/decisions/repoground-3-naming-and-migration.v1.json")
LICENSE_DECISION = Path("docs/decisions/repoground-public-license-decision.v1.json")
THIRD_PARTY = Path("docs/release/third-party-license-review.v1.json")
SOURCE_DISTRIBUTION = Path(
    "docs/release/third-party-source-distribution-review.v1.json"
)
ALLOWED_METADATA_STATUSES = {
    "identified",
    "metadata_ambiguous",
    "metadata_unresolved",
}


def check(root: Path) -> list[str]:
    """Return decision drift findings for a repository root."""

    findings: list[str] = []
    identity = json.loads((root / IDENTITY).read_text(encoding="utf-8"))
    license_decision = json.loads(
        (root / LICENSE_DECISION).read_text(encoding="utf-8")
    )
    third_party = json.loads((root / THIRD_PARTY).read_text(encoding="utf-8"))
    source_distribution = json.loads(
        (root / SOURCE_DISTRIBUTION).read_text(encoding="utf-8")
    )
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    trademark_text = (root / "TRADEMARK_POLICY.md").read_text(encoding="utf-8")
    naming_text = (root / "docs/architecture/naming.md").read_text(
        encoding="utf-8"
    )
    release_policy = (root / "docs/release/release-policy.md").read_text(
        encoding="utf-8"
    )

    if identity.get("decision") != "adopt_repoground_for_3_x":
        findings.append("RepoGround identity decision changed")
    if (
        identity.get("repository_target_name") != "repoground"
        or identity.get("python_namespace") != "merger.repoground"
        or identity.get("product_name") != "RepoGround"
        or identity.get("primary_cli_name") != "repoground"
    ):
        findings.append("RepoGround identity mismatch")
    compatibility = identity.get("compatibility") or {}
    if (
        compatibility.get("legacy_python_namespace") != "merger.lenskit"
        or compatibility.get("persisted_2_x_identifiers_reinterpreted") is not False
    ):
        findings.append("compatibility boundary drift")
    if "RepoGround" not in naming_text or "merger.repoground" not in naming_text:
        findings.append("naming document drift")

    expression = license_decision.get("current_license_expression")
    if expression != "Apache-2.0":
        findings.append("license expression changed")
    if (
        "Apache License" not in license_text
        or "Version 2.0" not in license_text
    ):
        findings.append("LICENSE does not match decision")
    if license_decision.get("decision") != "grant_public_open_source_distribution":
        findings.append("open-source owner decision changed")
    if (
        license_decision.get("distribution_status")
        != "permitted_under_project_license"
    ):
        findings.append("public source distribution unexpectedly blocked")

    normalized_policy = release_policy.casefold()
    if (
        "distributable under apache-2.0" not in normalized_policy
        or "does not upload or publish" not in normalized_policy
    ):
        findings.append("release policy open-source boundary drift")
    if (
        "does not restrict any right granted" not in trademark_text.casefold()
        or "good-faith community use" not in trademark_text.casefold()
    ):
        findings.append("trademark policy software-freedom boundary drift")

    summary = third_party.get("summary") or {}
    packages = third_party.get("packages") or []
    if summary.get("package_count") != len(packages) or not packages:
        findings.append("third-party inventory count mismatch")
    for item in packages:
        if not item.get("name") or not item.get("version"):
            findings.append("third-party package identity incomplete")
        if item.get("metadata_status") not in ALLOWED_METADATA_STATUSES:
            findings.append(f"invalid metadata status: {item.get('name')}")

    source_decision = source_distribution.get("decision") or {}
    evidence = source_distribution.get("evidence") or {}
    if source_decision.get("source_distribution_allowed") is not True:
        findings.append("source distribution review does not permit source")
    if source_decision.get("project_license_expression") != "Apache-2.0":
        findings.append("source distribution license mismatch")
    if source_decision.get("bundled_dependency_distribution_allowed") is not False:
        findings.append("bundled dependency boundary unexpectedly enabled")
    if evidence.get("source_candidate_embeds_third_party_packages") is not False:
        findings.append("source candidate embedding boundary drift")
    if evidence.get("inventory_package_count") != summary.get("package_count"):
        findings.append("source review inventory count mismatch")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    findings = check(args.root.resolve())
    report = {
        "kind": "repoground.identity_distribution_decision_check",
        "version": "1.1",
        "status": "pass" if not findings else "fail",
        "findings": findings,
    }
    if args.format == "json":
        print(json.dumps(report, indent=2))
    elif findings:
        print("\n".join(findings))
    else:
        print("Identity/distribution decisions: pass")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
