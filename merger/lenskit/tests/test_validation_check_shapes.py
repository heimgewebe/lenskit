"""Regression tests for TASK-VALIDATION-DIAG-003 — Check-Shape Consistency Audit.

These tests pin the *currently accepted* shape of the ``checks`` surface emitted by
the three validation producers, so the documented dict-vs-list divergence cannot
drift silently:

- ``output_health["checks"]``            -> mapping/dict keyed by check name
- ``post_emit_health["checks"]``         -> ordered list of check objects
- ``bundle_surface_validation["checks"]`` -> ordered list of check objects

They stabilize *shape only*. They intentionally do not assert verdicts, status
precedence, or per-check semantics (those are covered by each producer's own
suite), and they introduce no new vocabulary or producer behaviour. The audit and
its consumer inventory live in
``docs/proofs/validation-check-shape-consistency-audit.md``.

Fixtures are reused from the producers' own test modules (per the task scope: do
not duplicate fixture setup).
"""

from merger.lenskit.core.bundle_surface_validate import validate_bundle_surface
from merger.lenskit.core.output_health import compute_output_health
from merger.lenskit.core.post_emit_health import compute_post_emit_health
from merger.lenskit.tests.test_bundle_surface_validate import (
    _make_manifest as _make_surface_manifest,
)
from merger.lenskit.tests.test_output_health import _base_kwargs
from merger.lenskit.tests.test_post_emit_health import (
    _make_bundle as _make_post_emit_bundle,
)

# Shared diagnostic vocabulary for validation.mode. Kept as a set so the test
# stabilizes the shape without pinning one environment-dependent mode (a resolvable
# range ref yields "jsonschema"; a non-applicable/degraded run yields
# "skipped_unavailable"). See validation-diagnostics-schema-alignment-proof.md.
_VALIDATION_MODES = {"jsonschema", "skipped_unavailable", "minimal_fallback"}


def test_output_health_checks_remains_mapping(tmp_path):
    """output_health['checks'] is a mapping keyed by check name; the range-ref
    diagnostic is a nested object at checks['range_ref_resolution']['validation']."""
    report = compute_output_health(**_base_kwargs(tmp_path=tmp_path, with_sqlite=False))

    checks = report["checks"]
    assert isinstance(checks, dict)
    assert "range_ref_resolution" in checks
    assert isinstance(checks["range_ref_resolution"], dict)
    assert "validation" in checks["range_ref_resolution"]
    assert checks["range_ref_resolution"]["validation"]["mode"] in _VALIDATION_MODES


def test_post_emit_health_checks_remains_list_of_named_checks(tmp_path):
    """post_emit_health['checks'] is an ordered list of {name, status, ...} objects.

    A check's ``validation`` is optional, but where present it carries the full
    {mode, engine, reason} triad (the test does not force every check to carry it).
    """
    manifest = _make_post_emit_bundle(tmp_path)
    report = compute_post_emit_health(str(manifest))

    checks = report["checks"]
    assert isinstance(checks, list)
    assert checks, "expected at least one check"
    assert all(isinstance(check, dict) for check in checks)
    assert all("name" in check for check in checks)
    assert all("status" in check for check in checks)
    for check in checks:
        if "validation" in check:
            assert {"mode", "engine", "reason"} <= set(check["validation"])


def test_bundle_surface_validation_checks_remains_list_of_named_checks(tmp_path):
    """bundle_surface_validation['checks'] is an ordered list of {name, status, ...}
    objects; surface checks that carry validation use the surface engine."""
    manifest = _make_surface_manifest(tmp_path, claim_present=True)
    report = validate_bundle_surface(manifest, require_claim_evidence_map=True)

    checks = report["checks"]
    assert isinstance(checks, list)
    assert checks, "expected at least one check"
    assert all("name" in check for check in checks)
    assert all("status" in check for check in checks)
    for check in checks:
        if "validation" in check:
            assert check["validation"]["engine"] == "bundle_surface_validate"
            assert "mode" in check["validation"]
            assert "reason" in check["validation"]
