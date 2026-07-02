# Repo Complete Audit 2026-07 — Proof

Task: `TASK-REPO-FULL-AUDIT-001` (`docs/tasks/board.md`, `docs/tasks/index.json`)
Register-Eintrag: `docs/architecture/inconsistencies.md` §8

## 1. Scope

Repo-weiter Audit-Sweep (2026-07-02) mit anschließender Remediation in einem
Slice. Geprüft wurden:

- **Testsuite**: voller `pytest`-Lauf (`pytest -q`, Python 3.11 lokal;
  CI-Referenz ist 3.12).
- **Lint**: `ruff check .` (voll) und die CI-Selektion
  (`ruff check --select=F401,F811 --exclude='**/fixtures/**' .`).
- **Repo-eigene Guards**: Planning-Registration-Ratchet, Doc-Freshness
  (`doc-freshness inspect`), Parity Guard (`tools/parity_guard.py`),
  ai-context-Validator.
- **CI-Workflows**: alle 16 Workflows unter `.github/workflows/` auf
  Trigger-/Pfad-/Abdeckungskohärenz.
- **Task-Kontrollflächen**: `docs/tasks/board.md` ↔ `docs/tasks/index.json`
  (ID-Mengen, Status, Evidence-Pfad-Existenz, Tabellenintegrität).
- **Doku**: alle relativen Markdown-Links (50 geprüft), Roadmap-Aussagen
  gegen Repo-Stand.
- **Fleet-Metadaten**: `.ai-context.yml`, `.wgx/profile.yml` gegen realen
  Repo-Inhalt.
- **JS-Tests**: Node-Lauf aller `merger/lenskit/frontends/webui/tests/*.js`
  plus `merger/lenskit/tests/test_lens_facet_pattern_ecma.js`.

## 2. Befunde und Remediation

Vollständige Befundtabelle: `docs/architecture/inconsistencies.md` §8.
Kurzfassung der in diesem Slice umgesetzten Änderungen:

| # | Änderung | Dateien |
| --- | --- | --- |
| 1 | Full-Suite-CI-Gate eingeführt (pytest ohne `browser`/`doc_freshness_live` + Node-Job für WebUI-JS-Tests) | `.github/workflows/test-suite.yml` |
| 2 | Stale Artefakt-Annahmen repariert: Merge-Artefakt wird explizit selektiert statt `artifact_ids[0]`/`len==1` (Report-Artefakte aus TASK-SERVICE-002/003 werden ausgefiltert) | `merger/lenskit/tests/test_merges_dir_drift.py` |
| 3 | `.agent_entry_manifest.json` als Bundle-Level-Suffix registriert | `merger/lenskit/tests/test_per_repo_cohesion.py` |
| 4 | Browser-Tests skippen sauber ohne pytest-playwright (Collection-Hook) | `merger/lenskit/tests/conftest.py` |
| 5 | Board/Index reconciled: 8 fehlende Tasks in `index.json` ergänzt, 1 fehlender Task ins Board, Tabellen-Leerzeile entfernt, Audit- und Folge-Tasks registriert | `docs/tasks/board.md`, `docs/tasks/index.json` |
| 6 | Fleet-Metadaten auf lenskit korrigiert (waren Kopien aus `heimgewebe/tools`) | `.ai-context.yml`, `.wgx/profile.yml` |
| 7 | Stale Blueprint-File-Proof-Aussage aktualisiert | `docs/roadmap/lenskit-master-roadmap.md` |
| 8 | Audit-Register-Sektion + dieser Proof + Changelog-Eintrag | `docs/architecture/inconsistencies.md`, `docs/proofs/repo-complete-audit-2026-07-proof.md`, `CHANGELOG.md` |

## 3. Verifikation

Vor dem Fix (Baseline, lokaler Lauf 2026-07-02):

```
pytest -q            → 4 failed, 3167 passed, 11 skipped, 10 errors
```

- `test_merges_dir_drift.py`: 3 Failures (AssertionError `2 == 1`;
  KeyError `'json'`/`'md'` — `artifact_ids[0]` war der `pre_pull_report`).
- `test_per_repo_cohesion.py`: 1 Failure („Should have 2 JSON sidecars,
  found 3" — das dritte war `*_merge.agent_entry_manifest.json`).
- `test_webui_payload.py`: 10 Errors („fixture 'page' not found").

Nach dem Fix:

```
pytest -q -m "not browser and not doc_freshness_live"  → grün (0 failed, 0 errors)
```

Guards nach dem Fix erneut grün: Planning-Ratchet (0 new findings, exit 0),
Doc-Freshness (PASS), Parity Guard (PASS), ai-context-Validator (OK),
CI-Lint-Selektion sauber. Node-Läufe aller sechs JS-Testdateien: PASS.

## 4. Was dieser Proof NICHT belegt

- Kein Beweis der Abwesenheit weiterer Defekte; der Sweep ist ein
  Stichtags-Audit, kein vollständiger Korrektheitsnachweis.
- Der grüne Full-Suite-Lauf beweist keine Produktionsreife, Performance
  oder Sicherheit des Service.
- Die Board/Index-Reconciliation beweist nicht die inhaltliche Korrektheit
  historischer Task-Statusaussagen, nur die Registry-Parität zum Stichtag.

## 5. STOP (bewusst nicht getan)

- **Kein Style-Rundumschlag**: die ~120 ruff-Findings außerhalb des
  CI-Gates bleiben unangetastet (`TASK-LINT-RUFF-SCOPE-001`).
- **Keine Workflow-Löschung/-Umbau** von `contracts-validate.yml`
  (`TASK-CI-CONTRACTS-PATHS-001`); Entscheidung braucht metarepo-Kontext.
- **Kein `class`-Wechsel** in `.wgx/profile.yml`: gültiges Klassen-Set wird
  vom externen `heimgewebe/wgx`-Guard kontrolliert; nur belegbar falsche
  Felder (repo, lang, tags, Beschreibung) wurden korrigiert.
- **Kein Board↔Index-Paritäts-Guard** implementiert (möglicher Folge-Slice;
  der bestehende Planning-Ratchet prüft eine andere Invariante).
- **Keine Runtime-/Producer-Änderung**: `runner.py`-Report-Registrierung und
  `merge.py`-Emission bleiben unverändert; nur Tests wurden an dokumentiertes
  Ist-Verhalten angepasst.
