# RepoBrief Ask CLI v1 Proof

Status: review_ready
Initiative: `REPOBRIEF-FRONTDOOR-GROUNDING-V1`
Task: `RBGV-V1-T005`

## Result

This slice adds a minimal read-only Ask Frontdoor producer:

- `merger/lenskit/core/repobrief_ask.py`
- `repobrief ask` CLI dispatch in `merger/lenskit/cli/cmd_repobrief.py`
- tests in `merger/lenskit/tests/test_repobrief_ask_cli.py`

## Behavior

`repobrief ask` reads an existing bundle manifest and emits either:

- JSON context pack matching `repobrief-ask-context-pack.v1`; or
- human-readable context-pack text.

The context pack includes:

- snapshot reference;
- freshness and availability blocks;
- Required Reading result for the selected task profile;
- retrieval hits;
- resolved ranges where available;
- answer scaffold with citation obligations, caveats and non-claims;
- budget report.

## Read-only boundary

The implementation delegates to existing read-only access/query paths and does not write snapshots,
refresh artifacts, mutate Git, apply patches, create PRs, execute shell commands or authorize merges.

## Validation

```bash
git diff --check
python -m pytest merger/lenskit/tests/test_repobrief_ask_cli.py -q
python -m pytest merger/lenskit/tests/test_repobrief_ask_frontdoor_contracts.py -q
python -m pytest merger/lenskit/tests/test_repobrief_resolved_evidence_query.py -q
python -m pytest merger/lenskit/tests/test_repobrief_access_boundary.py -q
python -m ruff check merger/lenskit/core/repobrief_ask.py merger/lenskit/cli/cmd_repobrief.py merger/lenskit/tests/test_repobrief_ask_cli.py
```

## Does not establish

This proof does not establish answer correctness, claim truth, actual reading, complete context use,
retrieval quality, runtime correctness outside tested paths, full test sufficiency, review completeness,
merge readiness, security correctness or regression absence.
