"""Tests for the real-dump bundle surface self-check.

These exercise the headline coherence invariant the gate exists to enforce:
the claim-evidence-map surface is present XOR a machine-readable absence reason
is set — never silently absent — plus agent-pack consistency, post-emit-health
persistence, and generator runtime provenance.
"""

import json

import pytest

from merger.lenskit.core.bundle_surface_validate import (
    derive_surface_validation_path,
    validate_bundle_surface,
    write_bundle_surface_validation,
)
from merger.lenskit.core.constants import ArtifactRole
from merger.lenskit.core.merge import scan_repo, write_reports_v2
from merger.lenskit.core.post_emit_health import (
    derive_post_health_path,
    write_post_emit_health,
)
from merger.lenskit.tests._test_constants import make_generator_info


_PACK_SUMMARY_PRESENT = (
    "## CLAIM_EVIDENCE_MAP_SUMMARY\n"
    "- artifact: `x.claim_evidence_map.json`\n"
    "- claims: 3\n"
)
_PACK_ABSENT = (
    "## CLAIM_EVIDENCE_MAP_SUMMARY\n"
    "- _No verified `claim_evidence_map_json` artifact present._\n"
)
_PACK_ABSENT_WITH_REASON = (
    "## CLAIM_EVIDENCE_MAP_SUMMARY\n"
    "- _No verified `claim_evidence_map_json` artifact present._\n"
    "- reason=no_registry (registry missing)\n"
)
_PACK_LEGACY = "## CLAIM_EVIDENCE_MAP_SUMMARY\nclaim_evidence_map is not yet produced\n"

_DUMMY_SHA = "0" * 64


def _make_manifest(
    tmp_path,
    *,
    claim_present,
    absence_reason=None,
    pack_text=_PACK_SUMMARY_PRESENT,
    include_pack=True,
    include_runtime=True,
    include_post_health=True,
    include_output_health=True,
):
    """Write a synthetic but structurally valid bundle manifest + referenced files."""
    manifest_path = tmp_path / "x.bundle.manifest.json"
    artifacts = []

    (tmp_path / "x.md").write_text("# canonical\n", encoding="utf-8")
    artifacts.append({"role": "canonical_md", "path": "x.md", "sha256": _DUMMY_SHA, "bytes": 12})

    if include_pack:
        (tmp_path / "x.pack.md").write_text(pack_text, encoding="utf-8")
        artifacts.append(
            {"role": "agent_reading_pack", "path": "x.pack.md", "sha256": _DUMMY_SHA, "bytes": 1}
        )
    if include_output_health:
        (tmp_path / "x.oh.json").write_text('{"verdict": "pass"}', encoding="utf-8")
        artifacts.append(
            {"role": "output_health", "path": "x.oh.json", "sha256": _DUMMY_SHA, "bytes": 1}
        )
    if claim_present:
        (tmp_path / "x.cem.json").write_text("{}", encoding="utf-8")
        artifacts.append(
            {
                "role": "claim_evidence_map_json",
                "path": "x.cem.json",
                "sha256": _DUMMY_SHA,
                "bytes": 2,
            }
        )

    links = {}
    if absence_reason is not None:
        links["claim_evidence_map_absence_reason"] = absence_reason

    generator = {"name": "rlens", "version": "dev", "config_sha256": "a" * 64}
    if include_runtime:
        generator["runtime"] = {
            "module": "merger.lenskit.core.merge",
            "python_version": "3.11.0",
        }

    manifest = {
        "kind": "repolens.bundle.manifest",
        "version": "1.0",
        "run_id": "run-xyz",
        "created_at": "2026-06-02T00:00:00Z",
        "generator": generator,
        "artifacts": artifacts,
        "links": links,
        "capabilities": {"redaction": False},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if include_post_health:
        # A persisted (unregistered) post_emit_health sidecar at the derived path.
        write_post_emit_health(str(manifest_path), agent_pack_required=include_pack)
    return manifest_path


def _check(report, name):
    return next(c for c in report["checks"] if c["name"] == name)


# ── headline: claim-evidence-map surface ────────────────────────────────────

def test_claim_map_present_passes(tmp_path):
    mp = _make_manifest(tmp_path, claim_present=True)
    report = validate_bundle_surface(mp, require_claim_evidence_map=True)
    assert report["status"] == "pass"
    assert _check(report, "claim_evidence_map_surface")["status"] == "pass"


def test_claim_map_absent_with_reason_blocked_when_required(tmp_path):
    mp = _make_manifest(
        tmp_path,
        claim_present=False,
        absence_reason="no_registry",
        pack_text=_PACK_ABSENT_WITH_REASON,
    )
    report = validate_bundle_surface(mp, require_claim_evidence_map=True)
    # Not a silent pass: a declared absence is recorded as blocked when required.
    assert report["status"] == "blocked"
    assert _check(report, "claim_evidence_map_surface")["status"] == "blocked"


def test_claim_map_absent_without_reason_fails_when_required(tmp_path):
    mp = _make_manifest(
        tmp_path, claim_present=False, absence_reason=None, pack_text=_PACK_ABSENT
    )
    report = validate_bundle_surface(mp, require_claim_evidence_map=True)
    assert report["status"] == "fail"
    surf = _check(report, "claim_evidence_map_surface")
    assert surf["status"] == "fail"
    assert "no claim_evidence_map_absence_reason" in surf["detail"]


def test_claim_map_absent_with_reason_passes_when_not_required(tmp_path):
    mp = _make_manifest(
        tmp_path,
        claim_present=False,
        absence_reason="multi_repo_out_of_scope",
        pack_text=_PACK_ABSENT_WITH_REASON,
    )
    report = validate_bundle_surface(mp, require_claim_evidence_map=False)
    assert report["status"] == "pass"


def test_claim_map_present_with_absence_reason_is_contradiction(tmp_path):
    mp = _make_manifest(tmp_path, claim_present=True, absence_reason="no_registry")
    report = validate_bundle_surface(mp, require_claim_evidence_map=True)
    assert report["status"] == "fail"
    assert _check(report, "claim_evidence_map_surface")["status"] == "fail"


# ── agent reading pack consistency ──────────────────────────────────────────

def test_pack_announces_absent_while_map_present_fails(tmp_path):
    mp = _make_manifest(tmp_path, claim_present=True, pack_text=_PACK_ABSENT)
    report = validate_bundle_surface(mp, require_claim_evidence_map=True)
    assert report["status"] == "fail"
    assert _check(report, "agent_reading_pack_consistency")["status"] == "fail"


def test_pack_legacy_placeholder_is_drift(tmp_path):
    mp = _make_manifest(tmp_path, claim_present=False, absence_reason="no_registry",
                        pack_text=_PACK_LEGACY)
    report = validate_bundle_surface(mp, require_claim_evidence_map=False)
    pack = _check(report, "agent_reading_pack_consistency")
    assert pack["status"] == "fail"
    assert "legacy" in pack["detail"]


# ── post-emit health persistence ────────────────────────────────────────────

def test_post_emit_health_missing_warns_when_required(tmp_path):
    mp = _make_manifest(tmp_path, claim_present=True, include_post_health=False)
    # Ensure no sidecar exists.
    assert not derive_post_health_path(mp).exists()
    report = validate_bundle_surface(mp, require_claim_evidence_map=True)
    assert _check(report, "post_emit_health_persisted")["status"] == "warn"
    # A missing sidecar is degraded, not a hard defect.
    assert report["status"] in {"warn", "blocked"}


def test_post_emit_health_present_passes(tmp_path):
    mp = _make_manifest(tmp_path, claim_present=True, include_post_health=True)
    report = validate_bundle_surface(mp, require_claim_evidence_map=True)
    assert _check(report, "post_emit_health_persisted")["status"] == "pass"


# ── generator provenance ────────────────────────────────────────────────────

def test_missing_runtime_provenance_warns(tmp_path):
    mp = _make_manifest(tmp_path, claim_present=True, include_runtime=False)
    report = validate_bundle_surface(mp, require_claim_evidence_map=True)
    gp = _check(report, "generator_provenance")
    assert gp["status"] == "warn"
    assert "runtime" in gp["detail"]


# ── terminal / structural ───────────────────────────────────────────────────

def test_missing_manifest_blocked(tmp_path):
    report = validate_bundle_surface(tmp_path / "nope.json", require_claim_evidence_map=True)
    assert report["status"] == "blocked"
    assert report["checks"][0]["name"] == "manifest_present"


def test_report_shape_and_does_not_mean(tmp_path):
    mp = _make_manifest(tmp_path, claim_present=True)
    report = validate_bundle_surface(mp)
    assert report["kind"] == "lenskit.bundle_surface_validation"
    assert report["version"] == "1.0"
    assert report["bundle_run_id"] == "run-xyz"
    assert "forensic_ready" in report["does_not_mean"]
    # Always carries the headline check name (machine-readable contract).
    assert any(c["name"] == "claim_evidence_map_surface" for c in report["checks"])


# ── persistence sidecar ─────────────────────────────────────────────────────

def test_write_bundle_surface_validation_sidecar(tmp_path):
    mp = _make_manifest(tmp_path, claim_present=True)
    out, report = write_bundle_surface_validation(str(mp), require_claim_evidence_map=True)
    assert out == derive_surface_validation_path(mp)
    assert out.is_file()
    persisted = json.loads(out.read_text(encoding="utf-8"))
    assert persisted["status"] == report["status"]
    assert persisted["kind"] == "lenskit.bundle_surface_validation"


# ── end-to-end: a real single-repo dump self-checks to pass ─────────────────

_MINIMAL_REGISTRY_YAML = """\
kind: lenskit.doc_freshness_registry
version: "1.0"
authority: diagnostic_signal
risk_class: diagnostic
does_not_prove:
  - "a green verify does not prove docs complete or correct"
entries:
  - id: e2e-claim
    doc: docs/README.md
    locator: "intro"
    claim: "Feature exists"
    status: done
    normative: true
    owner: test
    last_verified: "2026-06-01"
    evidence:
      - kind: symbol
        target: "src/f.py::F"
"""


class _Extras:
    json_sidecar = True
    skip_md = False
    format = "markdown"
    augment_sidecar = False
    health = False
    organism_index = False
    fleet_panorama = False
    delta_reports = False
    heatmap = False


def test_real_single_repo_dump_surface_self_checks_pass_and_persists(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "README.md").write_text("# e2e\n", encoding="utf-8")
    (src_dir / "docs").mkdir()
    (src_dir / "docs" / "doc-freshness-registry.yml").write_text(
        _MINIMAL_REGISTRY_YAML, encoding="utf-8"
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    hub_dir = tmp_path / "hub"
    hub_dir.mkdir()

    summary = scan_repo(src_dir)
    artifacts = write_reports_v2(
        merges_dir=out_dir,
        hub=hub_dir,
        repo_summaries=[summary],
        detail="max",
        mode="gesamt",
        max_bytes=10000,
        plan_only=False,
        code_only=False,
        extras=_Extras(),
        output_mode="dual",
        generator_info=make_generator_info(name="rlens", version="dev"),
    )

    manifest = json.loads(artifacts.bundle_manifest.read_text(encoding="utf-8"))
    roles = {a["role"] for a in manifest["artifacts"]}
    assert ArtifactRole.CLAIM_EVIDENCE_MAP_JSON.value in roles

    # The dump path persisted both sidecars and recorded the verdict in links.
    links = manifest["links"]
    assert links["bundle_surface_validation_status"] == "pass"
    assert (out_dir / links["post_emit_health_path"]).is_file()
    assert (out_dir / links["bundle_surface_validation_path"]).is_file()

    # Re-validating the emitted manifest agrees.
    report = validate_bundle_surface(
        str(artifacts.bundle_manifest), require_claim_evidence_map=True
    )
    assert report["status"] == "pass"


@pytest.mark.parametrize("require", [True, False])
def test_validate_does_not_mutate_manifest(tmp_path, require):
    mp = _make_manifest(tmp_path, claim_present=True)
    before = mp.read_text(encoding="utf-8")
    validate_bundle_surface(mp, require_claim_evidence_map=require)
    assert mp.read_text(encoding="utf-8") == before
