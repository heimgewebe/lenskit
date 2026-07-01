---
doc_type: proof
status: active
task: TASK-EXPORT-SAFETY-CHECKVIEW-CONSUMER-001
---

# Proof: Export Safety CheckView Consumer

## Purpose

The CheckView consumer inventory selected `export_safety_report` as the smallest safe next runtime consumer because it reads exactly one output-health signal: `redact_secrets_enabled`.

This slice migrates that read path to `compact_check_projection(report)` while preserving the existing top-level fallback and report semantics.

## Implementation

`merger/lenskit/core/export_safety_report.py` now derives output-health check values through `compact_check_projection(oh)` before reading `redact_secrets_enabled`.

Preserved behavior:

- post_emit_health redaction status still has priority over output_health;
- output_health mapping-shaped `redact_secrets_enabled=True/False` still works;
- malformed or list-shaped check entries do not create a redaction claim;
- top-level `output_health["redact_secrets_enabled"]` fallback still works;
- export-safety JSON schema and output fields are unchanged.

## Verification

Regression tests in `merger/lenskit/tests/test_export_safety_report.py` cover existing mapping behavior, malformed list-shaped checks, top-level fallback and existing post_emit_health priority.

Focused local test:

```text
/tmp/lenskit-pytest903-venv/bin/python -m pytest -q merger/lenskit/tests/test_export_safety_report.py merger/lenskit/tests/test_validation_check_view.py
57 passed
```

## Negative semantics

This does not prove secret absence, PII absence, answer safety, repo understanding, runtime correctness, test sufficiency, regression absence, or forensic readiness. It only changes one read-only consumer to use the existing CheckView projection.

## Non-goals

No producer normalization, no schema or contract migration, no JSON-output migration, no bundle emission change, no parity-state migration, no operational smoke-script migration, and no broad adapter sweep.
