# RepoBrief Agent Workbench Usefulness Diagnostic v1

Status: review_ready  
Task: `TASK-REPOBRIEF-WORKBENCH-USEFULNESS-EVAL-001`  
Run: `20260709T030000Z`  
Report: `docs/diagnostics/repobrief-workbench-usefulness-eval-20260709T030000Z.json`  
Report SHA-256: `216c9d18114e73db94f90f155749cebb2062579e478d838f45d5a132e0636498`

## Result

This slice records a bounded diagnostic classification for the current RepoBrief Agent Workbench surfaces.

The decision is not "add more surfaces". The diagnostic conclusion is narrower:

1. Keep the existing front door surfaces as required navigation and diagnostics.
2. Treat graph, relation, card, symbol and retrieval surfaces as task-scoped aids.
3. Do not make raw card volume, raw health arrays, or retrieval metrics default required reading.
4. Prefer a future task-filtered Workbench shortlist before adding another broad surface.

## Scope

The report compares current surfaces against five criteria:

| Criterion | Meaning |
| --- | --- |
| `evidence_usefulness` | Helps support a concrete claim with inspectable evidence. |
| `navigation_value` | Helps an agent find the next file, range, symbol, artifact or status surface. |
| `false_confidence_risk` | Risk that an agent overreads the surface as correctness, completeness or approval. Higher is worse. |
| `missing_evidence_visibility` | Makes missing, stale, degraded or unavailable evidence visible. |
| `answer_compliance_value` | Helps an agent declare or check what it used before answering. |

Scores use a 0-3 scale and are diagnostic only.

## Evidence basis

This report is based on the committed RepoBrief/Agent Workbench architecture and current task registry surfaces:

- `docs/architecture/repobrief-agent-optimization-triage.md`
- `docs/architecture/repobrief-agent-workbench-boundary.md`
- `docs/architecture/agent-consumption-contract.md`
- `docs/proofs/agent-surface-real-dump-smoke-proof.md`
- `docs/proofs/retrieval-v2-default-promotion-decision-20260708T152502Z-proof.md`
- `docs/tasks/index.json`
- `docs/tasks/board.md`

No runtime, shell, Git, PR, patch, sidecar, test or local worktree authority is added by this slice.

## Findings

### Keep as required front door

| Surface | Reason |
| --- | --- |
| `canonical_md` | Content truth anchor. It is weak navigation by itself but must stay the canonical source. |
| `agent_reading_pack` | Best task-orientation surface. It carries required reading and negative semantics. |
| `bundle_manifest` | Best artifact inventory and role/authority map. |
| `citation_map_jsonl` | High value for cited answers and review workflows. |
| `output_health` / `post_emit_health` | Required diagnostics for missing/degraded evidence, but not proof of correctness. |
| `bundle_surface_validation` | Useful for surface review and artifact coherence checks. |

### Keep as task-scoped optional aids

| Surface | Use when | Main risk |
| --- | --- | --- |
| `claim_evidence_map_json` | Roadmap/status claims | Navigation can be mistaken for proof that a claim is true. |
| `python_symbol_index_json` | Symbol/file/range lookup | Symbol presence can be mistaken for runtime reachability. |
| Relation cards / graph signals | Static adjacency and related-files search | Static proximity can be mistaken for dependency, coverage or change impact. |
| Lens/concept cards | Summarized orientation | Raw volume can create noise and false semantic importance. |
| Query/session traces | Debugging or replay | Too noisy for default required reading. |

### Deprioritize as default required reading

- Raw lens/concept/relation-card volume.
- Raw health check arrays when compact projections are available.
- Retrieval metric reports as direct answer evidence.

Retrieval metrics remain useful as diagnostic measurement. They do not prove retrieval correctness, answer correctness, or default-promotion readiness.

## Recommendation

The next Workbench ergonomics improvement should be a compact, task-filtered shortlist that projects the most relevant surfaces for a requested task profile.

It should reuse existing authority and availability metadata rather than inventing new confidence levels.

## Task closeout posture

`TASK-REPOBRIEF-WORKBENCH-USEFULNESS-EVAL-001` is a closeout candidate after this slice, not automatically closed by this document.

The task registry remains the explicit task-state surface. Until `docs/tasks/index.json` and `docs/tasks/board.md` are reconciled, the task is still open in registry terms.

## Validation

Performed while preparing this revision:

```bash
python3 -m json.tool docs/diagnostics/repobrief-workbench-usefulness-eval-20260709T030000Z.json >/dev/null
```

The report SHA-256 above was computed from the exact JSON text committed by this patch.

Still required before merge if a local checkout is available:

```bash
git diff --check
```

CI should remain the repository validation authority.

## Non-claims

This evaluation does not establish:

- `repo_understood`
- `agent_correctness`
- `answer_correctness`
- `review_completeness`
- `test_sufficiency`
- `runtime_correctness`
- `retrieval_quality_in_general`
- `merge_readiness`
- `security_correctness`
- `forensic_ready`
