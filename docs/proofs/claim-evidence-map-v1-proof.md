# Claim-Evidence-Map v1 Proof

> Erstellt am 2026-05-31.
> Scope: Lenskit F1a + F1b/F2 - referenz-only claim_evidence_map als Bundle-Artefakt mit Surface-/Preflight-Diagnostik.

## 1. Scope

Dieser Slice erzeugt ein neues abgeleitetes Artefakt `.claim_evidence_map.json`,
das deklarierte Claims aus `docs/doc-freshness-registry.yml` mit ihren
deklarierten Evidence-Refs verbindet.

## 2. Negative Finding (historisch)

Vor der Umsetzung war `claim_evidence_map` nicht produziert:

- `docs/doc-freshness-registry.yml` führte `agent-reading-pack-v2-claim-evidence-map` als `partial`.
- `merger/lenskit/core/agent_reading_pack.py` signalisierte die epistemische
  Leerstelle für fehlende Claim-Map.
- Im Bundle-Manifest gab es keine Rolle für die Claim-Evidence-Map.

## 3. Warum referenz-only, kein Verdict

Die Map ist ein Navigation-/Evidence-Index. Sie macht ausschließlich Aussagen
über Referenzen (Claim -> Evidence-Ref) und enthält keine Wahrheitsurteile.

## 4. Contract-Felder

Neuer Contract: `merger/lenskit/contracts/claim-evidence-map.v1.schema.json`

Kernfelder:

- `kind: lenskit.claim_evidence_map`
- `authority: navigation_index`
- `canonicality: derived`
- `risk_class: evidence_index`
- `source.registry_path`, `source.registry_sha256`, `source.generated_at`
- `does_not_establish`
- `claims[*].evidence_refs`
- `claims[*].relation = declared_evidence_ref`

## 5. Producer-Integration

Neuer Producer: `merger/lenskit/core/claim_evidence_map.py`

- `build_claim_evidence_map(...)` ist pure und testbar.
- `produce_claim_evidence_map(...)` lädt/validiert die Registry via bestehender
  `doc_freshness`-Logik, berechnet `registry_sha256` und schreibt deterministisch
  (`indent=2`, `sort_keys=True`, abschließendes Newline).
- `source.generated_at` ist deterministisch aus der Registry abgeleitet
  (`max(last_verified) + T00:00:00Z`) wenn nicht explizit übergeben.

## 6. Bundle-/Manifest-Integration

Die Merge-Pipeline erzeugt optional `.claim_evidence_map.json` aus der Registry
und trägt es als `claim_evidence_map_json` ins Bundle-Manifest ein.

Wenn die Registry vorhanden ist und der Producer fehlschlägt, bricht die
Pipeline mit Fehler ab (kein stilles Wegfallen nur per Log-Warnung).

Manifest-Metadaten:

- contract: `claim-evidence-map` / `v1`
- authority: `navigation_index`
- canonicality: `derived`
- regenerable: `true`
- staleness_sensitive: `true`

## 7. Agent-Reading-Pack-Verhalten

Wenn `claim_evidence_map_json` vorhanden und verifizierbar:

- Rolle erscheint im Pack.
- Summary wird angezeigt (`claims`, `evidence_refs`, `requires_live_check`).
- Klarstellung: navigation/evidence index, not truth.
- `does_not_establish` wird explizit genannt.

Wenn `claim_evidence_map_json` fehlt oder nicht verifizierbar:

- epistemische Leerstelle bleibt sichtbar.

## 8. Post-Emit-/Forensic-Diagnostik (F1b/F2)

- `post_emit_health` prüft `claim_evidence_map_json` explizit auf
  Presence/Hash/Schema (`claim_evidence_map_present`,
  `claim_evidence_map_hash_ok`, `claim_evidence_map_schema_valid`).
- Fehlende Claim-Map bleibt im normalen Post-Emit-Flow sichtbar als
  diagnostischer Skip-Hinweis; `forensic_strict` wird dadurch nicht still
  hochgestuft.
- Neuer Governance-CLI-Check:
  `python3 -m merger.lenskit.cli.main governance forensic-preflight --manifest <bundle.manifest.json>`
  liefert `pass|warn|blocked|fail` für `forensic_strict`-Voraussetzungen.
- Preflight `pass` bedeutet ausschließlich: alle formalen Voraussetzungen sind
  erfüllt; es ist kein Wahrheitsurteil über Claims.

## 9. Non-Changes

- Keine freie Claim-Extraktion.
- Keine LLM-Bewertung.
- Keine Truth-/Support-Verdicts.
- Keine Runtime-Annotation.
- Keine Änderung an `canonical_md`.
- Keine CI-Promotion zu `forensic_strict`.
- Kein Ersatz für Citation Map.

## 10. Verification Commands

- `python3 -m pytest -q merger/lenskit/tests/test_claim_evidence_map.py`
- `python3 -m pytest -q merger/lenskit/tests/test_agent_reading_pack.py merger/lenskit/tests/test_bundle_manifest_schema.py merger/lenskit/tests/test_bundle_manifest_integration.py merger/lenskit/tests/test_post_emit_health.py merger/lenskit/tests/test_forensic_preflight.py merger/lenskit/tests/test_doc_freshness.py`
- `python3 -m merger.lenskit.cli.main governance forensic-preflight --manifest <bundle.manifest.json>`
- `python3 -m merger.lenskit.cli.main doc-freshness inspect`
- `python3 -m merger.lenskit.cli.main doc-freshness update --write`
- `python3 -m ruff check --select=F401,F811,F841,E711,E712 --exclude='**/fixtures/**' merger/lenskit/core merger/lenskit/tests`
- `git diff --check`

## 11. Results

- `python -m pytest -q merger/lenskit/tests/test_claim_evidence_map.py merger/lenskit/tests/test_agent_reading_pack.py merger/lenskit/tests/test_bundle_manifest_schema.py merger/lenskit/tests/test_bundle_manifest_integration.py merger/lenskit/tests/test_doc_freshness.py`
  - Ergebnis: `157 passed`
- `python -m pytest -q merger/lenskit/tests/test_role_completeness.py`
  - Ergebnis: `1 passed`
- `python -m merger.lenskit.cli.main doc-freshness inspect`
  - Ergebnis: `PASS`
- `python -m merger.lenskit.cli.main doc-freshness update --write`
  - Ergebnis: generated view aktualisiert, Registry konsistent
- `python -m ruff check --select=F401,F811,F841,E711,E712 --exclude='**/fixtures/**' merger/lenskit/core merger/lenskit/tests`
  - Ergebnis: `All checks passed`
- `git diff --check`
  - Ergebnis: keine Whitespace-/Patch-Fehler

## 12. Next Slice

Nächster sinnvoller Slice ist die optionale CI-Promotion von
`forensic_strict`, sobald die diagnostische Preflight-Qualität über reale
Bundle-Läufe stabil belegt ist.
