# RepoBrief live source citation address v1 proof

Status: implemented by the RPU-V1-T002 slice.

## Scope

The slice adds an optional live repository source address next to canonical Brief Bundle citations.

A citation map row may now include:

- `source_range`: normalized source-file path and line/byte range from the chunk index;
- `live_repo_address`: repository convenience address with repo id, remote, git commit, dirty state, source path, line range, optional Git SHA-1 blob id and explicit status.

`repobrief query` and `query_existing_index(..., resolve_evidence=True)` project those fields into resolved evidence results while retaining the canonical citation id and canonical Brief Source range.

## Authority model

`canonical_range` remains the authoritative citation locator. `live_repo_address` is a convenience address for normal repository reading. It is never promoted to canonical content authority.

When provenance is missing, unavailable, dirty, or lacks a blob hash, the live address is marked `unknown`, `unavailable`, or `degraded` instead of inventing freshness.

## Boundary

The query path remains read-only over existing bundle artifacts. The snapshot generation path records file-content Git blob ids in chunk metadata for later citation-map projection, but does not mutate Git, run Git writes, create PRs, apply patches, or refresh stale bundles.

## Validation

Targeted validation:

```bash
python3 -m pytest -q \
  merger/lenskit/tests/test_citation_map_schema.py \
  merger/lenskit/tests/test_citation_map_producer.py \
  merger/lenskit/tests/test_repobrief_resolved_evidence_query.py \
  merger/lenskit/tests/test_repobrief_source_citation_projection.py \
  merger/lenskit/tests/test_chunk_index_dual_ranges.py
```

Expected result: all tests pass.

## Non-claims

This proof does not establish semantic completeness, runtime correctness, test sufficiency, review completeness, stale-bundle validity, freshness against remote, or merge readiness.
