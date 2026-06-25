# Guard Relation Cards v1b (Target Proof — `validates_schema`)

## 1. Status und Scope

Dieser Target-Proof ist **diagnosis-only**. Er enthält **keinen Produktionscode**,
**keinen Guard-Relation-Contract**, **kein neues Schema**, **keinen Producer**,
**keinen Runtime-Validator**, **keine CLI- und keine Bundle-Integration**.

Untersucht wird ausschließlich der Roadmap-Kandidat `validates_schema`. Andere
Guard-Relation-Kandidaten (`tests_by_path`, `checks_surface`, `checks_cli`,
`checks_security`) werden **nicht** bewertet.

Ziel dieser Runde ist nicht primär das Zählen, sondern die Festlegung einer
**minimalen, stabilen, reproduzierbaren Identität** für eine Schema-Validierungs-
beziehung, sodass zwei unabhängige Auswertungen dieselben Beziehungen, Ausschlüsse
und Bedingungen ergeben.

## 2. Festgeschriebene Base-SHA

`05bbd0d608afa8faf581887a455d4dcf6fa15ae9` ist die **festgeschriebene Base-SHA**
dieses Target-Proofs und zugleich der **Merge-Commit von PR #798** (Parents
`58b8453b` + `fea5a71a`). Alle Messwerte beziehen sich ausschließlich auf diesen
Git-Baum. Es wird **keine** zeitabhängige Aussage über die jeweils aktuelle
`origin/main`-Spitze getroffen.

- **Inventar**: `git ls-tree -r --name-only 05bbd0d6` → **590 Pfade**,
  SHA-256 `19ccdd599e32d683b97d71a86b05594b825440bda1b900d32a756517f637b50a`.
- **`*.schema.json` im Base-Tree**: **54**.

## 3. Reproduktionsartefakte und Rollen

| Artefakt | Rolle |
|---|---|
| `docs/proofs/_repro/guard_relation_validates_schema_audit.py` | Versioniertes, deterministisches Diagnoseinstrument (stdlib + `infer_facets` aus dem Base-Snapshot). Liest Dateiinhalte via `git show <base>:<path>`, niemals den Working Tree. |
| `docs/proofs/guard-relation-cards-v1b-validates-schema-audit.json` | Aus dem Skript erzeugter, byteidentisch reproduzierbarer Audit-Output. |

Beides ist **Diagnosecode/-daten**, kein Produktionscode. Aufruf:

```bash
python3 docs/proofs/_repro/guard_relation_validates_schema_audit.py \
  --repo "$REPO" --base-sha 05bbd0d608afa8faf581887a455d4dcf6fa15ae9 \
  --output /tmp/validates-schema-audit-a.json
```

Zwei aufeinanderfolgende Läufe sind **byteidentisch** (keine Zeitstempel, keine
absoluten Pfade, deterministische Sortierung).

## 4. Ausgangszustand

- **Relation Card v1** erlaubt ausschließlich den `relation`-Wert **`imports`**
  (`relation-card.v1.schema.json`, `"const": "imports"`). Sie ist imports-only.
- Der Producer `merger/lenskit/core/relation_cards.py` projiziert vorhandene
  Importkanten aus `architecture.graph.v1`; keine Relationserkennung.
- `validates_schema` ist **kein** unterstützter Relationstyp; es existiert **kein**
  Guard-Relation-Producer. Diese Grenze wird hier nicht verändert.

## 5. Nachweis der Nichtimplementierung

- Repo-weite Suche nach `validates_schema|validates-schema|validates_against_schema|guard_relation`
  in Nicht-Doc-Code liefert keine Symbol-, Contract- oder Producer-Treffer.
- `relation-card.v1.schema.json` benennt im `relation`-Description die weiteren
  Kandidaten (`mentions`, `validates`, `tests`, …) ausdrücklich als **zurückgestellt**.
- Kein Contract, Producer, Runtime-Validator, Test oder Goldset realisiert eine
  Schema-Validierungsrelation. Vorkommen von `.schema.json` oder `jsonschema` sind
  keine Guard-Relation-Implementierung.

## 6. Roadmap-Name versus untersuchte Semantik

```
Roadmap-Kandidat:           validates_schema
untersuchte Semantik:       validates_instance_against_schema
empfohlener späterer Name:  validates_against_schema
```

`validates_schema` ist mehrdeutig: es könnte „validiert das Schema selbst“
(Meta-Validierung) oder „validiert Daten gegen das Schema“ (Instanzvalidierung)
meinen. Alle akzeptierten Beziehungen sind **Instanzvalidierung**. Der bestehende
Roadmap-Identifier wird in diesem PR **nicht** umbenannt; es wird keine Alias- oder
Migrationsentscheidung getroffen.

## 7. Definition der Relationsidentität

Eine akzeptierte Instanzvalidierungsbeziehung ist ein **Callsite-Flow**, eindeutig
identifiziert durch:

```
relation_flow_id =
  source_path + relation_owner_symbol + engine_owner_symbol + engine_call_line
  + schema_path + schema_fragment + activation_condition + target_scope
```

- **source_path** – repo-relativer Modulpfad.
- **relation_owner_symbol** – Symbol, das fachlich Instanz und Schema zusammenführt.
- **engine_owner_symbol** – Symbol, in dem die JSON-Schema-Engine aufgerufen wird.
- **engine_call_line** – Zeile der Engine-Callsite im Base-Snapshot.
- **schema_path** – repo-relativer oder externer relativer Schemapfad.
- **schema_fragment** – JSON-Pointer/Subschema (z. B. `#/properties/merge`) oder `null`.
- **activation_condition** – Bedingung, unter der genau dieser Flow aktiv wird.
- **target_scope** – `in_repo` | `external_static_relative` | `unresolved_dynamic`.

## 8. Granularitäten und Zähloberflächen

Mehrere Zahlen werden **getrennt** geführt (kein Vermischen). Alle werden im Audit
aus der normierten Relationstabelle berechnet, nicht hart codiert:

| Zähloberfläche | Wert |
|---|---|
| Callsite-Flow-Beziehungen | **24** |
| eindeutige Symbol→Schema-Ziele | **23** |
| eindeutige Modul→Schema-Ziele | **21** |
| akzeptierte Module (in_repo) | **17** |
| akzeptierte Schema-Ziele (in_repo) | **18** |
| externe/nicht akzeptierte Flows | **1** |

Mehrere Callsite-Flows können auf dasselbe Symbol- oder Modul-Schema-Paar fallen.
Beispiel: `federation.add_bundle` validiert dasselbe Schema an **zwei** Engine-
Callsites (156 und 187) → 2 Callsite-Flows, aber **1** Symbol→Schema-Ziel. Daher
`24 → 23` Symbol-Schema (einzig dieser Kollaps) und `24 → 21` Modul-Schema
(zusätzlich kollabieren `init_federation`/`validate_federation`/`add_bundle` auf
`federation → federation-index.v1`).

## 9. Kandidatenermittlung

- **AST-Sweep** über alle Python-Dateien des Base-Snapshots: Aufrufe der Instanz-APIs
  `.validate(...)` / `.iter_errors(...)` (sowie `.check_schema(...)` separat).
- **Provenienz-Gate**: nur Dateien, die den Token `jsonschema` enthalten.
- **Textsweep**: Produktionsdateien mit `jsonschema`-Token.
- **Mengenabgleich** (siehe §10): AST-Produktionsdateien = manuell akzeptierte
  Produktionsdateien; jede Differenz Text↔AST ist explizit erklärt.

Die Mengen­gleichheit ist nur ein **Vollständigkeitsgate für Kandidaten**, kein
Nachweis korrekter Schemaflüsse. Letztere sind manuell verifiziert (§11).

## 10. Import- und Engine-Provenienz; Candidate-Sweep

- AST-entdeckte Produktions-Validierungsdateien: **17 akzeptiert + 1 extern = 18**.
- Diese Menge ist **identisch** mit den manuell akzeptierten/ausgeschlossenen
  Produktionsdateien (Audit-Assertion).
- Textsweep − AST = exakt **5** erklärte Nicht-Validator-Dateien mit `jsonschema`-Token:
  `dependency_diagnostics.py` (Status-Reporter), `output_health.py` (nutzt nur den
  Reporter), `bundle_surface_validate.py` (eigener Strukturvalidator; `jsonschema`
  nur in einem `Literal`), `tests/conftest.py` (`no_jsonschema`-Fixture), und
  `scripts/docmeta/check_planning_registration.py` (verweist auf Tests).

Aufgelöste Engines: `jsonschema.validate` (15), `Draft7Validator.iter_errors` (6),
`Draft202012Validator.iter_errors` (3).

## 11. Akzeptanzregel

Direkt/delegiert nur, wenn: Source-Modul + Symbol bekannt; Schemapfad statisch
eindeutig; Schema im Base-Inventar (`target_scope == in_repo`); Instanz + Schema
erreichen eine konkrete `validate`-API; Aufrufkette vollständig; Aktivierungs- und
Degradationsbedingung dokumentiert; nicht allein auf Namens-, Test-, Import- oder
Konstanten-Ähnlichkeit gestützt. Jede der 24 akzeptierten Beziehungen wurde manuell
gegen den Quellcode des Base-Snapshots geprüft.

## 12. Akzeptierte Callsite-Flow-Tabelle (24)

| # | source (`merger/lenskit/…`) | relation_owner | engine_owner | line | schema (`contracts/…`) | fragment | activation | inv. |
|---|---|---|---|---|---|---|---|---|
| 1 | `architecture/graph_index.py` | `load_graph_index` | = | 39 | `architecture.graph_index.v1` | – | unconditional | direct |
| 2 | `cli/policy_loader.py` | `load_and_validate_embedding_policy` | = | 45 | `embedding-policy.v1` | – | unconditional | direct |
| 3 | `cli/pr_schau_verify.py` | `verify_basic` | = | 80 | `pr-schau.v1` | – | unconditional | direct |
| 4 | `core/agent_export_gate.py` | `_validate_post_health_schema` | = | 262 | `post-emit-health.v1` | – | unconditional | direct |
| 5 | `core/doc_freshness.py` | `validate_registry` | = | 668 | `doc-freshness-registry.v1` | – | unconditional | direct |
| 6 | `core/federation.py` | `init_federation` | = | 59 | `federation-index.v1` | – | unconditional | direct |
| 7 | `core/federation.py` | `validate_federation` | = | 87 | `federation-index.v1` | – | unconditional | direct |
| 8 | `core/federation.py` | `add_bundle` | = | 156 | `federation-index.v1` | – | unconditional | direct |
| 9 | `core/federation.py` | `add_bundle` | = | 187 | `federation-index.v1` | – | unconditional | direct |
| 10 | `core/forensic_preflight.py` | `_validate_claim_map_schema` | = | 119 | `claim-evidence-map.v1` | – | unconditional | direct |
| 11 | `core/lens_card_validate.py` | `validate_lens_card` | = | 136 | `lens-card.v1` | – | unconditional | direct |
| 12 | `core/parity_state.py` | `_validate_citation_map` | = | 349 | `citation-map.v1` | – | unconditional | direct |
| 13 | `core/post_emit_health.py` | `_validate_claim_evidence_map_schema` | = | 331 | `claim-evidence-map.v1` | – | unconditional | direct |
| 14 | `core/post_emit_health.py` | `_validate_manifest_schema` | = | 404 | `bundle-manifest.v1` | – | unconditional | direct |
| 15 | `core/pr_delta_card_validate.py` | `validate_pr_delta_card` | = | 135 | `pr-delta-card.v1` | – | unconditional | direct |
| 16 | `core/pr_delta_cards.py` | `_validate_source_delta` | = | 105 | `pr-schau-delta.v1` | – | unconditional | direct |
| 17 | `core/pr_schau_bundle.py` | `load_pr_schau_bundle` | = | 130 | `pr-schau.v1` | – | unconditional | direct |
| 18 | `core/range_resolver.py` | `resolve_range_ref` | = | 193 | `range-ref.v1` | – | `range_ref_version != "2"` | direct |
| 19 | `core/range_resolver.py` | `resolve_range_ref` | = | 193 | `range-ref.v2` | – | `range_ref_version == "2"` | direct |
| 20 | `core/relation_cards.py` | `_validate_source_graph` | = | 137 | `architecture.graph.v1` | – | unconditional | direct |
| 21 | `core/relation_card_validate.py` | `validate_relation_card` | `_schema_check` | 226 | `relation-card.v1` | – | unconditional | **delegated** |
| 22 | `core/relation_card_validate.py` | `validate_relation_card` | `_schema_check` | 235 | `architecture.graph.v1` | – | unconditional | **delegated** |
| 23 | `validate_merge_meta.py` | `validate_report_meta` | = | 95 | `repolens-report` | `#/properties/merge` | unconditional | direct |
| 24 | `validate_merge_meta.py` | `validate_report_meta` | = | 114 | `repolens-delta` | – | unconditional | direct |

`=` bedeutet `engine_owner_symbol == relation_owner_symbol`. Vollständige Felder
(Provenienz, Drafts, Dependency- und Schemaachsen, Evidenz-Zeilen) im Audit-JSON.

## 13. Eindeutige Symbol- und Modul-Schema-Aggregate

- **Symbol→Schema-Ziele: 23.** Einziger Kollaps: `federation.add_bundle` →
  `federation-index.v1` an zwei Callsites (156, 187).
- **Modul→Schema-Ziele: 21.** Zusätzlicher Kollaps: `federation` validiert
  `federation-index.v1` aus drei Symbolen (`init_federation`, `validate_federation`,
  `add_bundle`).

## 14. Engine-Aufrufachse (direkt/delegiert)

`engine_invocation = direct` gdw. `relation_owner_symbol == engine_owner_symbol`.

| Wert | Anzahl |
|---|---|
| direct | 22 |
| delegated | 2 |

Delegiert sind nur `validate_relation_card` (#21, #22): die Funktion lädt Card- und
Source-Schema und übergibt Instanz + Schema an den modulinternen Helper
`_schema_check` (Engine-Callsite `iter_errors` Zeile 159).

## 15. Schema-Bindungsachse

`schema_binding_origin` ist orthogonal zur Engine-Achse:

| Wert | Anzahl | Beispiel |
|---|---|---|
| `same_symbol_literal` | 9 | `_validate_post_health_schema` (Literal in der Funktion) |
| `same_module_loader` | 11 | `validate_relation_card` (über `_load_default_*_schema`) |
| `same_module_constant` | 2 | `resolve_range_ref` (Modulkonstanten v1/v2) |
| `caller_parameter` | 2 | `verify_basic`, `validate_registry` (Schema/Pfad als Parameter) |

So ist z. B. `verify_basic` `engine_invocation=direct` **und**
`schema_binding_origin=caller_parameter`; `validate_relation_card` ist
`delegated` + `same_module_loader`. Die zwei Achsen werden nicht vermischt.

## 16. Schemafragmente

Nur ein Flow validiert gegen ein **Subschema** statt der vollständigen Datei:
`validate_merge_meta.validate_report_meta` (#23) gegen
`repolens-report.schema.json` Fragment `#/properties/merge`. Der zugehörige
Delta-Flow (#24) validiert `repolens-delta.schema.json` vollständig (`fragment=null`).

## 17. Aktivierungsbedingungen

Genau ein Callsite (`range_resolver.resolve_range_ref`, Zeile 193) wählt zur Laufzeit
über `is_v2` eines von zwei Schemata. Modelliert als zwei Flows mit disjunkten
Bedingungen (`range_ref_version != "2"` / `== "2"`). Es wird **nicht** behauptet,
beide Schemata würden gleichzeitig auf dieselbe Instanz angewandt. Alle übrigen 22
Flows sind `unconditional`.

## 18. Externe bzw. nicht akzeptierte Flows (1)

| source | relation_owner | engine_owner | line | schema_path | target_scope |
|---|---|---|---|---|---|
| `adapters/sources.py` | `refresh` | `_validate_snapshot` | 178 | `metarepo/contracts/fleet/fleet.snapshot.schema.json` | `external_static_relative` |

`refresh()` validiert **ausschließlich** den Fleet-Snapshot
(`_validate_snapshot(fleet_snapshot, fleet_schema_path)`, Zeile 299) gegen ein
externes Metarepo-Schema. Der Schemapfad-Suffix ist statisch, die Wurzel stammt aus
dem Laufzeit-`hub_path`; das Schema liegt **nicht** im Base-Inventar (Akzeptanzregeln
2/3 verletzt). Der Organism-Snapshot (Zeilen 310–324) wird **gebaut und geschrieben,
aber nicht validiert** — er ist daher **keine** zweite externe Validierungsbeziehung.

## 19. Meta-Engine-Callsites (5)

`Draft*Validator.check_schema(...)` ist eine echte Meta-Validierung und wird nicht auf
null gesetzt. Fünf Produktions-Callsites:

| source | engine_owner | line |
|---|---|---|
| `core/lens_card_validate.py` | `validate_lens_card` | 134 |
| `core/pr_delta_card_validate.py` | `validate_pr_delta_card` | 133 |
| `core/pr_delta_cards.py` | `_validate_source_delta` | 99 |
| `core/relation_cards.py` | `_validate_source_graph` | 135 |
| `core/relation_card_validate.py` | `_schema_check` | 157 |

## 20. Meta-Schema-Flows (6)

Die 5 Callsites prüfen **6** schemaspezifische Meta-Flows, weil `_schema_check`
(Zeile 157) über **dieselbe** Callsite **zwei** verschiedene Schemata prüft
(`relation-card.v1`, `architecture.graph.v1`). Die Meta-Flows werden **nicht** zu den
24 Instanzvalidierungsbeziehungen addiert; betroffene Relationen tragen
`meta_guard_present = true` (6 Flows: #11, #15, #16, #20, #21, #22). Jede
Meta-Validierung steht unmittelbar als Guard **vor** der Instanzvalidierung derselben
Kette.

## 21. Testinventar

Testklassifikation über die bestehende Facet-API
(`merger.lenskit.core.lens_facets.infer_facets`, Facet `test`); `lens_facets.py` und
`lenses.py` sind zwischen Base und Head unverändert. Fixture-Ausschlüsse (Segment
`fixtures`) werden dadurch korrekt übernommen.

Befund: **44 Testdateien mit mindestens einem erkannten JSON-Schema-Validierungs-API-
Aufruf.** Dies sind **keine** `test_only`-Schema-Relationen; Inline-Schemata und
nicht repo-interne Schemata sind keine Relation zu einer `*.schema.json` des
Base-Inventars. `conftest.py` ist nach der Facet-API **kein** Testmodul.

## 22. Parsefehler

Vollständiger AST-Parsefehler-Befund im Base-Snapshot: **genau eine** Datei.

| path | lineno | message | Facet |
|---|---|---|---|
| `merger/lenskit/tests/fixtures/entrypoints_test_project/invalid.py` | 1 | `'(' was never closed` | (kein test-Facet; `fixtures`-Segment) |

Das Audit assertiert exakt diese Menge; keine anonyme Skip-Zahl.

## 23. Schema-Abdeckung

| Metrik | Wert |
|---|---|
| `*.schema.json` gesamt | 54 |
| mit akzeptierter Produktionsbeziehung | 18 |
| ohne akzeptierte Produktionsbeziehung | 36 |

Assertion: `18 + 36 = 54`. Die 36 heißen **„Schema-Dateien ohne akzeptierte
Produktions-Instanzvalidierungsbeziehung“** — **nicht** `load_only`. Mögliche Gründe
sind verschieden: nur in Tests validiert; nur produziert; nur referenziert; nur
dokumentiert; gar nicht produktiv verwendet; oder über nicht untersuchte dynamische
Pfade verwendet.

## 24. Dependency-Anforderungen

| `dependency_requirement` | Anzahl |
|---|---|
| `optional_module_import` (Modul-Top `try/except`) | 15 |
| `dynamic_runtime_import` (Import zur Laufzeit, z. B. `importlib.import_module`) | 7 |
| `required_at_module_import` (harter Top-Level-Import) | 2 |

Ein harter Top-Level-Import (`validate_merge_meta.py`:
`from jsonschema import Draft202012Validator`) wird als **`required_at_module_import`**
geführt — nicht als unbedingte Laufzeit-Verfügbarkeit.

## 25. Missing-Dependency-Verhalten

Beobachtetes Verhalten bei fehlendem `jsonschema` (gegenseitig eindeutig, Summe 24):

| `missing_dependency_outcome` | Anzahl |
|---|---|
| `raises_runtime_error` | 6 |
| `returns_failed_check_skipped_unavailable` | 4 |
| `raises_domain_error` | 4 |
| `module_import_failure` | 2 |
| `returns_environment_error` | 2 |
| `warn_and_continue` | 2 |
| `silent_skip` | 2 |
| `returns_blocked` | 1 |
| `structural_fallback` | 1 |

Unterschiedliche Zustände werden **nicht** unter „skipped_unavailable“ zusammengefasst.
`doc_freshness.validate_registry` etwa fällt auf einen dependency-freien
Strukturvalidator zurück (`structural_fallback`) — ein eigener Ausführungsmodus.

## 26. Schema-Anforderungen

| `schema_requirement` | Anzahl |
|---|---|
| `required` | 22 |
| `optional` | 2 |

`optional`: `graph_index.load_graph_index` und `pr_schau_bundle.load_pr_schau_bundle`
überspringen die Validierung, wenn die Schema-Datei fehlt.

## 27. Missing-Schema-Verhalten

| `missing_schema_outcome` | Anzahl |
|---|---|
| `raises_runtime_error` | 11 |
| `returns_blocked` | 6 |
| `raises_domain_error` | 2 |
| `returns_environment_error` | 2 |
| `silent_skip` | 2 |
| `warn_and_continue` | 1 |

Beispiel `warn_and_continue`: der optionale Delta-Block in
`validate_merge_meta.validate_report_meta` (#24) warnt und überspringt bei fehlendem
Delta-Schema.

## 28. Validator-Drafts und Formatprüfung

| `validator_draft` | n | | `format_checker_mode` | n |
|---|---|---|---|---|
| `auto-selected` (`jsonschema.validate`) | 15 | | `none` | 22 |
| `draft7` | 6 | | `FormatChecker` | 1 |
| `draft2020-12` | 3 | | `custom_date_time_checker` | 1 |

`FormatChecker`: `pr_delta_card_validate`. `custom_date_time_checker`:
`pr_delta_cards` (verlangt `date-time`-Formatprüfung). Diese Felder sind
Annotationen und nicht Teil der Relationsidentität.

## 29. Mehrfachschema- und Mehrfachvalidator-Fälle

- **Modul → mehrere Schemata:** `relation_card_validate` (relation-card.v1 +
  architecture.graph.v1), `post_emit_health` (claim-evidence-map.v1 +
  bundle-manifest.v1), `validate_merge_meta` (repolens-report + repolens-delta),
  `range_resolver` (range-ref.v1/v2 an einer bedingten Callsite).
- **Schema ← mehrere Module:** `claim-evidence-map.v1` (`post_emit_health` +
  `forensic_preflight`), `architecture.graph.v1` (`relation_cards`-Producer +
  `relation_card_validate`), `pr-schau.v1` (`pr_schau_verify` + `pr_schau_bundle`),
  `federation-index.v1` (`federation` an 4 Callsites).

## 30. Consumeranalyse

| Stufe | Befund |
|---|---|
| implementierter Consumer | keiner |
| verbindlich spezifizierter Consumer | keiner |
| möglicher zukünftiger Consumer | Contract-Review-Navigation, Impact-/Change-Abschätzung, relation-aware Retrieval (unspezifiziert) |
| nur plausible Idee | „Welche Validatoren liest man bei einem Contract-Review?“ |

Durchsucht: Blueprint, `lens-model.md`, `docs/retrieval/**`, `docs/roadmap/**`,
`merger/lenskit/retrieval/**`, `core/pr_delta_cards.py`, `cli/pr_explain.py`.
**Kein verbindlicher Consumer; kein Persistenzbedarf belegt.**

## 31. Bevorzugte Darstellungsrichtung

`Validator → Schema` ist die **bevorzugte Darstellungsrichtung dieses Target-Proofs**
(„validates data against schema“). Dies ist **keine** festgelegte Contractrichtung —
ohne Consumer ist keine persistierte Richtung entschieden. Keine bidirektionale
Persistenz wird empfohlen.

## 32. Persistenzoptionen

- **A — persistierter Contract begründbar:** erfordert reproduzierbare Beziehungen
  **und** eindeutige Semantik **und** verbindlichen Consumer **und** belegten
  Persistenzvorteil. → nicht erfüllt (Consumer fehlt, Name ungeklärt).
- **B — On-Demand-Auflösung genügt:** Beziehungen sind reproduzierbar und statisch
  gebunden; eine On-Demand-Diagnose ist möglich, aber ohne aktuellen Bedarf.
- **C — zurückstellen.**

## 33. Entscheidung

**Ergebnis C — zurückstellen.** Das Gate für einen persistierten Contract ist
geschlossen. Begründung (ein positiver Relationsproducer könnte ausschließlich
vorhandene Beziehungen emittieren — die Abdeckung 18/54 ist daher **kein**
Persistenzblocker, sondern nur ein Coverage-Befund):

- kein implementierter oder verbindlich spezifizierter Consumer;
- Relationsidentität noch nicht contractuell festgelegt;
- Namensambiguität (`validates_schema` vs. `validates_against_schema`);
- kein belegter Persistenzvorteil gegenüber On-Demand-Auflösung;
- keine contractuelle Richtung;
- externe bzw. bedingte Zielpfade (sources.py extern; range_resolver bedingt).

Diese Entscheidung führt in diesem PR **zu keiner** Produktionsimplementierung.

## 34. Offene epistemische Leerstellen

- Keine verbindliche Consumerfrage, die Richtung, Persistenzbedarf und
  Qualitätsanforderung festlegt.
- Nur Validierung gegen `*.schema.json` erfasst; interne Datenstrukturen und externe
  Schemata nicht als In-Repo-Relation modelliert.
- `load_only`- und `path_reference_only`-Callsites wurden **nicht** vollständig
  inventarisiert (siehe §35).
- Dynamisch/konfigurationsgeladene Schemata und Nicht-`jsonschema`-Validatoren sind
  außerhalb des Scopes.
- Laufzeitausführung ist nicht bewiesen.

## 35. Negativsemantik

Es wird **nicht** behauptet, dass keine Load-only- oder Reference-only-Callsites
existieren oder dass deren Anzahl null sei: Load-only-Callsites wurden in diesem
Target-Proof nicht vollständig inventarisiert; Reference-only-Callsites wurden in
diesem Target-Proof nicht vollständig inventarisiert.

Eine Schema-Validierungsrelation beweist **nicht**: `schema_correctness`,
`validator_completeness`, `runtime_execution`, `runtime_correctness`,
`test_sufficiency`, `regression_absence`, `change_impact`, `consumer_need`,
`repo_understood`, `forensic_ready`.

Ein erfolgreicher statischer Nachweis bedeutet nur:

> Im untersuchten Snapshot existiert eine statisch nachvollziehbare Codekette zwischen
> einer Validierungsstelle und einem bestimmten Schema.

## 36. Implementierungsgates

Für einen etwaigen späteren persistierten `validates_against_schema`-Contract müssen
mindestens bestehen: (1) Namensklärung; (2) Consumer-Nachweis; (3) Richtung;
(4) Source-Kohärenz aller 17 Module / 24 Flows; (5) Modellierung der Dependency- und
Schema-Achsen inkl. Degradationspfade; (6) Trennung Instanz- vs. Meta-Validierung;
(7) Behandlung der 36 Schemata ohne akzeptierte Beziehung; (8) Behandlung externer
(`sources.py`) und bedingter (`range_resolver`) Flows; (9) manuelle Review jeder
Beziehung; (10) Goldset vor Persistenz. Dieser Proof öffnet **keines** dieser Gates.

## 37. Reproduktion und Assertions

```bash
git ls-tree -r --name-only 05bbd0d608afa8faf581887a455d4dcf6fa15ae9 \
  | LC_ALL=C sort -u > /tmp/inv.txt
sha256sum /tmp/inv.txt   # 19ccdd59…

python3 docs/proofs/_repro/guard_relation_validates_schema_audit.py \
  --repo "$REPO" --base-sha 05bbd0d608afa8faf581887a455d4dcf6fa15ae9 \
  --output /tmp/a.json
python3 docs/proofs/_repro/guard_relation_validates_schema_audit.py \
  --repo "$REPO" --base-sha 05bbd0d608afa8faf581887a455d4dcf6fa15ae9 \
  --output /tmp/b.json
cmp /tmp/a.json /tmp/b.json                                           # byteidentisch
cmp /tmp/a.json docs/proofs/guard-relation-cards-v1b-validates-schema-audit.json
```

Das Skript erzwingt u. a.: Base-SHA und Inventarhash; Sortierung und Eindeutigkeit
der `relation_flow_id`; `target_scope == in_repo` und `schema_path ∈ inventory` für
alle akzeptierten Flows; gültige Fragmente (`null` oder `#/…`); je Achse Summe 24;
`accepted_modules`/`accepted_schema_targets` aus der Tabelle berechnet;
`with + without == 54`; `meta_engine_callsites == 5`; `meta_schema_flows == 6`;
Testdateien tragen das `test`-Facet; Parsefehlermenge `== {…/invalid.py}`. Bei jeder
Abweichung oder jedem ungeklärten Kandidaten beendet sich das Skript mit Fehlerstatus.
