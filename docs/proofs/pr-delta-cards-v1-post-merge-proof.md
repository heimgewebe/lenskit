# PR Delta Cards v1 — Post-Merge Reconciliation Proof

## Identität
- **Repository**: `heimgewebe/lenskit`
- **Feature-PR**: `#793`
- **Feature-Branch**: `feat/pr-delta-cards-v1`
- **Merge-Zeitpunkt**: 2026-06-23T14:38:44Z
- **GitHub-Merge-Commit-SHA**: `fdd8da5f033770203810864911766312a04062ea`
- **Verifizierter main-SHA**: `fdd8da5f033770203810864911766312a04062ea`
- **Datum des Post-Merge-Laufs**: 2026-06-23

## Gegenstand
- **Contract**: `merger/lenskit/contracts/pr-delta-card.v1.schema.json`
- **Source-Contract**: `merger/lenskit/contracts/pr-schau-delta.v1.schema.json`
- **Producer**: `merger/lenskit/core/pr_delta_cards.py`
- **Validator**: `merger/lenskit/core/pr_delta_card_validate.py`
- **Runtime-Requirement**: `merger/lenskit/requirements.txt`
- **Tests**: `merger/lenskit/tests/test_pr_delta_cards.py`, `merger/lenskit/tests/test_pr_delta_card_validate.py`, `merger/lenskit/tests/test_pr_schau_delta_schema.py`
- **Lens-Model-Workflow**: `.github/workflows/lens-model.yml`

## Verifizierte Invarianten
- PR Delta Cards projizieren bereits geladene Source-Mappings.
- Genau eine Card pro Source-Dateieintrag.
- Deterministische Sortierung.
- Kontrollierte Change-Statuswerte.
- Kontrollierte Lens- und Facet-Projektion.
- Source- und Card-Schema validierbar.
- RFC-3339-Validierung ist in sauberer Installation verfügbar.
- Fehlende `date-time`-Capability schlägt fail-closed fehl.
- Card-Validator meldet fehlende Source-Capability als fehlgeschlagene Source-Producer-Kohärenz.
- Kein automatisches Finding.
- Keine Hashprovenienzbehauptung.
- Keine GitHub-PR- oder Commitidentität durch die Card.

## Ausgeführte Gates
- **RFC-3339-Capability-Probe**: Pass.
- **Regressionstests**: `python -m pytest -q ...` — Pass (4/4 passed).
- **PR-Delta-Fokustests**: `python -m pytest -q ...` — Pass (65/65 passed).
- **Anti-Hallucination-Lint-Tests**: `python -m pytest -q ...` — Pass (42/42 passed).
- **Vollständiger Lens-Model-Lauf**: `python -m pytest -q ...` — Pass.
- **Schema-Metavalidierung**: Pass für Draft 7 und Draft 2020-12.
- **ECMAScript-Pfadparität**: `node ...` — Pass.
- **Ruff**: `ruff check ...` — Pass.
- **Governance-Lint**: `python -m merger.lenskit.cli.main governance lint` — Pass (0 Fehler, L3 aktiv, L5 aktiv, keine neue Deferral).
- **Parity Guard**: `python tools/parity_guard.py` — Pass.
- **Planning-Tests**: `python -m pytest -q scripts/docmeta/tests/test_check_planning_registration.py ...` — Pass.
- **Planning-Ratchet**: `python -m scripts.docmeta.check_planning_registration --ratchet ...` — Pass (exit code 0, keine neue Drift).

## Ergebnis
Der definierte PR-Delta-Cards-v1-Slice ist auf main gemergt und auf main post-merge verifiziert.

## Explizite Nicht-Aussagen
Der Proof etabliert nicht:
- vollständiges Repoverständnis
- Runtime-Korrektheit außerhalb der geprüften Pfade
- Testsuffizienz
- Regressionsfreiheit
- tatsächlichen Agentennutzen
- tatsächlichen Retrievalnutzen
- automatische Emission
- Bundle-/Manifest-Integration
- Consumer-/Frontend-Adoption
- Relation Cards
- Guard Relation Cards
- Review- oder Impact-Wahrheit
