# Graph Availability Snapshot Proof

Status: done
Task: `RBV1-T015`

## Result

This slice exposes graph availability as a read-only projection in the RepoBrief
snapshot availability model.

The new `graph_availability` section reports whether graph artifacts are:

- `available`
- `stale`
- `not_generated`
- `profile_excluded`
- `blocked_by_missing_source`
- `blocked_by_missing_provenance`
- `invalid`

The projection is diagnostic. It does not build graph artifacts, refresh a
snapshot, mutate Git state, or create relation/impact claims.

## Retrieval boundary

A graph is `retrieval_eligible` only when the graph index is file-backed,
schema-valid and provenance-coherent with the bundle manifest's canonical dump
index hash.

A stale or mismatched graph remains visible as `status: stale`, but
`retrieval_eligible` is `false`. This preserves the existing stale-graph
fallback rule: stale graph evidence must not influence ranking.

## Validation

```text
pytest -q merger/lenskit/tests/test_repobrief_profiles.py
# 12 passed

pytest -q merger/lenskit/tests/test_graph_rerank.py \
  merger/lenskit/tests/test_retrieval_query.py \
  merger/lenskit/tests/test_graph_eval.py
# 44 passed
```

## Non-claims

This slice does not establish graph completeness, dependency completeness,
test sufficiency, runtime behavior, review impact, retrieval improvement,
regression absence, security correctness or merge readiness.
