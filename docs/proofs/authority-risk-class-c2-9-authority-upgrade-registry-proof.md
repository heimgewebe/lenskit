# Authority/Risk-Class C2.9 — Authority-Upgrade Registry / Upgrade Declaration v0

## 1. Scope

C2.9 closes the first gap identified by the C2.8 adoption pilot
(`docs/proofs/authority-risk-class-c2-8-adoption-pilot-proof.md` §9.1). The C2.7
marker-gated AST lint detects when a *declared* low-authority value flows into a
*declared* canonical sink (rules L1/L2/L4). C2.8 ran it against real code and found
**four intentional L4 detections** in `core/merge.py`: the `derived_projection`
value `md_parts` flowing into `resolve_canonical_md` — which is precisely the
canonical-selection step, i.e. a *legitimate, reviewed authority upgrade*, not a
bug. The lint could not tell an intentional upgrade apart from a real L4 finding.

C2.9 adds the smallest **machine-readable upgrade declaration** so the lint can
make that distinction — **without** suppressing the detection. It is the
"Registry first, analysis later" slice: a registry + report integration, *not* a
dataflow/alias engine.

New / changed files:

- `merger/lenskit/core/authority_upgrade_registry.py` (new — registry + validation + matching)
- `merger/lenskit/core/anti_hallucination_ast_lint.py` (finding gains `authority`/`sink`; report gains `declared_upgrades`)
- `merger/lenskit/cli/cmd_governance.py` (human report surfaces declared upgrades)
- `merger/lenskit/tests/test_anti_hallucination_ast_lint.py` (25 → 39 tests)
- `docs/proofs/authority-risk-class-c2-9-authority-upgrade-registry-proof.md` (this file)
- `docs/roadmap/lenskit-master-roadmap.md`, `docs/testing/test-matrix.md` (status)

This slice adds **no** new lint rules, **no** type inference, **no**
dataflow/alias analysis, **no** runtime annotation (C4 stays open), **no**
producer emission, **no** contract/schema mutation, **no** new blocking CI gate.

## 2. Negative Finding — The Gap Was Real and Tracked

Verified by doc + code inspection before writing any code:

| Claim | Evidence |
|-------|----------|
| The upgrade-declaration gap was the **explicit, tracked** next step | C2.8 proof §9.1 ("Authority upgrade declarations … analogous to … an explicit entry in an authority registry. Without this, the … lint will have an irremovable L4 false positive at every canonical-selection call"); §5 row "Authority registry needs an 'upgrade declaration' mechanism"; roadmap C2.8 "Nächste Schritte (C2.9+): (1) Authority-Upgrade-Deklaration"; test-matrix "Offen: Authority-Upgrade-Deklaration". |
| No registry / upgrade-declaration mechanism existed | No `authority_upgrade_registry` module; `anti_hallucination_ast_lint.py` had no concept of an allowed upgrade; the four merge.py detections counted as warnings (exit 1). |
| The four detections are **known-intentional** | C2.8 proof §4.1: `resolve_canonical_md()` "IS the function that upgrades a derived path to canonical status. The crossing is intentional." |

The Stop-Kriterium (no duplication) is satisfied: this is the declared C2.9 work,
not a re-implementation.

## 3. The Registry (Upgrade Declaration v0)

A declared upgrade is one frozen `AuthorityUpgrade` record
(`authority_upgrade_registry.py`):

| Field | Meaning |
|-------|---------|
| `rule` | which AST rule the detection is (`L1`/`L2`/`L4`) |
| `source_authority` | the low-authority class of the flowing value (e.g. `derived_projection`) |
| `target_authority` | the sink's required authority — `canonical_content` (the only sink authority the AST lint models in v0) |
| `sink` | the canonical-sink name the value flows into |
| `file_suffix` | file-level scope constraint for the declared upgrade |
| `reason` | mandatory, substantive rationale (audit trail) |
| `symbol` *(optional)* | narrows the declaration to a single variable name; `None` = any |

The v0 registry has exactly one entry — the merge.py canonical-selection upgrade:

```python
AuthorityUpgrade(
    rule="L4",
    source_authority="derived_projection",
    target_authority="canonical_content",
    sink="resolve_canonical_md",
    file_suffix="merger/lenskit/core/merge.py",
    reason="resolve_canonical_md() is the canonical-selection step: by bundle "
           "contract it selects md_parts[0] as the single canonical markdown "
           "source of truth. Passing the derived_projection list … into it IS "
           "the deliberate, reviewed authority upgrade … not an accidental "
           "escalation. See <this proof>.",
)
```

It is **file-scoped + sink-scoped** (no `symbol`): the declaration binds the
upgrade to `merger/lenskit/core/merge.py` and `resolve_canonical_md`, so same-name
sinks in other files are not treated as declared upgrades. The optional `symbol`
field exists for cases where an upgrade should be narrowed to one name (proven by
test).

The registry is a **lint-only static-analysis artifact**, exactly like the C2.7
markers: it is never emitted into any bundle artifact, mutates no contract/schema,
and is not a runtime annotation (C4 stays open).

## 4. AST-Lint Integration — Detect, Then Declare (Not Suppress)

The integration is deliberately layered so the smoke detector is **never switched
off**:

1. **Detection is registry-blind.** `lint_source`/`lint_file` still fire on every
   declared low-authority → canonical flow and still produce a raw L4 finding for
   `md_parts → resolve_canonical_md`. (Proven: `test_declared_upgrade_is_detected_then_allowed_not_suppressed`
   asserts the raw finding exists *before* registry partitioning.)
2. **Findings carry structured `authority` + `sink`** (not only prose) so the
   registry can match without parsing the message.
3. **Partitioning happens at report assembly.** `AstLintReport.add_findings()`
   calls `classify_findings()`, routing each raw finding into either
   `findings` (real warning, no declaration matches) or `declared_upgrades`
   (a validated declaration matches).
4. **Declared upgrades stay visible.** The report emits `declared_upgrades`
   (each with the detection *and* the matched declaration + reason) **and** the
   full `authority_upgrade_registry`. Nothing is silently swallowed. `status`
   stays `pass` only because there are no *un-declared* warnings; the four
   upgrades remain machine-readable.

Severity / counting semantics:

- `finding_count` counts **real warnings only**. Declared upgrades are counted
  separately as `declared_upgrade_count`.
- `status == "warn"` iff there is ≥1 real finding; declared upgrades alone →
  `status == "pass"` → CLI exit 0. (Stop-criterion: the four merge.py cases no
  longer count as warn-findings.)

## 5. Validation — Not Silently Lenient

`validate_registry()` rejects (returns errors for) any entry that is:

- an unknown `rule` (not in `RULES_COVERED`);
- a `(rule, source_authority)` pair that can *never* produce that rule (e.g.
  `L4` with `diagnostic_signal`, which the lint emits as `L2`) — a dead, silent
  no-op declaration;
- a `target_authority` other than `canonical_content`;
- an empty `sink`, an empty (whitespace) `symbol`, or a missing/token `reason`
  (< 12 chars).

`match_upgrade()` / `classify_findings()` call validation first and **raise
`ValueError`** on a malformed registry — so a bad declaration surfaces loudly
(the CLI converts it to exit 2) rather than being quietly accepted. (Proven:
`test_invalid_registry_entry_is_rejected_not_silently_accepted`, parametrized over
all seven failure modes.)

## 6. Tests (25 → 39)

Updated (C2.7/C2.8 semantics preserved, not watered down):

- `test_report_self_declares_…`: report `stage` is now `C2.9`; asserts the new
  `declared_upgrade_count`, the `declared_upgrades`/`authority_upgrade_registry`
  arrays, and the new `does_not_mean` honesty entry. The L2 fixture (a
  `runtime_observation` escalation, *not* in the registry) still warns.
- `test_real_tree_merge_l4_are_declared_upgrades_not_warnings` (was
  `…c2_8_pilot_findings_match_expected`): real tree now has **0 real findings**
  and **4 declared upgrades** at the exact known lines (5699/5714/5824/5843),
  each `derived_projection → canonical_content @ resolve_canonical_md`.
- `test_cli_governance_ast_lint_exits_zero_when_only_declared_upgrades` (was
  `…exits_one_for_c2_8_findings`): declared-only → exit 0.
- `test_cli_governance_ast_lint_json_contains_declared_upgrades` (was
  `…json_is_valid`): `finding_count == 0`, `declared_upgrade_count == 4`, the
  declared-upgrade records and the registry are present.

New (C2.9):

- `…detected_then_allowed_not_suppressed` — raw L4 fires; report reclassifies it.
- `…unregistered_derived_projection_into_canonical_sink_stays_l4` — same class,
  different (undeclared) sink → still a warning.
- `…l2_escalation_into_same_sink_is_not_matched_by_l4_declaration` — rule+source
  specificity (an L2 into `resolve_canonical_md` is **not** reclassified).
- `…shipped_registry_is_valid_and_declares_the_merge_upgrade`.
- `…symbol_narrowing_scopes_a_declaration` — optional `symbol` narrows / matches.
- `…match_upgrade_returns_none_for_unrelated_finding`.
- `…invalid_registry_entry_is_rejected_not_silently_accepted` (×7 modes).
- `…valid_custom_registry_entry_passes_validation`.

## 7. Non-Changes (out of scope)

- **No** new lint rules; L1/L2/L4 detection logic is unchanged (still marker-gated).
- **No** type inference, **no** dataflow/alias analysis. The indirect
  `health → PackModel → render` flow (C2.8 §4.3) remains undetected and is **not**
  addressed here — that is a later slice.
- **No** runtime annotation; **C4 remains open and untouched.** The registry is a
  static-analysis-only artifact, never an artifact field.
- **No** producer emission, **no** contract / schema mutation, **no** manifest
  mutation, **no** change to `canonical_md`, retrieval/ranking, or the export gate (C5).
- **No** modification of the C2.4 contract lint (`anti_hallucination_lint.py`).
- **No** new blocking CI workflow. The existing `Anti-Hallucination Contract Lint`
  gate runs only `governance lint` + `test_anti_hallucination_lint.py` (both
  unchanged-green); `governance ast-lint` is still not wired into CI.
- **No** silent suppression. A declared upgrade is detected and surfaced; it is
  reviewed intent, **not** a runtime-correctness proof (recorded in `does_not_mean`).

## 8. Verification Commands

```bash
# Existing contract lint (unchanged; min-test requirement) — stays PASS, exit 0
python3 -m merger.lenskit.cli.main governance lint

# AST lint: 0 real findings, 4 declared upgrades, status pass, exit 0
python3 -m merger.lenskit.cli.main governance ast-lint
python3 -m merger.lenskit.cli.main governance ast-lint --json

# Targeted suites
python3 -m pytest -q \
  merger/lenskit/tests/test_anti_hallucination_lint.py \
  merger/lenskit/tests/test_anti_hallucination_ast_lint.py

# Regression
python3 -m pytest -q \
  merger/lenskit/tests/test_contract_inference_boundaries.py \
  merger/lenskit/tests/test_contract_version_guards.py \
  merger/lenskit/tests/test_cli_bundle_health.py \
  merger/lenskit/tests/test_cli_context_quality.py

# Import hygiene (repo CI gate selection)
python3 -m ruff check --select=F401,F811,F841,E711,E712 --exclude='**/fixtures/**' \
  merger/lenskit/core/authority_upgrade_registry.py \
  merger/lenskit/core/anti_hallucination_ast_lint.py \
  merger/lenskit/cli/cmd_governance.py \
  merger/lenskit/tests/test_anti_hallucination_ast_lint.py

git diff --check

## 9. Results (local run)

- `governance lint`: `PASS` — 38 scanned, 0 errors, 0 deferred, exit 0 (unchanged).
- `governance ast-lint`: `PASS` — 92 files scanned, 0 skipped, **0 findings**,
  **4 declared upgrades** (all L4 in merge.py, `derived_projection →
  canonical_content @ resolve_canonical_md`), exit 0. Non-blocking (`blocking: false`).
  *(File count is 92, +1 vs C2.8's 91: the new registry module is itself scanned
  and yields 0 findings.)*
- `test_anti_hallucination_lint.py` (33) + `test_anti_hallucination_ast_lint.py` (39): **72 passed**.
- Regression (contracts/version-guards/cli): 45 passed, no regressions.
- `ruff --select=F401,F811,F841,E711,E712` (and repo-wide `F401,F811`): clean.
  `git diff --check`: clean.
- Python: 3.11.15 (local). CI runs 3.12.

## 10. Precise Next Slice (C2.10+)

C2.9 closes gap (1) from C2.8 §9. Still open, in increasing risk order:

1. **Object-intermediary / dataflow tracking.** The indirect
   `health (diagnostic_signal) → PackModel → render_agent_reading_pack` flow
   (C2.8 §4.3) is invisible to the file-scoped engine. Detection requires per-field
   authority on the constructor or a real dataflow analysis. This is the key open
   work for the inference-based lift.
2. **Lift from marker-gated to inference-based** detection, with the
   false-positive calibration (blueprint §6 Phase-3 "FP-Rate > 10% → Regel
   zurückziehen") measured *before* any CI promotion. The registry built here is the
   prerequisite that lets such a lint declare its intentional upgrades.
3. **CI promotion:** only after a measured low FP rate, a path-scoped blocking gate.
4. **C4 (runtime annotation)** remains a separate, still-open track and is **not**
   a prerequisite for the above.
```
