# RepoBrief Agent Memory Citations v1 Self-Review

PR: #944
Head SHA: `1791a86f6ff67c4cb7284f748abf5e741a223945`
Diff SHA256: `4f1e6be0f4e7c1e38c6caee467d307dbcc7d742072b0b861ed76f2a978c17a43`
Base: `origin/main`

## Scope reviewed

- `merger/lenskit/core/repobrief_memory.py`
- `merger/lenskit/tests/test_repobrief_memory.py`
- `docs/proofs/repobrief-agent-memory-citations-v1-proof.md`
- `docs/tasks/index.json`
- `docs/tasks/board.md`

## Review result

Status: pass with explicit boundaries.

The diff implements the requested RPU-V1-T015 pattern as an additive core helper and tests it against the three acceptance axes:

1. Memory record shape binds claim text, citation ids/ranges, snapshot stem/hash and freshness status.
2. Recall blocks changed, stale, missing or unverifiable evidence before source-backed presentation.
3. Memory remains explicitly non-authoritative and never becomes source truth without verified citations.

## Findings checked

- Range identity rejects missing file paths, invalid byte spans, bool bytes and missing content hashes.
- Artifact-axis byte aliases are accepted when primary byte aliases are `None`.
- Projection import keeps only resolved citations.
- Changed citation hashes, changed snapshot hashes, missing citations and missing freshness all produce `unusable` recall results.
- The implementation does not add persistence, CLI, MCP, scheduler, background refresh or repository mutation.

## Verification used

- `python3 -m pytest merger/lenskit/tests/test_repobrief_memory.py -q`
- `python3 -m pytest merger/lenskit/tests/test_repobrief_memory.py merger/lenskit/tests/test_repobrief_source_citation_projection.py merger/lenskit/tests/test_repobrief_resolved_evidence_query.py -q`
- `python3 -m ruff check merger/lenskit/core/repobrief_memory.py merger/lenskit/tests/test_repobrief_memory.py`
- `python3 -m compileall -q merger/lenskit/core/repobrief_memory.py`
- `git diff --cached --check`

## Non-claims

This self-review does not establish claim truth, answer correctness, full repository understanding, review completeness, full-suite success, CI success, runtime behavior, persistence safety, or merge readiness by itself.
