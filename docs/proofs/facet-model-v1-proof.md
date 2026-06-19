# Facet Model v1 Proof

Status: implemented / contract-core-test slice proof.

## Purpose and scope

This proof documents the smallest viable Facet Model v1 slice: a versioned JSON
contract, a deterministic core producer and focused tests for additive lens
facets. It records the diagnosis, the decisions taken, and the explicit limits
of this slice.

- Task: `TASK-LENS-FACET-001`
- Branch: `claude/affectionate-hamilton-tvda1d`
- Goal: introduce additive facet *view-axes* derived from controlled
  path/suffix rules, without replacing the single Primary Lens.

Explicit non-goals (this slice does **not** do any of these):

- no change to `LENS_IDS` or `infer_lens()`
- no new Primary Lens
- no population of `possible_facets` in the Primary Lens Audit
- no CLI, no bundle/manifest emission, no Artifact Role
- no Lens Cards, Relations, States or Task Context
- no retrieval ranking / graph / symbol integration
- no shared rule engine
- no review, security, impact, coverage or sufficiency verdicts
- no LLM, embeddings, network, timestamps in factual output or hidden global state

## Target proof (state before the patch)

Verified against `origin/main` at `aa2d04c6` ("docs(lens): define deterministic
lens model", PR #787), with the Primary Lens Audit landed in PR #786.

- The normative lens model is present on `origin/main`
  (`docs/architecture/lens-model.md`).
- The blueprint still names Facet Model v1 as the next unimplemented slice
  (`docs/blueprints/lenskit-agent-front-door-hardening.md` §14 / Slice 11).
- A facet contract was missing (`git ls-tree origin/main` matched no
  `lens-facet`/`facet-model` file).
- A facet producer was missing (no `merger/lenskit/core/lens_facets.py`).
- Focused facet tests were missing (no `merger/lenskit/tests/test_lens_facets.py`).
- `possible_facets` was — and remains — only an empty placeholder emitted by the
  Primary Lens Audit (`merger/lenskit/core/lens_audit.py` emits `[]`).
- No parallel facet PR exists: a PR search for `facet` returned only the merged
  #786 and #787; no remote branch matches `facet`.
- Task control held no equivalent running task (no `TASK-LENS-*` on the board or
  in `index.json`).

All gate conditions held, so the slice proceeded.

## Plan review (critique of the previously sketched scope)

What was right in the earlier plan and is preserved:

- define the normative lens model first;
- keep Primary Lens single-label and facets strictly additive;
- build no Lens Cards / Relations / retrieval integration before the contract;
- bound the task to a contract/core/test slice with a proof and task control.

What was premature and was changed here:

- **Taxonomy was treated as settled too early.** The blueprint candidate list
  (`contract`, `artifact_surface`, `diagnostic`, `retrieval`, `claim_boundary`,
  `security`, `test_guard`) is explicitly non-final in the lens model. v1 adopts
  only the candidates that pass a controlled-signal test and defers the rest.
- **`test_guard` was split.** The `guards` Primary Lens already absorbs tests,
  validation, CI and guard surfaces; a `test_guard` facet would largely restate
  the Primary Lens. v1 keeps a narrower, additive `test` facet (test modules
  only) and defers the `guard` half.
- **`security`, `claim_boundary`, `artifact_surface`, `diagnostic`,
  `uncertainty` were deferred** rather than guessed (reasons in the matrix).
- **Field names were verified against the repo** before being fixed: `path`,
  `facet`, `source_rule`, `derivation_type`, `does_not_establish`.
- The resulting scope is **smaller** (3 facets, all `direct`, one rule each)
  and deliberately reversible/extensible.

## Decision matrix

| Decision | Value | Basis |
| --- | --- | --- |
| Normative sources | lens-model.md §4–§6, §15–§16; blueprint Slice 11 / §14; primary-lens-audit contract+core | documented |
| v1 facet taxonomy | `contract`, `test`, `retrieval` | repo-derived from controlled signals |
| Excluded candidates | `artifact_surface`, `diagnostic`, `claim_boundary`, `security`, `uncertainty`, `guard` (the guard half of `test_guard`) | new decision (deferred) |
| Input model | repo-relative path (`str \| Path`) | repo-conventional (matches primary-lens-audit) |
| Target identity | normalized repo-relative POSIX path | repo-conventional |
| Report vs single assignment | aggregated report with per-`(path, facet)` items | repo-conventional (mirrors primary-lens-audit) |
| Root kind / version | `lenskit.lens_facet_report` / `1.0` | repo-conventional |
| Root fields | `kind`, `version`, `items`, `summary`, `does_not_establish` | repo-conventional |
| Item fields | `path`, `facet`, `source_rule`, `derivation_type`, `does_not_establish` | blueprint Slice 11 + repo-conventional |
| Facet field name | `facet` | blueprint sketch |
| Derivation field | `derivation_type` (values `direct`/`derived`/`heuristic`; v1 emits only `direct`) | lens-model §5; field name a new decision |
| Allowed derivation values | `direct`, `derived`, `heuristic` (no confidence/ordering) | lens-model §5 |
| Assignment identity | `(path, facet)` | new decision (minimal) |
| Sorting | stable by `(path, facet)`; `facet_counts` keys sorted | lens-model §16; repo-conventional |
| Deduplication | by `(path, facet)`; deterministic | lens-model §16 |
| Rule catalog | `contract_schema_suffix`, `test_module_marker`, `retrieval_surface_path` | new decision (controlled, one per facet) |
| Rule collisions | structurally impossible (one rule per facet); no canonical-rule mechanism needed in v1 | new decision |
| Unknown-facet behaviour | rejected by schema enum; no synthetic `unknown`/`other` facet; a path may carry 0 facets | lens-model §17 |
| Evidence policy | none mandatory in v1; `path`+`source_rule`+`derivation_type` form the provenance | lens-model §6 (left open) → minimal |
| Negative semantics | the 9-term lens-family baseline at report and item level | lens-model §15; primary-lens-audit |
| Summary | `item_count`, `target_count`, `facet_counts` (mechanical only) | repo-conventional |
| Task ID | `TASK-LENS-FACET-001` | free, matches `TASK-<DOMAIN>-NNN` |
| Proof path | `docs/proofs/facet-model-v1-proof.md` | repo-conventional |
| Non-scope | CLI, bundle emission, `possible_facets`, cards, relations, retrieval integration | lens-model §20; blueprint |

### Taxonomy rationale

Each v1 facet is derived from a single controlled path/suffix rule, has clear
positive and negative examples, cross-cuts or refines the Primary Lens additively,
and asserts nothing about importance, safety, effect or sufficiency.

- **`contract`** ← `contract_schema_suffix`: path ends with `.schema.json`.
  Narrower than the `data_models` Primary Lens (e.g. a `.proto` is `data_models`
  but is *not* a v1 contract facet). `direct`.
- **`test`** ← `test_module_marker`: filename is `test_*.py`, `*_test.py`,
  `*.test.ts` or `*.spec.ts`. Narrower than the `guards` Primary Lens (a
  `tests/` fixture helper that is not itself a test gets no facet). `direct`.
- **`retrieval`** ← `retrieval_surface_path`: a `retrieval` path segment
  (e.g. `merger/lenskit/retrieval/`, `docs/retrieval/`). Cross-cuts `core` and
  `data_models`. `direct`.

Deferred candidates and why:

- `artifact_surface` — no clear non-circular definition; "artifact"/"surface"
  are repo-wide unspecific.
- `diagnostic` — would need broad name matching (e.g. `*_health`) or a thin
  doc-folder scope; the boundary against health modules is unresolved.
- `claim_boundary` — lens-model leaves open whether this is a facet, a state or
  a scope boundary.
- `security` — a name-based security facet would risk implying risk/safety
  verdicts; explicitly out.
- `uncertainty` — lens-model leaves open whether this is a facet, a state
  umbrella, or not a controlled term.
- the `guard` half of `test_guard` — would duplicate the `guards` Primary Lens.

## Implementation evidence

- Contract: `merger/lenskit/contracts/lens-facet.v1.schema.json`
  (draft-07, `additionalProperties:false`, const `kind`/`version`, controlled
  `facet`/`source_rule`/`derivation_type` enums, per-facet `if/then` binding of
  facet→rule, 9-term `does_not_establish` at report and item level, repo-relative
  path pattern shared with primary-lens-audit).
- Core: `merger/lenskit/core/lens_facets.py` — `infer_facets(path)` and
  `produce_facet_report(paths)`. Pure: no I/O, env, git, network, timestamps,
  randomness or hidden state. Stable sort and dedup. Normalizer mirrors
  `lens_audit._normalize_path` (replicated locally rather than importing a
  private symbol).
- Tests: `merger/lenskit/tests/test_lens_facets.py` (61 tests).
- Task control: `docs/tasks/board.md` and `docs/tasks/index.json`
  (`TASK-LENS-FACET-001`, status `in-progress` — a draft PR is not a merged
  completion).
- Architecture alignment: `docs/architecture/lens-model.md` (§17 status, §19
  open decisions narrowed to what v1 actually decided).
- Blueprint alignment: `docs/blueprints/lenskit-agent-front-door-hardening.md`
  (Slice 11 / §14 status).

## Rule goldset

A hand-written table in the tests expresses business expectations (which facet
applies, why others do not, which rule is expected) rather than echoing the
producer:

- positive examples per facet: `contract` (3), `test` (5), `retrieval` (2);
- multi-facet paths: `retrieval`+`test`, `retrieval`+`contract`;
- a valid path with no facet: `merger/lenskit/core/lenses.py`;
- negative refinements: `.proto` (data_models, no contract facet) and a
  `tests/` fixture helper (no test facet).

Rule collisions cannot occur in v1: each facet has exactly one rule, so a
`(path, facet)` pair is never produced by two competing rules. The
multi-facet and dedup cases are covered by tests.

## Validation

Commands actually executed (Python 3.11, `jsonschema` 4.26 installed locally so
the schema tests run rather than skip):

- `python -m pytest merger/lenskit/tests/test_lens_facets.py -q` → 61 passed
- `python -m pytest merger/lenskit/tests/test_lenses.py merger/lenskit/tests/test_primary_lens_audit.py -q` → passed
- `python -m pytest merger/lenskit/tests/test_contract_version_guards.py merger/lenskit/tests/test_link_integrity.py -q` → passed
- `python -m pytest merger/lenskit/tests/test_planning_registration_ratchet.py -q` → passed
- `python3 -m scripts.docmeta.check_planning_registration --ratchet --baseline docs/tasks/planning-registration-baseline.json --format human` → no new drift (0 findings)
- `python scripts/check_no_test_stubs.py` → OK
- `ruff check` on the new Python files → All checks passed
- `Draft7Validator.check_schema(...)` on the contract → OK
- `git diff --check` → clean

## Claim boundary

This slice does **not** establish:

- completeness of the facet taxonomy (3 of many candidates; the rest are
  deferred by decision);
- actual agent usefulness or improved retrieval quality;
- review completeness, runtime correctness, test sufficiency, or
  regression-freedom outside the checked surfaces;
- that facets are consumed anywhere (no bundle emission, no CLI, no
  `possible_facets` population, no Lens Cards).

The draft PR presents the smallest evidenced Facet Model v1 slice for review.
Merge approval, taxonomy completeness, consumer integration, bundle emission and
Lens Cards are out of scope for this task.
