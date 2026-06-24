# Guard Relation Cards v1b (Target Proof — validates_schema)

## Status und Scope

Dieser PR enthält einen diagnosis-only Target-Proof für den Guard-Relation-Kandidaten `validates_schema`.
Es ist **kein Produktionscode** enthalten. Der Scope ist strikt auf die statische Untersuchung einer
Schema-Validierungsbeziehung begrenzt. Andere Guard-Relation-Kandidaten (`tests_by_path`,
`checks_surface`, `checks_cli`, `checks_security`) werden in diesem Proof nicht bewertet.

Die Bezeichnung `validates_schema` ist im Roadmap-Kontext mehrdeutig. Abschnitt 6 behandelt die
Namensfrage ausführlich.

## Live-Basis und Base-SHA

- **Repo**: `/home/alex/repos/lenskit` (heimgewebe/lenskit)
- **Branch**: `docs/guard-relation-validates-schema-v1b-target-proof`
- **Base-SHA**: `05bbd0d608afa8faf581887a455d4dcf6fa15ae9`
- **Merge-SHA PR #798**: `05bbd0d608afa8faf581887a455d4dcf6fa15ae9` (identisch; PR #798 ist in `origin/main` enthalten)
- **Inventardatei**: `/tmp/lenskit-validates-schema-inventory.txt` (590 Pfade, SHA-256: `19ccdd599e32d683b97d71a86b05594b825440bda1b900d32a756517f637b50a`)

## Dokumentarischer Ausgangszustand

- **Relation Card v1** ist `imports`-only (`merger/lenskit/contracts/relation-card.v1.schema.json`).
- Der Producer `merger/lenskit/core/relation_cards.py` projiziert vorhandene Importkanten.
- `validates_schema` ist **nicht** als Relationstyp implementiert.
- Es existiert **kein** Guard-Relation-Producer.
- Ein Target-Proof darf diese Grenze nicht verändern.

## Belegter aktueller Codebestand

Die Codebasis enthält fünf produktive Validator-Module, die `jsonschema` verwenden,
um Instanzen gegen spezifische Contract-Schemata zu validieren:

1. `merger/lenskit/core/lens_card_validate.py` → `merger/lenskit/contracts/lens-card.v1.schema.json`
2. `merger/lenskit/core/pr_delta_card_validate.py` → `merger/lenskit/contracts/pr-delta-card.v1.schema.json`
3. `merger/lenskit/core/relation_card_validate.py` → `merger/lenskit/contracts/relation-card.v1.schema.json`
4. `merger/lenskit/core/relation_card_validate.py` → `merger/lenskit/contracts/architecture.graph.v1.schema.json`
5. `merger/lenskit/core/post_emit_health.py` → `merger/lenskit/contracts/claim-evidence-map.v1.schema.json`
6. `merger/lenskit/core/post_emit_health.py` → `merger/lenskit/contracts/bundle-manifest.v1.schema.json`

Zusätzlich validieren `parity_state.py` und `forensic_preflight.py` gegen interne Strukturen
(keine `*.schema.json`-Pfade) und werden hier nicht als Schema-Validierungsrelationen geführt.

## Semantik vor der Messung

### Klassen von Schema-Beziehungen

| Klasse | Definition |
|---|---|
| `instance_validation_direct` | Source lädt ein bestimmtes Schema und reicht Instanz + Schema direkt an eine JSON-Schema-Validierungs-API. |
| `instance_validation_delegated` | Source lädt ein bestimmtes Schema und übergibt es an einen Helper; der Helper ruft nachweisbar JSON-Schema-Validierung auf. |
| `schema_meta_validation` | Source prüft, ob das Schema selbst ein gültiges Schema ist (`check_schema`). |
| `load_only` | Schema wird gelesen oder referenziert, aber nicht an eine Validierungs-API weitergegeben. |
| `path_reference_only` | Schemapfad wird nur erwähnt, nicht geladen. |
| `unresolved_dynamic` | Schemapfad oder Weitergabe ist statisch nicht eindeutig auflösbar. |
| `test_only` | Beziehung existiert nur in Testcode. |

### Akzeptanzregel

Eine Beziehung gilt nur als `instance_validation_direct` oder `instance_validation_delegated`, wenn:

1. Source-Modul und öffentliches Symbol bekannt sind.
2. Schemapfad ist statisch eindeutig.
3. Schema existiert im Inventar.
4. Eine Instanz und das Schema erreichen eine konkrete `validate()`-API.
5. Die Aufrufkette ist vollständig nachvollziehbar.
6. Options- oder Degradationsbedingungen sind dokumentiert.
7–10. Die Beziehung beruht nicht nur auf Namensähnlichkeit, Testnamen, Import oder Pfadkonstante.

Ein Modul, das ein Schema lädt und anschließend nur Felder daraus liest, validiert damit noch nichts.

## Source-Population

- **Produktions-Python-Dateien**: aus `merger/lenskit/core/` und weiteren produktiven Pfaden.
- **Test-Python-Dateien**: Pfade mit `/tests/`, `_test`-Präfix oder `tests/`-Wurzel.
- **Schema-Dateien**: alle `*.schema.json` im Inventar.

## Analyseverfahren

1. Base-Inventar aus `git ls-tree -r --name-only 05bbd0d6` binden.
2. Alle `*.schema.json` sammeln.
3. Für jeden bekannten Validator den statischen Schemapfad via `_SCHEMA_PATH`/`schema_path`-Literal auflösen.
4. Jede Callsite manuell prüfen: Instanz + Schema → `validate()`.
5. Klassifizieren nach obiger Tabelle.
6. Summen durch Assertions schließen.

## Evidenz- und Ausschlussklassen

- **Eingeschlossen**: produktive Validator-Module, die `*.schema.json` laden und `jsonschema.validate(...)` aufrufen.
- **Ausgeschlossen**: Testcode, interne Validierung ohne Schema-Pfad (`parity_state.py`, `forensic_preflight.py`), reine Importe ohne Validierungsaufruf, Schema-Metavalidierung ohne Instanzvalidierung.

## Vollständige Mengen- und Summenübersicht

| Metrik | Wert |
|---|---|
| Inventar-Pfade | 590 |
| `*.schema.json`-Dateien | 54 |
| Produktions-Validator-Schema-Paare (Candidates) | 6 |
| `instance_validation_direct` | 6 |
| `instance_validation_delegated` | 0 |
| `schema_meta_validation` | 0 |
| `load_only` | 48 |
| `path_reference_only` | 0 |
| `unresolved_dynamic` | 0 |
| `test_only` | 0 |

Summe: `6 + 0 + 0 + 48 + 0 + 0 + 0 = 54 = candidate_callsite_count`. ✅

## Tabelle: direkte Instanzvalidierungen

| Source-Symbol | Source-Pfad | Callsite | Schema-Pfad | Engine | Dependency-Modus |
|---|---|---|---|---|---|
| `validate_lens_card` | `merger/lenskit/core/lens_card_validate.py` | 133–136 | `merger/lenskit/contracts/lens-card.v1.schema.json` | jsonschema | conditional_jsonschema_available |
| `validate_pr_delta_card` | `merger/lenskit/core/pr_delta_card_validate.py` | 133–136 | `merger/lenskit/contracts/pr-delta-card.v1.schema.json` | jsonschema | conditional_jsonschema_available |
| `validate_relation_card` | `merger/lenskit/core/relation_card_validate.py` | 157–158 | `merger/lenskit/contracts/relation-card.v1.schema.json` | jsonschema | conditional_jsonschema_available |
| `validate_relation_card` | `merger/lenskit/core/relation_card_validate.py` | 228–229 | `merger/lenskit/contracts/architecture.graph.v1.schema.json` | jsonschema | conditional_jsonschema_available |
| `_validate_claim_evidence_map` | `merger/lenskit/core/post_emit_health.py` | 329–331 | `merger/lenskit/contracts/claim-evidence-map.v1.schema.json` | jsonschema | conditional_jsonschema_available |
| `_validate_bundle_manifest` | `merger/lenskit/core/post_emit_health.py` | 404–406 | `merger/lenskit/contracts/bundle-manifest.v1.schema.json` | jsonschema | conditional_jsonschema_available |

## Tabelle: delegierte Instanzvalidierungen

Keine. Alle sechs produktiven Validatoren rufen `jsonschema.validate(...)` oder `Draft7Validator(...).iter_errors(...)` direkt auf. Die `jsonschema_dependency`-Hilfsfunktion meldet nur den Dependency-Status, sie delegiert keine Validierung.

## Tabelle: Schema-Metavalidierungen

Keine. `jsonschema.Draft7Validator.check_schema(active_schema)` wird nur aufgerufen, um das geladene **Contract-Schema** auf Gültigkeit zu prüfen, bevor es für die Instanzvalidierung verwendet wird. Dies ist Teil der direkten Validierungskette, keine separate Meta-Validierung.

## Tabelle: load_only

48 `*.schema.json`-Dateien haben keinen produktiven Validator, der sie über einen statisch nachvollziehbaren Pfad lädt und validiert. Sie sind Contract-Definitionen oder nicht verwendete Schemata.

## Tabelle: path_reference_only

Keine. Alle erfassten Schemapfade werden tatsächlich geladen, falls ein zugehöriger produktiver Validator existiert.

## Tabelle: unresolved_dynamic

Keine. Alle Validator-Schema-Paare sind statisch über `_SCHEMA_PATH`- oder `schema_path`-Literal gebunden.

## Test-only-Befunde

Keine. Alle sechs akzeptierten produktiven Validatoren befinden sich in Produktionsdateien. In den Testdateien wurden keine zusätzlichen Validierungs-Schema-Paare gefunden, die über die bereits erfassten produktiven Validatoren hinausgehen.

## Optionalitäts- und Degradationsmodi

Alle sechs produktiven Validatoren verwenden dasselbe Muster:

1. `jsonschema` wird optional importiert (`_load_jsonschema()`).
2. Bei `ImportError` wird `skipped_unavailable` mit `reason=dependency_unavailable` zurückgegeben.
3. Bei verfügbarem `jsonschema` wird `Draft7Validator.check_schema()` + `Draft7Validator()` verwendet.
4. Die Validierung ist **fail-closed**: fehlendes `jsonschema` führt zu `fail`/`skipped_unavailable`, niemals zu `pass`.

Diese Konsistenz erlaubt die einheitliche Klassifizierung als `conditional_jsonschema_available`.

## Mehrfachschema-Fälle

- `merger/lenskit/core/relation_card_validate.py` validiert gegen **zwei** Schemata (`relation-card.v1.schema.json` und `architecture.graph.v1.schema.json`) in derselben `validate_relation_card()`-Funktion. Es handelt sich um zwei getrennte `instance_validation_direct`-Beziehungen, nicht um eine.
- `merger/lenskit/core/post_emit_health.py` validiert gegen **zwei** Schemata (`claim-evidence-map.v1.schema.json` und `bundle-manifest.v1.schema.json`) in getrennten Funktionen. Ebenfalls zwei getrennte Beziehungen.

## Schema-Dateien ohne gefundenen Produktionsvalidator

48 der 54 `*.schema.json`-Dateien haben keinen produktiven Validator. Dazu gehören unter anderem:

- `merger/lenskit/contracts/lens-facet.v1.schema.json`
- `merger/lenskit/contracts/lens-card.v1.schema.json` — **wird** validiert (siehe Tabelle)
- `merger/lenskit/contracts/relation-card.v1.schema.json` — **wird** validiert
- `merger/lenskit/contracts/required-reading-protocol.v1.schema.json`
- `merger/lenskit/contracts/answer-compliance.v1.schema.json`
- `merger/lenskit/contracts/agent-consumption-trace.v1.schema.json`
- `merger/lenskit/contracts/agent-entry-manifest.v1.schema.json`
- `merger/lenskit/contracts/primary-lens-audit.v1.schema.json`
- `merger/lenskit/contracts/pr-delta-card.v1.schema.json` — **wird** validiert
- `merger/lenskit/contracts/bundle-surface-validation.v1.schema.json`
- (und 38 weitere Contracts ohne nachgewiesenen produktiven Validator)

## Consumeranalyse

1. **Implementierter Consumer**: Kein aktueller Consumer nutzt eine persistierte `validates_schema`-Relation.
2. **Verbindlich spezifizierter Consumer**: Nicht vorhanden. Die Roadmap (`lenskit-master-roadmap.md`) listet `validates` als geplanten Relationstyp, aber ohne spezifizierten Consumer.
3. **Möglicher zukünftiger Consumer**: Relation-aware Retrieval-Ranking, Contract-Review-Tools, Impact-Analyse — jeweils ohne verbindliche Spezifikation.
4. **Nur plausible Idee**: Test-Coverage-Aussagen, Change-Impact-Schätzungen.

Fazit: **Kein Persistenzbedarf belegt.**

## Relationsrichtung

Mögliche Richtungen:

| Richtung | Semantik |
|---|---|
| Validator → Schema | "validates data against schema" |
| Schema → Validator | "is used by validator" |

Für die sechs gefundenen Beziehungen ist `Validator → Schema` die natürliche Lesart. Eine bidirektionale Persistenz wird nicht empfohlen, solange kein Consumer eine Richtung verlangt.

## Benennungsempfehlung

Der Roadmap-Name `validates_schema` ist mehrdeutig:

- **Missverständnis 1**: "Validiert das Schema selbst" (Schema-Metavalidierung).
- **Missverständnis 2**: "Validiert Daten gegen das Schema" (Instanzvalidierung).

Empfehlung für einen späteren Contract: **`validates_against_schema`** oder **`instance_validation_against`**.

Der Proof ändert den Roadmap-Namen nicht still. Er dokumentiert die Ambiguität und empfiehlt Präzisierung.

## Contract- und Persistenzoptionen

### Ergebnis A – persistierter Contract grundsätzlich begründbar

Nicht erfüllt: Kein verbindlicher Consumer. Persistenz hätte keinen belegten Vorteil gegenüber On-Demand-Auflösung.

### Ergebnis B – On-Demand-Auflösung genügt

Teilweise erfüllt: Die sechs Beziehungen sind reproduzierbar und statisch gebunden. On-Demand-Auflösung über `_SCHEMA_PATH`-Replikation wäre möglich. Aber: 48 Schema-Dateien ohne Validator erzeugen eine große Noise-Fläche.

### Ergebnis C – zurückstellen

**Empfohlen.** Semantik ist klar genug für eine Diagnose, aber:

- `validates_schema` vs. `validates_against_schema`: Namensambiguität nicht aufgelöst.
- Consumer fehlt.
- Persistenzbedarf nicht belegt.
- Hoher Noise-Faktor (48 nicht-verwendete Schemata).

## Entscheidung

Das Gate für einen persistierten `validates_schema`-Contract ist vorerst geschlossen.

Ein On-Demand-Diagnose-Tool, das bei Bedarf die sechs produktiven Validator-Schema-Paare auflöst, bleibt eine mögliche spätere Evaluationsmaßnahme.

Andere Guard-Relation-Kandidaten (`tests_by_path`, `checks_surface`, `checks_cli`, `checks_security`) wurden in diesem Proof nicht bewertet.

Begründung:
- Kein aktiver oder verbindlich spezifizierter Consumer.
- Namensambiguität (`validates_schema` vs. `validates_against_schema`).
- Persistenzbedarf nicht belegt.
- 48 von 54 Schema-Dateien haben keinen produktiven Validator → hoher Anteil an `load_only`.

Falls später ein persistierter Contract entsteht, müssen Name, Richtung, Source-Kohärenz und Dependency-Modi separat entschieden werden. Dieser Proof entscheidet diese Punkte nicht abschließend.

## Alternative On-Demand-Auflösung

Eine mögliche spätere Implementierung könnte:

1. Die festen `_SCHEMA_PATH`- und `schema_path`-Literalbindungen replizieren.
2. Für jedes produktive Validator-Modul eine deterministische Auflösung anbieten.
3. `conditional_jsonschema_available` als Dependency-Modi sichtbar machen.
4. Nicht verifizierbare Fälle (`unresolved_dynamic`) offen ausgeben.

Dieser Proof entscheidet keine solche Implementierung.

## Offene epistemische Leerstellen

- Es fehlt eine verbindliche Consumerfrage, die `validates_schema` oder `validates_against_schema` benötigt und Persistenzbedarf, Richtung und Qualitätsanforderungen festlegt.
- Die statische Analyse erfasst nur `*.schema.json`-Dateien. Validierungen gegen interne Datenstrukturen (z.B. `parity_state.py`, `forensic_preflight.py`) wurden nicht als Schema-Validierungsrelationen modelliert.
- Dynamisch geladene Schemata (z.B. über Konfigurationsdateien) wurden nicht untersucht.
- Die Dependency-Semantik wurde nur auf `jsonschema`-Verfügbarkeit eingeschränkt; weitere Runtime-Bedingungen (z.B. feature flags) wurden nicht verfolgt.

## Negativsemantik

Eine Schema-Validierungsrelation beweist nicht:

- `schema_correctness` — Das Schema selbst kann fehlerhaft sein.
- `validator_completeness` — Nicht alle Validatoren wurden untersucht.
- `runtime_execution` — Die Validierung wird nicht in jeder Runtime ausgeführt.
- `runtime_correctness` — Fehlendes `jsonschema` degradiert zu `skipped_unavailable`.
- `test_sufficiency` — Es wurden keine Test-Impact-Aussagen getroffen.
- `regression_absence` — Es wurde keine Regressionsanalyse durchgeführt.
- `change_impact` — Eine Namensrelation beweist keinen Change Impact.
- `consumer_need` — Kein Consumer wurde identifiziert.
- `repo_understood` — Die Analyse ist statisch und begrenzt.
- `forensic_ready` — Es wurde keine vollständige Callgraph-Verfolgung durchgeführt.

Ein erfolgreicher statischer Nachweis bedeutet nur:

> Im untersuchten Snapshot existiert eine statisch nachvollziehbare Codekette zwischen einer Validierungsstelle und einem bestimmten Schema-Pfad.

## Implementierungsgates

Falls ein persistierter `validates_schema`-Contract zukünftig erwogen wird, müssen folgende Gates bestanden werden:

1. **Namensklärung**: `validates_schema` → `validates_against_schema` (oder äquivalent präzise).
2. **Consumer-Nachweis**: Mindestens ein implementierter oder verbindlich spezifizierter Consumer.
3. **Richtung**: `Validator → Schema` oder `Schema → Validator` festlegen.
4. **Source-Kohärenz**: Alle produktiven Validatoren und ihre Abhängigkeiten sind erfasst.
5. **Dependency-Modi**: `conditional_jsonschema_available` und Degradationspfade sind im Contract modelliert.
6. **Schema-Meta vs. Instanz**: Validierung des Schemas selbst muss von Instanzvalidierung getrennt werden.
7. **Load-only-Filter**: 48 nicht-verwendete Schemata müssen von der Persistenz ausgeschlossen werden.
8. **Negativsemantik**: Die oben genannten Negativaussagen müssen im Contract explizit verankert sein.
9. **Review**: Jede der sechs produktiven Beziehungen muss manuell gegen den Code geprüft sein.
10. **Goldset**: Bevor persistiert wird, muss ein Goldset die Korrektheit der Klassifikation belegen.

Dieser Proof hat keines dieser Gates geöffnet.

## Reproduktionshinweise

Das Inventar wird mit:

```bash
git ls-tree -r --name-only 05bbd0d608afa8faf581887a455d4dcf6fa15ae9
```

direkt aus dem Git-Baum des Base-Commits gewonnen.

Die Klassifikation basiert auf statischer Analyse der Schema-Pfad-Literale in den bekannten Validator-Modulen.
Jede der sechs `instance_validation_direct`-Beziehungen wurde manuell gegen den Quellcode verifiziert.

Die Ergebnisse wurden durch das Skript `/tmp/lenskit-validates-schema-audit.py` erzeugt,
das Assertions für Sortierung, Klassifikationsgültigkeit und Schemainventarzugehörigkeit enthält.
Die Ausgabe liegt unter `/tmp/lenskit-validates-schema-audit.json`.
