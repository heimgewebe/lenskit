# Facet Model v1 Proof

Status: implemented / contract-core-test slice proof.

## Purpose and scope

This proof documents the smallest viable Facet Model v1 slice: a versioned JSON
contract, a deterministic core producer, focused tests, and a path-scoped CI
gate for additive lens facets. It records the diagnosis, the decisions taken,
and the explicit limits of this slice. It reflects the state after the hardening
pass that closed the dump-confirmed gaps (real test classification, fixture
exclusion, host-independent path identity, v1 contract uniqueness, CI coverage)
and a follow-up review pass that added a control-character/surrogate path-content
policy, a producer collection boundary, and a deprecation-safe `jsonschema`
version probe in CI, followed by a portability pass that made the schema path
pattern ECMAScript-portable (rejecting only *unpaired* UTF-16 surrogates so valid
emoji pass under Ajv/Node as well as Python) with a dedicated Node parity gate.

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
- no shared rule engine; no general path-utility refactor
- no review, security, impact, coverage or sufficiency verdicts
- no LLM, embeddings, content analysis, git-history analysis
- no network, timestamps in factual output, or hidden global state

## Target proof (state before the patch)

Verified against `origin/main` at `aa2d04c6` ("docs(lens): define deterministic
lens model", PR #787), with the Primary Lens Audit landed in PR #786.

- The normative lens model is present on `origin/main`
  (`docs/architecture/lens-model.md`).
- The blueprint named Facet Model v1 as the next unimplemented slice
  (`docs/blueprints/lenskit-agent-front-door-hardening.md` §14 / Slice 11).
- A facet contract, producer and focused tests were all missing.
- `possible_facets` was — and remains — only an empty placeholder emitted by the
  Primary Lens Audit (`merger/lenskit/core/lens_audit.py` emits `[]`).
- No parallel facet PR existed; no `TASK-LENS-*` on the board or in `index.json`.

## Plan review

What was right and is preserved: define the normative lens model first; keep
Primary Lens single-label and facets strictly additive (0..n); build no Lens
Cards / Relations / retrieval integration before the contract; defer open terms
(`uncertainty`, `claim_boundary`, `security`); separate `derivation_type` from
confidence language; keep the task `in-progress` during the draft.

What was not ideal and was corrected in the hardening pass:

- **Tests used hypothetical paths**, missing real JavaScript test modules
  (`test_*.js`). The goldset is now overwhelmingly real repo paths.
- **The test rule was filename-only**, so a `fixtures/.../test_*.py` was a false
  positive. A `fixtures` path-segment now excludes the `test` facet.
- **Path normalization mirrored a private sibling helper** and the test even
  imported `lens_audit._normalize_path`. The facet code now has its own explicit
  canonical grammar, and the test no longer imports anything from `lens_audit`.
- **The path grammar was not fully canonical or host-independent** (`./a`,
  `a/./b`, `a//b`, trailing slash, Windows drive prefixes were not all covered).
  It now is, in both core and schema.
- **The contract allowed `derived`/`heuristic`** although the v1 producer only
  emits `direct`. The v1 contract now pins `derivation_type` to `const: direct`.
- **`(path, facet)` uniqueness and summary coherence were over-stated as contract
  guarantees.** They are producer invariants; the schema enforces only what
  draft-07 can (strict shape, `uniqueItems`, fixed field bindings).
- **No CI gate ran the facet tests.** A path-scoped `lens-model.yml` gate now runs
  them with `jsonschema` installed.

## Decision matrix

| Decision | Value | Basis |
| --- | --- | --- |
| v1 facet taxonomy | `contract`, `test`, `retrieval` | repo-derived from controlled signals |
| Excluded candidates | `artifact_surface`, `diagnostic`, `claim_boundary`, `security`, `uncertainty`, `guard` (the guard half of `test_guard`) | new decision (deferred) |
| Input model / types | repo-relative path; accepts only `str` or `PurePosixPath`, else `TypeError` (a `PureWindowsPath` is rejected, not coerced) | repo-conventional + hardening |
| Target identity | host-independent canonical repo-relative POSIX path | new decision (hardened grammar) |
| Path content policy | reject ASCII control chars (U+0000–U+001F, U+007F) in core+schema; core rejects all surrogate code points, schema rejects only *unpaired* UTF-16 surrogate code units (valid pairs/emoji accepted); ordinary non-ASCII Unicode stays valid | new decision (Facet v1 artifact boundary; ECMAScript-portable) |
| Collection boundary | `produce_facet_report()` requires an iterable of many paths; a single path-like (`str`/`bytes`/`bytearray`/`os.PathLike`) raises `TypeError`; generators supported | new decision (producer API) |
| Report vs single assignment | aggregated assignment report with per-`(path, facet)` items | repo-conventional (mirrors primary-lens-audit) |
| Root kind / version | `lenskit.lens_facet_report` / `1.0` | repo-conventional |
| Item fields | `path`, `facet`, `source_rule`, `derivation_type`, `does_not_establish` | blueprint Slice 11 + repo-conventional |
| Derivation field (general model) | `direct` / `derived` / `heuristic` | lens-model §5 |
| Derivation field (v1 contract + producer) | `const: direct` only | new decision (hardening) |
| Assignment identity | `(path, facet)` (producer dedup) | new decision (minimal) |
| Sorting | stable by `(path, facet)`; `facet_counts` keys sorted | lens-model §16 |
| Rule catalog | `contract_schema_suffix`, `test_module_marker`, `retrieval_surface_path` | new decision (one rule per facet) |
| `test` markers | `test_*.py`, `test_*.js` (real) + `*_test.py`, `*.test.ts`, `*.spec.ts` (infer_lens norm); `fixtures` segment excluded | repo inventory + norm |
| `retrieval` scope | any `retrieval` path segment, incl. retrieval fixtures (Variant A) | new decision (documented) |
| Rule collisions | structurally impossible (one rule per facet) | new decision |
| Unknown-facet behaviour | rejected by schema enum; no synthetic `unknown`/`other`; a path may carry 0 facets | lens-model §17 |
| Evidence policy | none mandatory in v1; `path`+`source_rule`+`derivation_type` form the provenance | lens-model §6 → minimal |
| Negative semantics | the 9-term lens-family baseline, fixed canonical order, at report and item level | lens-model §15 |
| Summary | `item_count`, `target_count`, `facet_counts` (producer-computed; schema checks shape only) | repo-conventional |
| Report type | assignment report (not evaluation/coverage); facet-free paths are not emitted | new decision (documented) |
| CI gate | `.github/workflows/lens-model.yml` (path-scoped; jsonschema required; Node ECMAScript pattern-parity check) | new decision |

## Facet semantics

- **`contract`** ← `contract_schema_suffix`: the path carries the controlled
  `.schema.json` file extension (not a broader "versioned contract surface"
  claim). A `.proto` is a `data_models` Primary Lens but is *not* a v1 contract
  facet. `direct`.
- **`test`** ← `test_module_marker`: the file is itself a test module by a
  controlled filename marker (`test_*.py`, `test_*.js`, `*_test.py`, `*.test.ts`,
  `*.spec.ts`), and is **not** under a `fixtures` path segment. The facet does
  **not** mean the test was collected by a runner, executed, passed, is complete,
  or is sufficient. Narrower than the broad `guards` Primary Lens. `direct`.
- **`retrieval`** ← `retrieval_surface_path`: a `retrieval` path segment
  (Variant A — includes retrieval fixtures such as
  `merger/lenskit/tests/fixtures/retrieval/...`). The facet marks a
  retrieval-related surface, not production status. `direct`.

Deferred candidates: `artifact_surface` (no non-circular definition),
`diagnostic` (boundary against health modules unresolved), `claim_boundary` and
`uncertainty` (lens-model leaves their facet/state status open), `security` (a
name-based facet would risk a safety verdict), and the `guard` half of
`test_guard` (would restate the `guards` Primary Lens).

## Path identity

Accepted runtime types: `str` and `PurePosixPath`. String inputs are lexically
strict and never silently normalized (non-canonical inputs like `./a` or `a//b`
are rejected). For `PurePosixPath`, only the already-interpreted POSIX
representation from `pathlib` is visible; earlier redundant spellings cannot be
reconstructed. Native `Path` on POSIX hosts is accepted merely due to its type
relationship to `PurePosixPath`; it carries no portable cross-platform guarantee.
In particular, `PureWindowsPath` (and native `Path` on Windows) is
**rejected with `TypeError`**. The grammar is enforced in core, while the
schema checks only the emitted string representation:

- rejected (both surfaces): empty/whitespace, leading `/`, trailing `/`, `./a`,
  `a/./b`, `a//b`, `.`/`..` components, backslash, Windows drive prefix (`C:/`,
  `c:/`), and ASCII control characters (U+0000–U+001F, U+007F, incl. a trailing
  newline).
- accepted: e.g. `.github/workflows/ci.yml`, `merger/lenskit/core/lenses.py`,
  `a`, `a.b`, `a-b/c_d.schema.json`, and ordinary non-ASCII Unicode — including
  astral scalars — such as `docs/überblick.md`, `docs/évidence.md`,
  `docs/分析.md`, `docs/🔍.md`.

**Surrogate handling differs by surface, by design.** The Python core rejects any
surrogate *code point* in a runtime string (it operates on code points, so any
value in U+D800–U+DFFF is caught directly). The JSON Schema models JSON strings
and rejects only *unpaired* UTF-16 surrogate *code units*, while accepting valid
surrogate pairs — i.e. ordinary scalars such as emoji. This split is required for
**validator portability**: a JSON-Schema `pattern` is ECMA-262 and is applied by
ECMAScript-based validators (the repo already runs Ajv in
`scripts/jsonl-validate.sh`) over UTF-16 code units, where an emoji is a surrogate
pair. A blanket surrogate class spanning U+D800–U+DFFF is green under Python's
`re` (code points) yet rejects valid emoji under ECMAScript, so the contract now
rejects only *unpaired* high/low surrogates (lone high, lone low, a low at string
start, a high at string end). Because Python validators cannot observe this,
parity is guarded by a Node test,
`merger/lenskit/tests/test_lens_facet_pattern_ecma.js`, which loads the pattern
directly from the schema (no copied regex, no npm/Ajv dependency — Node built-ins
only) and runs an accept/reject matrix: emoji and an explicit surrogate pair are
accepted; every unpaired-surrogate and control case is rejected. The Python `re`
parity for control characters and *lone* surrogates is asserted per cause in
`test_lens_facets.py`; a JSON-decode test there also confirms a surrogate-pair
escape recombines to the emoji and validates.

Rejecting these inputs is a **Facet v1 artifact-boundary decision for this path
surface, not a global Lenskit filename policy**. Other subsystems deliberately
preserve odd filenames: the source-acquisition and atlas layers decode git output
and filenames with `errors="surrogateescape"`
(`merger/lenskit/service/source_acquisition.py`,
`merger/lenskit/adapters/atlas.py`), so a real invalid-UTF-8 filename byte can
surface there as exactly the kind of lone surrogate (e.g. U+DCFF) that the facet
path surface refuses.

`produce_facet_report()` enforces a **collection boundary**: it expects an
iterable of many paths, so a single path-like value (`str`, `bytes`, `bytearray`
or `os.PathLike`) raises `TypeError` rather than being iterated character-wise.
Generators are accepted; an empty iterable yields an empty report; a bad element
inside an iterable still raises from `_normalize_path`. A single path uses
`infer_facets()`.

The facet test no longer imports the private `lens_audit._normalize_path`; both
test surfaces verify their own baseline cases independently, and `lens_audit.py`
is untouched.

## Contract uniqueness and summary boundary

- `derivation_type` is `const: direct` in v1; `derived`/`heuristic` are invalid
  in a v1 report (reserved by the general lens model for later rules).
- `does_not_establish` is a fixed, positional tuple (`items` array of `const`s,
  `minItems`/`maxItems` 9, `additionalItems: false`): reordered, missing or extra
  entries are rejected. The fixed order is a **canonical serialization order for
  deterministic output; it carries no rank, priority or importance meaning**
  (consistent with lens-model §2: list order expresses no semantic priority).
- Each facet binds to exactly one `source_rule` via `if/then`.
- The root `items` array sets `uniqueItems: true`.
- **Producer guarantee:** deduplication by `(path, facet)`; stable sort;
  coherent summary counters.
- **Schema guarantee:** strict shape, controlled vocabulary, fixed bindings, and
  rejection of duplicate items according to JSON value equality (`uniqueItems`).
- **Remaining draft-07 limit:** the schema does not (and cannot) recompute the
  summary counters against `items`, nor prove arbitrary semantic key coherence;
  that remains a producer invariant, asserted directly in the tests.

## Report type

Facet Model v1 is an **assignment report**, not an evaluation/coverage report.
`items` contains only produced `(path, facet)` assignments; a checked path with
no facet is not emitted and is indistinguishable from a path never passed in.
`target_count` counts only distinct paths that carry at least one facet. No
`evaluated_target_count` / `coverage` / `classification_rate` fields exist.

## Repository projection snapshot (`git ls-files -z`)

This projection was measured from `git ls-files -z` on the current PR checkout. It
is descriptive evidence for that checkout and is not automatically
freshness-enforced after later repository additions or deletions.

- tracked paths: 569
- facet items: 274
- facet targets: 274
- facet counts: `contract` 51, `test` 201, `retrieval` 22
- real multi-facet targets: **0**

The projection run also asserts that every tracked path is accepted by the
producer and that the produced report validates against the schema. The Node
ECMAScript test `merger/lenskit/tests/test_lens_facet_pattern_ecma.js` is a newly
tracked `test_*.js` path, so relative to the previous snapshot it adds exactly one
tracked path, one facet item and one `test` target (568→569, 273→274, `test`
200→201); all other counts are unchanged.

There are currently no real multi-facet paths in the repo. Multi-facet support
is genuine producer capability, exercised only by clearly labelled **synthetic
capability fixtures** in the tests (e.g. `merger/lenskit/retrieval/
test_eval_capability.py`); the rules were not widened to manufacture overlaps.

## CI gate

`.github/workflows/lens-model.yml` is a failure-enforcing, path-scoped CI gate.
Changes to lens core, contracts, tests, the lens-model architecture document,
the Facet Model proof, the front-door blueprint, requirements files,
`pytest.ini`, or the workflow itself trigger the gate. Documentation changes
re-run the associated code, contract, schema and lint checks; the workflow does
not semantically validate the truth or completeness of the proof or blueprint
text.

The gate installs `merger/lenskit/requirements.txt` + `requirements-dev.txt`,
asserts `jsonschema` is importable (so contract tests run rather than skip) and
prints its version via `importlib.metadata.version` (not the deprecated
`jsonschema.__version__`), meta-validates the contract, validates the schema path
pattern under ECMAScript regex semantics via Node
(`actions/setup-node@v4`, Node 24, no npm — `node merger/lenskit/tests/test_lens_facet_pattern_ecma.js`),
runs `test_lenses.py` + `test_primary_lens_audit.py` + `test_lens_facets.py`, and
runs ruff on the facet code and tests. The job fails the run on any failing step;
whether that blocks merge depends on branch-protection configuration, which this
proof does not assert (only `pytest.ini` is tracked — there is no nested test
config).

## Validation

All commands are run from the repository root. Tool versions are a local
**validation snapshot** (volatile, not normative): Python 3.11.15, `jsonschema`
4.26.0, `pytest` 9.1.1, Node v22.22.2, and a standalone `ruff` 0.15.8 binary.
`requirements-dev.txt` pins `ruff==0.15.13`; the local 0.15.8 differs, is **not**
representative of CI (which installs the pinned version), and no dependency file
was changed.

- `node merger/lenskit/tests/test_lens_facet_pattern_ecma.js` → ECMAScript parity OK
- `node --check merger/lenskit/tests/test_lens_facet_pattern_ecma.js` → syntax OK
- `python -m pytest -q merger/lenskit/tests/test_lens_facets.py` → 161 passed
  (incl. control/unpaired-surrogate core↔schema parity per cause, accepted
  non-ASCII Unicode incl. emoji, JSON-decoded surrogate-pair acceptance, and the
  producer collection-boundary cases)
- `python -m pytest -q merger/lenskit/tests/test_lenses.py merger/lenskit/tests/test_primary_lens_audit.py merger/lenskit/tests/test_lens_facets.py` → 214 passed
- `python -m pytest -q merger/lenskit/tests/test_contract_version_guards.py merger/lenskit/tests/test_link_integrity.py` → 6 passed
- `python -m pytest -q merger/lenskit/tests/test_anti_hallucination_lint.py` → 33 passed (contracts dir green incl. ECMA-portable schema)
- `python -m pytest -q merger/lenskit/tests/test_planning_registration_ratchet.py` → 101 passed
- `python3 -m scripts.docmeta.check_planning_registration --ratchet --baseline docs/tasks/planning-registration-baseline.json --format human` → 0 findings
- `python scripts/check_no_test_stubs.py` → OK
- `ruff check merger/lenskit/core/lens_facets.py merger/lenskit/tests/test_lens_facets.py` → All checks passed
- `Draft7Validator.check_schema(...)` on the contract → meta-valid; a Python+Node accept/reject matrix over the in-file pattern → parity OK
- repository projection over `git ls-files -z` → all tracked paths accepted; report validates against the schema
- `git diff --check` → clean
- workflow YAML parses; `yamllint`/`actionlint` are not installed in this environment (gap noted; not installed for a single run)

## Claim boundary

This slice does **not** establish: completeness of the facet taxonomy (3 of many
candidates); actual agent usefulness or improved retrieval quality; review
completeness, runtime correctness, test sufficiency, or regression-freedom
outside the checked surfaces; or that facets are consumed anywhere (no bundle
emission, no CLI, no `possible_facets` population, no Lens Cards). The `test`
facet does not assert runner collection, execution, pass, or coverage.

The draft PR presents the smallest evidenced Facet Model v1 slice for review.
Merge approval, task completion, consumer integration and Lens Cards remain a
separate review and reconciliation step.
