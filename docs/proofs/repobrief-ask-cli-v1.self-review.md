# Self-review — RepoBrief Ask CLI v1

Review target: `RBGV-V1-T005` branch head before PR creation

Files reviewed:

- `merger/lenskit/core/repobrief_ask.py`
- `merger/lenskit/cli/cmd_repobrief.py`
- `merger/lenskit/contracts/repobrief-ask-context-pack.v1.schema.json`
- `merger/lenskit/tests/test_repobrief_ask_cli.py`
- `docs/contracts/repobrief-ask-frontdoor-v1.md`
- `docs/proofs/repobrief-ask-cli-v1-proof.md`
- `docs/proofs/repobrief-ask-cli-v1.self-review.md`

## Result

No blocking issue found in this minimal CLI slice.

## Critical checks

| Check | Result |
| --- | --- |
| JSON context-pack output | Pass |
| Human-readable context-pack output | Pass |
| Uses existing read-only access/query surfaces | Pass |
| Does not write snapshots or refresh artifacts | Pass |
| Token budget affects excerpt truncation and is reported as constraint | Pass |
| Basic profile smoke | Pass |
| Stricter `pr_review` profile smoke | Pass |
| Missing required evidence returns failure | Pass |

## Review notes

The CLI is intentionally narrow. It does not try to answer the user's question. It produces an
answer-ready context pack and scaffold. Retrieval quality remains a later evaluation topic (`RBGV-V1-T006`).

## Limitations

- The selector is minimal and uses existing index results; no gold-query optimization yet.
- If no `sqlite_index` exists, query evidence is surfaced as unavailable rather than causing a refresh.
- The human output is for operator readability, not a stable machine contract.

## Validation

```bash
git diff --check
python -m pytest merger/lenskit/tests/test_repobrief_ask_cli.py -q
python -m pytest merger/lenskit/tests/test_repobrief_ask_frontdoor_contracts.py -q
python -m pytest merger/lenskit/tests/test_repobrief_resolved_evidence_query.py -q
python -m pytest merger/lenskit/tests/test_repobrief_access_boundary.py -q
python -m ruff check merger/lenskit/core/repobrief_ask.py merger/lenskit/cli/cmd_repobrief.py merger/lenskit/tests/test_repobrief_ask_cli.py
```

## Non-claims

This self-review does not establish answer correctness, claim truth, actual reading, complete context use,
retrieval quality, runtime correctness, full test sufficiency, review completeness, merge readiness,
security correctness or absence of regressions.
