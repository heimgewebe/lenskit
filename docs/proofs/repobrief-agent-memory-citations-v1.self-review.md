# RepoBrief Agent Memory Citations v1 Self-Review

PR: #944
Reviewed implementation head SHA: `39f6bd8fb21bd4b89d1dd0702a10cf3bca070ac9`
Reviewed implementation diff SHA256: `fddfed5ad2c9603c00860fd0b2bc81b3da5cb622e02d2c0972f583df632f11dd`
Diff hash basis: `git diff origin/main...39f6bd8fb21bd4b89d1dd0702a10cf3bca070ac9 -- . ':(exclude)docs/proofs/repobrief-agent-memory-citations-v1.self-review.md'`
Base: `origin/main` / `f0f4e460a923a479f861af3ac1a3552bca3570a5`

## Evidence boundary

This file is a review-evidence artifact. Its own evidence-only commit is not included in the implementation diff hash above, to avoid a self-referential hash loop. A final merge gate must still verify the live PR head, CI status and current PR diff.

## Scope reviewed

- `merger/lenskit/core/repobrief_memory.py`
- `merger/lenskit/tests/test_repobrief_memory.py`
- `docs/proofs/repobrief-agent-memory-citations-v1-proof.md`
- `docs/tasks/index.json`
- `docs/tasks/board.md`

## Review result

Status: pass with explicit boundaries.

The reviewed implementation satisfies the requested RPU-V1-T015 pattern and the follow-up hardening findings:

1. Memory record shape binds claim text, citation ids/ranges, snapshot stem/hash and freshness status.
2. Recall blocks changed, stale, missing, conflicting or unverifiable evidence before source-backed presentation.
3. Recall now compares citation range identity, not only range content hash.
4. Projection import now fails closed on unresolved or malformed projection items.
5. Projection import preserves `repo_id` when present.
6. Memory remains explicitly non-authoritative and never becomes source truth without verified citations.

## Findings checked

- Range identity rejects missing file paths, invalid byte spans, bool bytes and missing content hashes.
- Artifact-axis byte aliases are accepted when primary byte aliases are `None`.
- Projection import preserves resolved citation identity and blocks unresolved citations.
- Changed citation hashes, changed snapshot hashes, missing citations and missing freshness all produce `unusable` recall results.
- Same-hash range moves across file path, byte range or `repo_id` produce `unusable` recall results.
- Mapping-key and inner `citation_id` conflicts produce `unusable` recall results.
- The implementation does not add persistence, CLI, MCP, scheduler, background refresh or repository mutation.

## Verification used

- `python3 -m pytest merger/lenskit/tests/test_repobrief_memory.py -q` → 12 passed
- `python3 -m pytest merger/lenskit/tests/test_repobrief_memory.py merger/lenskit/tests/test_repobrief_source_citation_projection.py merger/lenskit/tests/test_repobrief_resolved_evidence_query.py -q` → 41 passed
- `python3 -m ruff check merger/lenskit/core/repobrief_memory.py merger/lenskit/tests/test_repobrief_memory.py` → passed
- `python3 -m compileall -q merger/lenskit/core/repobrief_memory.py` → passed
- `git diff --check` → passed
- `git diff --cached --check` before commit → passed

## Non-claims

This self-review does not establish claim truth, answer correctness, full repository understanding, review completeness, full-suite success, CI success, runtime behavior, persistence safety, or merge readiness by itself.
