# Guard Relation Cards v1b (Target Proof — `validates_schema`)

## 1. Status und Scope

Dieser Target-Proof ist **diagnosis-only**. Er enthält **keinen Produktionscode**,
**keinen Guard-Relation-Contract**, **kein neues Schema**, **keinen Producer**,
**keinen Runtime-Validator**, **keine CLI- und keine Bundle-Integration**.

Untersucht wird ausschließlich der Roadmap-Kandidat `validates_schema`. Andere
Guard-Relation-Kandidaten (`tests_by_path`, `checks_surface`, `checks_cli`,
`checks_security`) werden nicht bewertet.

## 2. Festgeschriebene Base

Alle Messwerte beziehen sich ausschließlich auf den Git-Baum:

`05bbd0d608afa8faf581887a455d4dcf6fa15ae9`

Das ist der Merge-Commit von PR #798. Das Inventar umfasst **590 Pfade** mit
SHA-256 `19ccdd599e32d683b97d71a86b05594b825440bda1b900d32a756517f637b50a` und enthält **54** Dateien mit Suffix `*.schema.json`.

## 3. Reproduktionsartefakte

| Artefakt | Rolle |
|---|---|
| `docs/proofs/_repro/guard_relation_validates_schema_audit.py` | Versioniertes Diagnoseinstrument. Liest ausschließlich den festgeschriebenen Base-Baum über `git show` und `git ls-tree`. |
| `docs/proofs/guard-relation-cards-v1b-validates-schema-audit.json` | Deterministischer Audit-Output des Instruments. |

Zwei Ausführungen **desselben versionierten Audits** sind byteidentisch. Das ist
Reproduzierbarkeit desselben Messverfahrens, keine Behauptung zweier unabhängiger
Messmethoden.

## 4. Nachweis der Nichtimplementierung

Relation Card v1 bleibt `imports`-only. Es existiert kein unterstützter
`validates_schema`-Relationstyp, kein entsprechender Contract, Producer,
Runtime-Validator, Consumer oder Goldset. Vorkommen von `jsonschema` oder
`.schema.json` sind keine Guard-Relation-Implementierung.

## 5. Untersuchte Semantik

```text
Roadmap-Kandidat:           validates_schema
untersuchte Semantik:       validates_instance_against_schema
möglicher späterer Name:    validates_against_schema
```

Der Roadmap-Name bleibt in diesem PR unverändert. Meta-Validierung eines Schemas
und Instanzvalidierung gegen ein Schema werden getrennt geführt.

## 6. Relationsidentität

Eine akzeptierte Instanzvalidierungsbeziehung wird als Callsite-Flow modelliert:

```text
relation_flow_id =
  source_path
  + relation_owner_symbol
  + relation_call_line
  + engine_owner_symbol
  + engine_call_line
  + schema_path
  + schema_fragment
  + activation_condition
  + target_scope
```

- `relation_owner_symbol`: Symbol, das fachlich Instanz und Schema zusammenführt.
- `relation_call_line`: Stelle, an der dieser Symbolpfad die Engine direkt oder
  einen delegierten Engine-Helper aufruft.
- `engine_owner_symbol`: Symbol, in dem die eigentliche JSON-Schema-Engine läuft.
- `engine_call_line`: Zeile von `.validate(...)` oder `.iter_errors(...)`.
- `schema_path`: statisch aufgelöster Schema-Zielpfad.
- `schema_fragment`: Subschema-Pointer oder `null`.
- `activation_condition`: Bedingung für genau diesen Flow.
- `target_scope`: `in_repo`, `external_static_relative` oder
  `unresolved_dynamic`.

Bei direkten Flows sind Relation- und Engine-Owner sowie beide Zeilen gleich.
Bei delegierten Flows bleiben Relation- und Engine-Callsite getrennt.

## 7. Zähloberflächen

| Oberfläche | Wert |
|---|---:|
| akzeptierte Callsite-Flows | 24 |
| eindeutige Instanz-Engine-Callsites, inklusive externem Flow | 23 |
| eindeutige Symbol→Schema-Ziele | 23 |
| eindeutige Modul→Schema-Ziele | 21 |
| akzeptierte In-Repo-Module | 17 |
| akzeptierte In-Repo-Schema-Ziele | 18 |
| externe/nicht akzeptierte Flows | 1 |

Die 24 Relationsflows sind nicht mit 24 verschiedenen Engine-Callsites
gleichzusetzen:

- `range_resolver` modelliert an einer Engine-Callsite zwei disjunkte Schema-Flows.
- `relation_card_validate._schema_check` ist eine Engine-Callsite für zwei
  delegierte Relationsflows.
- der externe `sources.py`-Flow ergänzt eine weitere Engine-Callsite.

## 8. Callsite-Vollständigkeitsgate

Das Audit scannt den Base-Baum per AST und erhebt für jede
Instanzvalidierungs-Callsite das Tripel:

```text
(source_path, engine_owner_symbol, engine_call_line)
```

Für Nicht-Test-Facet-Dateien wird die entdeckte Menge exakt mit der manuell
reviewten Menge verglichen. Das Audit schlägt fehl, wenn eine Callsite nur auf
einer Seite vorkommt.

Zusätzlich wird für jeden Flow geprüft:

1. Die deklarierte Engine-Zeile enthält wirklich `.validate(...)` oder
   `.iter_errors(...)`.
2. Die Engine-Zeile liegt im deklarierten `engine_owner_symbol`.
3. Die Relation-Zeile liegt im deklarierten `relation_owner_symbol`.
4. Bei delegierten Flows ruft die Relation-Zeile tatsächlich den angegebenen
   Engine-Helper auf.

Dieses Gate ist stärker als ein reiner Dateimengenvergleich. Es beweist dennoch
nicht die semantische Richtigkeit der manuell zugeordneten Schema-Bindung.

## 9. Klassifikationsgrenze

Die bestehende Facet-API klassifiziert das kontrollierte Facet `test`.
`non_test_facet` bedeutet daher ausschließlich:

> Das kontrollierte Test-Facet wurde nicht vergeben.

Es bedeutet **nicht automatisch Produktionscode**. Insbesondere ist
`merger/lenskit/tests/conftest.py` Testinfrastruktur, obwohl es nach der engen
Facet-Regel kein `test`-Facet erhält.

## 10. Akzeptierte Callsite-Flows

| # | source | relation owner | relation line | engine owner | engine line | schema | fragment | activation | invocation |
|---:|---|---|---:|---|---:|---|---|---|---|
| 1 | `architecture/graph_index.py` | `load_graph_index` | 39 | `load_graph_index` | 39 | `architecture.graph_index.v1` | – | `unconditional` | direct |
| 2 | `cli/policy_loader.py` | `load_and_validate_embedding_policy` | 45 | `load_and_validate_embedding_policy` | 45 | `embedding-policy.v1` | – | `unconditional` | direct |
| 3 | `cli/pr_schau_verify.py` | `verify_basic` | 80 | `verify_basic` | 80 | `pr-schau.v1` | – | `unconditional` | direct |
| 4 | `core/agent_export_gate.py` | `_validate_post_health_schema` | 262 | `_validate_post_health_schema` | 262 | `post-emit-health.v1` | – | `unconditional` | direct |
| 5 | `core/doc_freshness.py` | `validate_registry` | 668 | `validate_registry` | 668 | `doc-freshness-registry.v1` | – | `unconditional` | direct |
| 6 | `core/federation.py` | `init_federation` | 59 | `init_federation` | 59 | `federation-index.v1` | – | `unconditional` | direct |
| 7 | `core/federation.py` | `validate_federation` | 87 | `validate_federation` | 87 | `federation-index.v1` | – | `unconditional` | direct |
| 8 | `core/federation.py` | `add_bundle` | 156 | `add_bundle` | 156 | `federation-index.v1` | – | `unconditional` | direct |
| 9 | `core/federation.py` | `add_bundle` | 187 | `add_bundle` | 187 | `federation-index.v1` | – | `unconditional` | direct |
| 10 | `core/forensic_preflight.py` | `_validate_claim_map_schema` | 119 | `_validate_claim_map_schema` | 119 | `claim-evidence-map.v1` | – | `unconditional` | direct |
| 11 | `core/lens_card_validate.py` | `validate_lens_card` | 136 | `validate_lens_card` | 136 | `lens-card.v1` | – | `unconditional` | direct |
| 12 | `core/parity_state.py` | `_validate_citation_map` | 349 | `_validate_citation_map` | 349 | `citation-map.v1` | – | `unconditional` | direct |
| 13 | `core/post_emit_health.py` | `_validate_claim_evidence_map_schema` | 331 | `_validate_claim_evidence_map_schema` | 331 | `claim-evidence-map.v1` | – | `unconditional` | direct |
| 14 | `core/post_emit_health.py` | `_validate_manifest_schema` | 404 | `_validate_manifest_schema` | 404 | `bundle-manifest.v1` | – | `unconditional` | direct |
| 15 | `core/pr_delta_card_validate.py` | `validate_pr_delta_card` | 135 | `validate_pr_delta_card` | 135 | `pr-delta-card.v1` | – | `unconditional` | direct |
| 16 | `core/pr_delta_cards.py` | `_validate_source_delta` | 105 | `_validate_source_delta` | 105 | `pr-schau-delta.v1` | – | `unconditional` | direct |
| 17 | `core/pr_schau_bundle.py` | `load_pr_schau_bundle` | 130 | `load_pr_schau_bundle` | 130 | `pr-schau.v1` | – | `unconditional` | direct |
| 18 | `core/range_resolver.py` | `resolve_range_ref` | 193 | `resolve_range_ref` | 193 | `range-ref.v1` | – | `range_ref_version != "2"` | direct |
| 19 | `core/range_resolver.py` | `resolve_range_ref` | 193 | `resolve_range_ref` | 193 | `range-ref.v2` | – | `range_ref_version == "2"` | direct |
| 20 | `core/relation_cards.py` | `_validate_source_graph` | 137 | `_validate_source_graph` | 137 | `architecture.graph.v1` | – | `unconditional` | direct |
| 21 | `validate_merge_meta.py` | `validate_report_meta` | 95 | `validate_report_meta` | 95 | `repolens-report` | `#/properties/merge` | `unconditional` | direct |
| 22 | `validate_merge_meta.py` | `validate_report_meta` | 114 | `validate_report_meta` | 114 | `repolens-delta` | – | `unconditional` | direct |
| 23 | `core/relation_card_validate.py` | `validate_relation_card` | 226 | `_schema_check` | 159 | `relation-card.v1` | – | `unconditional` | delegated |
| 24 | `core/relation_card_validate.py` | `validate_relation_card` | 235 | `_schema_check` | 159 | `architecture.graph.v1` | – | `unconditional` | delegated |

Die zwei delegierten `relation_card_validate`-Flows rufen `_schema_check` an
Zeile 226 beziehungsweise 235 auf; die eigentliche Instanzvalidierung läuft
gemeinsam in `_schema_check` an Zeile **159**.

## 11. Direkte und delegierte Engine-Aufrufe

Für die 24 akzeptierten Flows:

| `engine_invocation` | Anzahl |
|---|---:|
| `direct` | 22 |
| `delegated` | 2 |

Der externe Flow in `adapters/sources.py` ist ebenfalls delegiert:
`refresh` ruft `_validate_snapshot` an Zeile 299 auf; die Engine läuft dort an
Zeile 178. Dieser externe Flow wird nicht in die obige 24er-Achse eingerechnet.

## 12. Schema-Bindungsachse

| `schema_binding_origin` | Anzahl |
|---|---:|
| `same_module_loader` | 11 |
| `same_symbol_literal` | 9 |
| `same_module_constant` | 2 |
| `caller_parameter` | 2 |

Diese Achse ist unabhängig davon, ob die Engine direkt oder delegiert aufgerufen
wird.

## 13. Schemafragmente und Aktivierung

Ein Flow verwendet ein Subschema:
`validate_merge_meta.validate_report_meta` gegen
`repolens-report.schema.json#/properties/merge`.

Die Aktivierungsachse der 24 Flows lautet:

| Zustand | Anzahl |
|---|---:|
| `unconditional` | 22 |
| `range_ref_version != "2"` | 1 |
| `range_ref_version == "2"` | 1 |

Damit gibt es **22 unbedingte Flows und zwei bedingte Flows an einer
Engine-Callsite**.

## 14. Externer Flow

| relation owner | relation line | engine owner | engine line | schema | scope |
|---|---:|---|---:|---|---|
| `adapters.sources.refresh` | 299 | `_validate_snapshot` | 178 | `metarepo/contracts/fleet/fleet.snapshot.schema.json` | `external_static_relative` |

`refresh()` validiert nur den Fleet-Snapshot. Der Organism-Snapshot wird gebaut
und geschrieben, aber nicht gegen ein Schema validiert.

## 15. Meta-Validierung

`Draft*Validator.check_schema(...)` wird orthogonal zu den
Instanzvalidierungs-Flows erfasst:

- 5 Meta-Engine-Callsites
- 6 schemaspezifische Meta-Flows

`relation_card_validate._schema_check` prüft an derselben Meta-Callsite zwei
verschiedene Schemata. Meta-Flows werden nicht zu den 24 Instanzflows addiert.

## 16. Test- und Parseinventar

- 44 Test-Facet-Dateien enthalten mindestens einen erkannten
  Instanzvalidierungs-API-Aufruf.
- Ein vollständiger AST-Parsefehler liegt vor:
  `merger/lenskit/tests/fixtures/entrypoints_test_project/invalid.py`, Zeile 1,
  Meldung `'(' was never closed`.
- Die Parsefehlermenge wird exakt assertiert.

## 17. Schema-Abdeckung

| Metrik | Wert |
|---|---:|
| `*.schema.json` gesamt | 54 |
| mit akzeptierter In-Repo-Instanzvalidierungsrelation | 18 |
| ohne akzeptierte In-Repo-Instanzvalidierungsrelation | 36 |

Die 36 Dateien werden nicht als `load_only` klassifiziert. Gründe können unter
anderem Tests, Produktion, Referenzierung, Dokumentation oder nicht untersuchte
dynamische Pfade sein.

## 18. Dependency- und Schemaachsen

### Dependency-Anforderung

| Wert | Anzahl |
|---|---:|
| `optional_module_import` | 15 |
| `dynamic_runtime_import` | 7 |
| `required_at_module_import` | 2 |

### Verhalten bei fehlender Dependency

| Wert | Anzahl |
|---|---:|
| `raises_runtime_error` | 6 |
| `raises_domain_error` | 4 |
| `returns_failed_check_skipped_unavailable` | 4 |
| `module_import_failure` | 2 |
| `returns_environment_error` | 2 |
| `silent_skip` | 2 |
| `warn_and_continue` | 2 |
| `returns_blocked` | 1 |
| `structural_fallback` | 1 |

### Schema-Anforderung

| Wert | Anzahl |
|---|---:|
| `required` | 21 |
| `optional` | 3 |

Optional sind:

1. `graph_index.load_graph_index`
2. `pr_schau_bundle.load_pr_schau_bundle`
3. der Delta-Schema-Flow in `validate_merge_meta.validate_report_meta`

### Verhalten bei fehlendem Schema

| Wert | Anzahl |
|---|---:|
| `raises_runtime_error` | 11 |
| `returns_blocked` | 6 |
| `raises_domain_error` | 2 |
| `returns_environment_error` | 2 |
| `silent_skip` | 2 |
| `warn_and_continue` | 1 |

## 19. Validator-Drafts und Formatprüfung

| `validator_draft` | Anzahl |
|---|---:|
| `auto-selected` | 15 |
| `draft7` | 6 |
| `draft2020-12` | 3 |

| `format_checker_mode` | Anzahl |
|---|---:|
| `none` | 22 |
| `FormatChecker` | 1 |
| `custom_date_time_checker` | 1 |

## 20. Consumeranalyse und Richtung

Es existiert kein implementierter oder verbindlich spezifizierter Consumer.
`Validator → Schema` ist lediglich die bevorzugte Darstellung dieses Proofs,
keine contractuell festgelegte Richtung.

## 21. Persistenzentscheidung

**Ergebnis C — zurückstellen.**

Das Gate für einen persistierten Contract bleibt geschlossen:

- kein implementierter oder verbindlich spezifizierter Consumer;
- kein belegter Persistenzvorteil gegenüber On-Demand-Auflösung;
- Relationsidentität nicht contractuell festgelegt;
- Name und Contractrichtung nicht entschieden;
- externe und bedingte Flows benötigen ein ausdrücklich festgelegtes Modell;
- ein Goldset fehlt.

Die Abdeckung 18/54 ist ein Coverage-Befund und kein Persistenzblocker.

## 22. Negativsemantik

Eine statisch nachvollziehbare Beziehung beweist nicht:

`schema_correctness`, `validator_completeness`, `runtime_execution`,
`runtime_correctness`, `test_sufficiency`, `regression_absence`,
`change_impact`, `consumer_need`, `repo_understood`, `forensic_ready`.

`load_only`- und `path_reference_only`-Callsites wurden nicht vollständig
inventarisiert.

## 23. Reproduktion

```bash
python3 docs/proofs/_repro/guard_relation_validates_schema_audit.py \
  --repo "$REPO" \
  --base-sha 05bbd0d608afa8faf581887a455d4dcf6fa15ae9 \
  --output /tmp/a.json

python3 docs/proofs/_repro/guard_relation_validates_schema_audit.py \
  --repo "$REPO" \
  --base-sha 05bbd0d608afa8faf581887a455d4dcf6fa15ae9 \
  --output /tmp/b.json

cmp /tmp/a.json /tmp/b.json
cmp /tmp/a.json \
  docs/proofs/guard-relation-cards-v1b-validates-schema-audit.json
```

Das Audit beendet sich mit Fehlerstatus bei Inventardrift, unbekannten
Engine-Callsites, falschen Owner-/Zeilenbindungen, ungeklärten Textkandidaten,
abweichenden Meta-Callsites, unerwarteten Parsefehlern oder offenen Summen.
