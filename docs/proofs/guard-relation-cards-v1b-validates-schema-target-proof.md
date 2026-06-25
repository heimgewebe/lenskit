# Guard Relation Cards v1b (Target Proof — `validates_schema`)

## 1. Status und Scope

Dieser Target-Proof ist **diagnosis-only**. Er enthält **keinen Produktionscode**,
**kein neues Schema**, **keinen Producer**, **keinen Validator**, **keine CLI** und
**keine persistierte Guard Relation Card**. Der Scope ist strikt auf die statische,
reproduzierbare Inventarisierung einer Schema-Validierungsbeziehung im Base-Snapshot
begrenzt.

Untersucht wird ausschließlich der Kandidat `validates_schema`. Andere
Guard-Relation-Kandidaten (`tests_by_path`, `checks_surface`, `checks_cli`,
`checks_security`) werden **nicht** bewertet.

Kernfrage: *Kann Lenskit aus dem aktuellen Codebestand deterministisch und
reproduzierbar ableiten, welches Modul Daten gegen welches JSON-Schema validiert?*

## 2. Live-Basis und Base-SHA

- **Repo**: `heimgewebe/lenskit`
- **Branch**: `docs/guard-relation-validates-schema-v1b-target-proof`
- **Base-SHA**: `05bbd0d608afa8faf581887a455d4dcf6fa15ae9`
- **Merge-SHA PR #798**: `05bbd0d608afa8faf581887a455d4dcf6fa15ae9` — der Merge-Commit
  von PR #798 (`Merge pull request #798 …`, Parents `58b8453b` + `fea5a71a`) **ist**
  die aktuelle `origin/main`-Spitze. PR #798 ist nachweislich in `origin/main` enthalten.
- **Inventardatei**: `git ls-tree -r --name-only 05bbd0d6` → **590 Pfade**,
  SHA-256 `19ccdd599e32d683b97d71a86b05594b825440bda1b900d32a756517f637b50a`.
- **`*.schema.json`-Dateien im Base-Tree**: **54**.

Alle Diagnosewerte beziehen sich genau auf diesen Base-Snapshot.

## 3. Dokumentarischer Ausgangszustand

- **Relation Card v1** ist `imports`-only (`merger/lenskit/contracts/relation-card.v1.schema.json`).
- Der Producer `merger/lenskit/core/relation_cards.py` projiziert vorhandene Importkanten
  aus `architecture.graph.v1`; **keine** Relationserkennung.
- `validates_schema` ist **kein** unterstützter Relationstyp.
- Es existiert **kein** Guard-Relation-Producer.
- Ein Target-Proof darf diese Grenze nicht verändern und tut es nicht.

## 4. Belegter aktueller Relations-Codebestand

Im Base-Snapshot existieren **18 Produktions-Python-Module** mit mindestens einer
JSON-Schema-**Instanz**validierung gegen eine repo-interne `*.schema.json`-Datei.
Über alle Callsites ergeben sich **24 akzeptierte Validierungsbeziehungen**
(22 direkt, 2 delegiert) gegen **18 distinkte** Schema-Dateien.

> Korrektur gegenüber dem ersten Entwurf dieses Proofs: Eine frühere Fassung nannte
> nur 6 Beziehungen über 4 Module und 48 `load_only`-Schemata und schloss
> `parity_state.py` sowie `forensic_preflight.py` fälschlich als „interne Strukturen
> ohne `*.schema.json`-Pfad“ aus. Beide laden tatsächlich ein repo-internes Schema
> (`citation-map.v1`, `claim-evidence-map.v1`) und rufen `jsonschema.validate(...)`
> darauf auf. Die korrekten, durch Assertions geschlossenen Zahlen stehen unten.

`output_health.py` und `dependency_diagnostics.py` melden nur den
`jsonschema`-Dependency-Status (`jsonschema_dependency(...)`) und validieren selbst
nicht; `bundle_surface_validate.py` führt eine eigene strukturelle Prüfung ohne
`jsonschema`/`*.schema.json` aus. Diese sind **keine** Schema-Validierungsrelationen.

## 5. Nachweis: `validates_schema` ist nicht implementiert

- Repo-weite Suche nach `validates_schema|validates-schema|validates_against_schema|guard_relation`
  in Nicht-Doc-Code liefert **keine** Symbol-, Contract- oder Producer-Treffer.
- `relation-card.v1.schema.json` kennt nur den `relation`-Wert `import` (S1);
  `edge_type`/`evidence_level` modellieren Importkanten, keine Validierungskanten.
- `relation_cards.py` / `relation_card_validate.py` projizieren bzw. validieren
  Import-Relation-Cards; sie erzeugen keine Validierungsrelationen.
- Es existiert kein Contract, Producer, Validator, Test oder Goldset für eine
  Schema-Validierungsrelation. Das bloße Vorkommen von `.schema.json` oder
  `jsonschema` ist keine Guard-Relation-Implementierung.

## 6. Begriffsproblem: `validates_schema` vs. `validates_against_schema`

Der Roadmap-Name `validates_schema` ist mehrdeutig:

1. **Schema-Metavalidierung** — „ein Modul validiert das Schema selbst“ (z. B. via
   `Draft7Validator.check_schema`).
2. **Instanzvalidierung** — „ein Modul validiert Daten gegen das Schema“.

Beide Aussagen dürfen nicht vermischt werden. Die hier gefundenen Beziehungen sind
durchweg **Instanzvalidierung**. Empfehlung (siehe §23): präziser Name
`validates_against_schema` bzw. `validates_instance_against_schema`.

## 7. Source-Population

- **Produktions-Python**: alle `*.py` aus dem Base-Inventar ohne Testpfade.
- **Test-Python**: Pfade mit `/tests/`, Dateiname `test_*.py` oder `*_test.py`.
- **Schema-Dateien**: alle 54 `*.schema.json` aus dem Base-Inventar.
- Drei Test-Fixtures mit absichtlich ungültigem Python werden beim Parsen
  übersprungen (nie Produktionsvalidatoren).

## 8. Analyseverfahren

1. Base-Inventar aus `git ls-tree -r --name-only 05bbd0d6` binden; SHA-256 prüfen.
2. Alle `*.schema.json` bestimmen.
3. **Kandidatengenerator (AST)**: jede Python-Datei parsen und alle Aufrufe der
   JSON-Schema-Instanz-APIs (`.validate(...)`, `.iter_errors(...)`) sowie der
   Meta-API (`.check_schema(...)`) mit umschließendem Symbol und Zeile erfassen.
4. **Manuelle Vollprüfung**: jede produktive Beziehung gegen den Quellcode prüfen
   (Schemapfad-Literal → Laden → Instanz + Schema erreichen `validate`).
5. Klassifizieren nach §9; Mehrfachschema-/Mehrfachvalidator-Fälle getrennt halten.
6. **Vollständigkeit**: Die per AST entdeckten Produktionsdateien mit Instanz-API
   müssen **exakt** der Menge der manuell klassifizierten Produktionsmodule
   entsprechen (Assertion, siehe §30).
7. Alle Summen durch Assertions schließen; deterministisch sortierte JSON-Ausgabe.

Einzige Diagnosequelle: `/tmp/lenskit-validates-schema-audit.py`
→ `/tmp/lenskit-validates-schema-audit.json` (nicht committet).

## 9. Evidenz- und Ausschlussklassen

| Klasse | Definition |
|---|---|
| `instance_validation_direct` | Codepfad löst Schemapfad statisch auf, lädt das Schema und reicht Instanz + Schema **direkt** an eine JSON-Schema-Validierungs-API. |
| `instance_validation_delegated` | Codepfad löst/lädt das Schema und übergibt es an einen **Helper**, der nachweisbar `validate`/`iter_errors` aufruft. |
| `schema_meta_validation` | Code prüft, ob das **Schema selbst** gültig ist (`check_schema`), ohne darauf folgende Instanzvalidierung. |
| `load_only` | Schema wird gelesen/geparst, aber in der Kette nicht zur Validierung verwendet. |
| `path_reference_only` | Schemapfad wird nur erwähnt/dokumentiert/ausgegeben. |
| `unresolved_dynamic` | Schemapfad oder Weitergabe ist statisch nicht eindeutig auflösbar. |
| `test_only` | Beziehung existiert nur in Testcode. |

**Akzeptanzregel** (direkt/delegiert nur bei vollständigem Beleg): Source-Modul +
Symbol bekannt; Schemapfad statisch eindeutig; Schema im Base-Inventar; Instanz +
Schema erreichen eine konkrete `validate`-API; Aufrufkette vollständig; Degradations-
bedingung dokumentiert; nicht auf Namens-, Test-, Import- oder Konstanten-Ähnlichkeit
allein gestützt. Ein Modul, das ein Schema lädt und nur Felder daraus liest,
validiert nichts.

## 10. Vollständige Mengen- und Summenübersicht

Es werden zwei **getrennte Granularitäten** geführt (kein Vermischen):

**(A) Callsite-Granularität** — Einträge im Audit (`items`):

| Klasse | Anzahl |
|---|---|
| `instance_validation_direct` | 22 |
| `instance_validation_delegated` | 2 |
| `schema_meta_validation` | 0 |
| `load_only` (Callsite) | 0 |
| `path_reference_only` (Callsite) | 0 |
| `unresolved_dynamic` | 1 |
| `test_only` (Datei-aggregiert) | 44 |
| **Summe `candidate_callsite_count`** | **69** |

Assertion: `22 + 2 + 0 + 0 + 0 + 1 + 44 = 69`. ✅
Akzeptierte Produktionsbeziehungen (direkt + delegiert): **24**.

> Hinweis: `load_only`/`path_reference_only` sind auf Callsite-Ebene 0, weil der
> Audit gezielt **Validierungs**-Callsites enumeriert. Reine Lade-/Erwähnungs-Stellen
> werden auf Schema-Datei-Ebene erfasst (B), nicht als eigene Items.

**(B) Schema-Datei-Granularität** — Abdeckung der 54 Schemata:

| Metrik | Wert |
|---|---|
| `*.schema.json` gesamt | 54 |
| mit Produktions-Instanzvalidator | 18 |
| ohne Produktions-Instanzvalidator | 36 |

Assertion: `18 + 36 = 54`. ✅

## 11. Tabelle: direkte Instanzvalidierungen (22)

| Source-Symbol | Source-Pfad | Callsite | Schema (`contracts/…`) | Dependency-Modus |
|---|---|---|---|---|
| `load_graph_index` | `architecture/graph_index.py` | 39 | `architecture.graph_index.v1` | skipped_unavailable |
| `load_and_validate_embedding_policy` | `cli/policy_loader.py` | 45 | `embedding-policy.v1` | fail_closed_dependency_missing |
| `verify_basic` | `cli/pr_schau_verify.py` | 80 | `pr-schau.v1` | skipped_unavailable |
| `_validate_post_health_schema` | `core/agent_export_gate.py` | 262 | `post-emit-health.v1` | skipped_unavailable |
| `validate_registry` | `core/doc_freshness.py` | 668 | `doc-freshness-registry.v1` | degraded_structural_precheck |
| `init_federation` | `core/federation.py` | 59 | `federation-index.v1` | fail_closed_dependency_missing |
| `validate_federation` | `core/federation.py` | 87 | `federation-index.v1` | fail_closed_dependency_missing |
| `add_bundle` | `core/federation.py` | 156 | `federation-index.v1` | fail_closed_dependency_missing |
| `add_bundle` | `core/federation.py` | 187 | `federation-index.v1` | fail_closed_dependency_missing |
| `_validate_claim_map_schema` | `core/forensic_preflight.py` | 119 | `claim-evidence-map.v1` | skipped_unavailable |
| `validate_lens_card` | `core/lens_card_validate.py` | 136 | `lens-card.v1` | conditional_jsonschema_available |
| `_validate_citation_map` | `core/parity_state.py` | 349 | `citation-map.v1` | fail_closed_dependency_missing |
| `_validate_claim_evidence_map_schema` | `core/post_emit_health.py` | 331 | `claim-evidence-map.v1` | skipped_unavailable |
| `_validate_manifest_schema` | `core/post_emit_health.py` | 404 | `bundle-manifest.v1` | skipped_unavailable |
| `validate_pr_delta_card` | `core/pr_delta_card_validate.py` | 135 | `pr-delta-card.v1` | conditional_jsonschema_available |
| `_validate_source_delta` | `core/pr_delta_cards.py` | 105 | `pr-schau-delta.v1` | fail_closed_dependency_missing |
| `load_pr_schau_bundle` | `core/pr_schau_bundle.py` | 130 | `pr-schau.v1` | skipped_unavailable |
| `resolve_range_ref` | `core/range_resolver.py` | 193 | `range-ref.v1` | fail_closed_dependency_missing |
| `resolve_range_ref` | `core/range_resolver.py` | 193 | `range-ref.v2` | fail_closed_dependency_missing |
| `_validate_source_graph` | `core/relation_cards.py` | 137 | `architecture.graph.v1` | fail_closed_dependency_missing |
| `validate_report_meta` | `validate_merge_meta.py` | 95 | `repolens-report` (Subschema `merge`) | always_available |
| `validate_report_meta` | `validate_merge_meta.py` | 114 | `repolens-delta` | always_available |

(`merger/lenskit/`-Präfix der Pfade aus Platzgründen weggelassen.)

## 12. Tabelle: delegierte Instanzvalidierungen (2)

| Source-Symbol | Source-Pfad | Delegations-Callsite | Engine-Callsite | Schema | Dependency-Modus |
|---|---|---|---|---|---|
| `validate_relation_card` | `core/relation_card_validate.py` | 226 | `_schema_check` (159) | `relation-card.v1` | conditional_jsonschema_available |
| `validate_relation_card` | `core/relation_card_validate.py` | 235 | `_schema_check` (159) | `architecture.graph.v1` | conditional_jsonschema_available |

`validate_relation_card` lädt Card- und Source-Schema und übergibt sie an den
modulinternen Helper `_schema_check`, der `Draft7Validator(...).iter_errors(...)`
aufruft. Zwei semantisch verschiedene Schemata über denselben Engine-Callsite.

## 13. Tabelle: Schema-Metavalidierungen (0)

Es gibt **keine** eigenständige Schema-Metavalidierung. `check_schema(...)` tritt an
5 Produktions-Callsites auf (`lens_card_validate`, `pr_delta_card_validate`,
`relation_card_validate`/`_schema_check`, `relation_cards`, `pr_delta_cards`), jeweils
**unmittelbar als Schutz vor** der nachfolgenden Instanzvalidierung derselben Kette.
Diese Aufrufe sind Teil der direkten/delegierten Instanzvalidierung, nicht eine
separate `schema_meta_validation`-Relation.

## 14. Tabelle: `load_only` (Callsite-Ebene: 0)

Auf Callsite-Ebene wurden keine reinen Lade-ohne-Validierung-Items modelliert (der
Audit enumeriert Validierungs-Callsites). Die fehlende Produktionsvalidierung wird
auf Schema-Datei-Ebene in §20 erfasst (36 Dateien). Dies vermeidet die in der
Vorfassung vorhandene Vermischung von „Schema-Datei ohne Validator“ mit
„Validierungs-Callsite“.

## 15. Tabelle: `path_reference_only` (Callsite-Ebene: 0)

Keine eigenen Callsite-Items. Beispiel einer reinen Pfaderwähnung ohne Laden/Validieren:
`core/agent_consumption_validate.py:76` nennt
`contracts/agent-consumption-trace.v1.schema.json` nur im Docstring. Solche Erwähnungen
fließen in die Schema-Datei-Abdeckung (§20), nicht in akzeptierte Relationen.

## 16. Tabelle: `unresolved_dynamic` (1)

| Source-Symbol | Source-Pfad | Callsite | Schemapfad | Grund |
|---|---|---|---|---|
| `_validate_snapshot` | `adapters/sources.py` | 178 | (Laufzeit) | `schema_path` wird aus Laufzeit-`hub_path` gebildet und zeigt auf **externe** Metarepo-Schemata (`contracts/fleet/fleet.snapshot.schema.json`, `organism.index.snapshot.schema.json`), die **nicht** im Base-Inventar liegen. |

`adapters/sources.py` validiert echt (`jsonschema.validate`), aber gegen ein
repo-externes, laufzeitabhängiges Schema. Akzeptanzregel 2 (statisch eindeutig) und 3
(im Inventar) sind nicht erfüllt → keine akzeptierte In-Repo-Relation.

## 17. Test-only-Befunde (44 Dateien, getrennt)

44 Testdateien enthalten JSON-Schema-Instanzvalidierungen (gegen geladene Contracts
oder inline aufgebaute Schemata). Sie sind **keine** Produktionsbeziehungen und
werden datei-aggregiert geführt (nicht callsite-enumeriert), um die produktive
Diagnose nicht zu verfälschen. Mehrere der 36 produktionsseitig unvalidierten
Schemata (z. B. `answer-compliance.v1`, `agent-consumption-trace.v1`,
`required-reading-protocol.v1`, `planning-registration-*`) werden ausschließlich in
Tests gegen Instanzen geprüft.

## 18. Optionalitäts- und Degradationsmodi

Verteilung über die 24 akzeptierten Beziehungen:

| Modus | Anzahl | Bedeutung |
|---|---|---|
| `fail_closed_dependency_missing` | 10 | fehlendes `jsonschema` → Exception (`RuntimeError`/`ValueError`/`ParityInputError`/`SourceValidationError`) |
| `skipped_unavailable` | 7 | fehlendes `jsonschema` → Validierung wird übersprungen / „blocked“ / „environment_error“ (kein `pass`) |
| `conditional_jsonschema_available` | 4 | fehlendes `jsonschema` → `skipped_unavailable`-Check, fail-closed (nie `pass`) |
| `always_available` | 2 | harter Import `from jsonschema import Draft202012Validator` (Modul ohne `jsonschema` nicht importierbar) |
| `degraded_structural_precheck` | 1 | `doc_freshness.validate_registry`: fehlendes `jsonschema` → dependency-freier Strukturvalidator |

**Wichtig:** Eine statisch vorhandene Relation bedeutet **nicht**, dass die
Validierung in jeder Runtime ausgeführt wird. Insbesondere `skipped_unavailable` und
`degraded_structural_precheck` belegen zwei verschiedene Ausführungsmodi pro Stelle.

## 19. Mehrfachschema- und Mehrfachvalidator-Fälle

**Ein Modul → mehrere Schemata:**
- `relation_card_validate.validate_relation_card` → `relation-card.v1` **und** `architecture.graph.v1`.
- `post_emit_health` → `claim-evidence-map.v1` (`_validate_claim_evidence_map_schema`) **und** `bundle-manifest.v1` (`_validate_manifest_schema`).
- `validate_merge_meta.validate_report_meta` → `repolens-report` (Subschema `merge`) **und** `repolens-delta`.
- `range_resolver.resolve_range_ref` → `range-ref.v1` **oder** `range-ref.v2`, zur Laufzeit über `is_v2` an **einem** Callsite (193) gewählt → als zwei Schemarelationen geführt.

**Ein Schema ← mehrere Module (Mehrfachvalidator):**
- `claim-evidence-map.v1` ← `post_emit_health._validate_claim_evidence_map_schema` **und** `forensic_preflight._validate_claim_map_schema`.
- `architecture.graph.v1` ← `relation_cards._validate_source_graph` (Producer) **und** `relation_card_validate.validate_relation_card` (Validator).
- `pr-schau.v1` ← `pr_schau_verify.verify_basic` **und** `pr_schau_bundle.load_pr_schau_bundle`.
- `federation-index.v1` ← `federation` an 4 Callsites (`init_federation`, `validate_federation`, `add_bundle` ×2).

Daher wird **callsite-bezogen** modelliert (Source-Symbol + Validierungspfad + Schema),
nicht „ein Modul = ein Schema“. Keine Deduplizierung verschluckt semantisch
verschiedene Calls.

## 20. Schema-Dateien ohne Produktions-Instanzvalidator (36 von 54)

```
agent-consumption-trace.v1   agent-entry-manifest.v1      agent-export-gate.v1
agent-query-session.v1       agent-query-session.v2       answer-compliance.v1
artifact-lookup.v1           atlas-delta.v1               atlas-inventory.v1
atlas-machine.v1             atlas-mode-output.v1         atlas-root.v1
atlas-snapshot.v1            bundle-surface-validation.v1 context-lookup.v1
context-quality.v1           cross-repo-links.v1          diagnostics-lookup.v1
entrypoints.v1               export-safety-report.v1      federation-conflicts.v1
federation-trace.v1          lens-facet.v1                output-health.v1
planning-registration-baseline.v1  planning-registration-report.v1  primary-lens-audit.v1
query-context-bundle.v1      query-result.v1              repolens-agent.v2
required-reading-protocol.v1 retrieval-eval-diagnostics.v1  retrieval-eval.v1
source-acquisition-report.v1 sync.report                  trace-lookup.v1
```

Diese Schemata werden produktiv nicht über eine statisch nachvollziehbare Kette gegen
Instanzen validiert (einige werden in Tests geprüft, andere nur referenziert/erzeugt).
Sie wären bei einer etwaigen Persistenz eine große Noise-Fläche und müssten gefiltert
werden.

## 21. Consumeranalyse

| Stufe | Befund |
|---|---|
| implementierter Consumer | **keiner** — kein Modul liest eine persistierte `validates_schema`-Relation. |
| verbindlich spezifizierter Consumer | **keiner** — Roadmap/Blueprint nennen `validates`/Guard Relations als Ziel, ohne Consumer-Spezifikation. |
| möglicher zukünftiger Consumer | Contract-Review-Navigation, Impact-/Change-Abschätzung, relation-aware Retrieval — jeweils unspezifiziert. |
| nur plausible Idee | „Welche Validatoren liest man bei einem Contract-Review?“ / „Welche Schemas nutzt dieser Validator?“ |

Durchsucht: `docs/blueprints/lenskit-agent-front-door-hardening.md`,
`docs/architecture/lens-model.md`, `docs/retrieval/**`, `docs/roadmap/**`,
`merger/lenskit/retrieval/**`, `core/pr_delta_cards.py`, `cli/pr_explain.py`.

**Fazit: Kein verbindlicher Consumer. Kein Persistenzbedarf belegt.** Aus bloßem
potenziellem Nutzen wird kein Persistenzbedarf abgeleitet.

## 22. Relationsrichtung

| Richtung | Semantik |
|---|---|
| Validator → Schema | „validates data against schema“ |
| Schema → Validator | „is used by validator“ |

Natürliche Leserichtung der 24 Beziehungen: **Validator → Schema**. Eine bidirektionale
Persistenz wird nicht empfohlen, solange kein Consumer eine Richtung verlangt.

## 23. Benennungsempfehlung

`validates_schema` ist mehrdeutig (Metavalidierung vs. Instanzvalidierung, §6). Da
alle gefundenen Beziehungen **Instanzvalidierung** sind, lautet die Empfehlung für
einen etwaigen späteren Contract: **`validates_against_schema`** (oder
`validates_instance_against_schema`). Der Roadmap-Name wird hier **nicht still**
umbenannt; die Ambiguität wird dokumentiert und die Präzisierung empfohlen.

## 24. Contract- und Persistenzoptionen

- **Ergebnis A — persistierter Contract begründbar.** Erfordert reproduzierbare
  Beziehungen **und** eindeutige Semantik **und** verbindlichen Consumer **und**
  belegten Persistenzvorteil. → Consumer fehlt, Name ungeklärt ⇒ **nicht erfüllt**.
- **Ergebnis B — On-Demand-Auflösung genügt.** Beziehungen sind reproduzierbar und
  statisch gebunden; eine On-Demand-Diagnose ist möglich. → **plausibel**, aber ohne
  aktuellen Bedarf.
- **Ergebnis C — zurückstellen.** Bei ungeklärter Semantik/Name, fehlendem Consumer
  oder unzureichender Evidenz.

## 25. Entscheidung

**Ergebnis C — zurückstellen.** Das Gate für einen persistierten
`validates_schema`-Contract ist geschlossen. Gründe:

- Kein implementierter oder verbindlich spezifizierter Consumer.
- Namensambiguität (`validates_schema` vs. `validates_against_schema`) ungeklärt.
- Persistenzvorteil gegenüber On-Demand-Auflösung nicht belegt.
- 36 von 54 Schemata ohne Produktionsvalidator → hohe Noise-Fläche.

Die Beziehungen selbst sind reproduzierbar (24 akzeptiert, durch Assertions
geschlossen). Diese Entscheidung führt in diesem PR **zu keiner**
Produktionsimplementierung — auch ein hypothetisches Ergebnis A würde das nicht.

## 26. Alternative On-Demand-Auflösung

Eine spätere, separate Maßnahme könnte die festen Schemapfad-Literale (`_SCHEMA_PATH`,
`SCHEMA_PATH`, modullokale Pfade) deterministisch replizieren, pro Validator-Modul
auflösen, die Dependency-Modi sichtbar machen und `unresolved_dynamic`-Fälle offen
ausgeben — **ohne** Persistenz. Dieser Proof entscheidet keine solche Implementierung.

## 27. Offene epistemische Leerstellen

- Es fehlt eine verbindliche Consumerfrage, die Richtung, Persistenzbedarf und
  Qualitätsanforderung festlegt.
- Erfasst sind nur Validierungen gegen `*.schema.json`. Validierungen gegen interne
  Datenstrukturen oder externe (Metarepo-)Schemata (`adapters/sources.py`) sind nicht
  als In-Repo-Relationen modelliert.
- Dynamisch oder per Konfiguration geladene Schemata wurden nicht verfolgt.
- Dependency-Semantik ist auf `jsonschema`-Verfügbarkeit beschränkt; weitere
  Runtime-Bedingungen (Feature-Flags, Format-Checker) sind nicht vollständig verfolgt.
- `test_only` ist datei-aggregiert, nicht callsite-genau.

## 28. Negativsemantik

Eine Schema-Validierungsrelation beweist **nicht**:

`schema_correctness`, `validator_completeness`, `runtime_execution`,
`runtime_correctness`, `test_sufficiency`, `regression_absence`, `change_impact`,
`consumer_need`, `repo_understood`, `forensic_ready`.

Ein erfolgreicher statischer Nachweis bedeutet nur:

> Im untersuchten Snapshot existiert eine statisch nachvollziehbare Codekette zwischen
> einer Validierungsstelle und einem bestimmten Schema.

## 29. Implementierungsgates

Falls künftig ein persistierter `validates_against_schema`-Contract erwogen wird,
müssen mindestens bestehen: (1) Namensklärung; (2) Consumer-Nachweis; (3) Richtung;
(4) Source-Kohärenz aller 18 Module / 24 Beziehungen; (5) Modellierung der 5
Dependency-Modi inkl. Degradationspfade; (6) Trennung Instanz- vs. Metavalidierung;
(7) Filter für die 36 unvalidierten Schemata; (8) Behandlung von
`unresolved_dynamic`/externen Schemata; (9) manuelle Review jeder Beziehung;
(10) Goldset vor Persistenz. Dieser Proof öffnet **keines** dieser Gates.

## 30. Reproduktionshinweise

```bash
# Base-Inventar (bindet Base-SHA)
git ls-tree -r --name-only 05bbd0d608afa8faf581887a455d4dcf6fa15ae9 \
  | LC_ALL=C sort -u > /tmp/lenskit-validates-schema-inventory.txt
sha256sum /tmp/lenskit-validates-schema-inventory.txt
#   -> 19ccdd599e32d683b97d71a86b05594b825440bda1b900d32a756517f637b50a

# Kandidatengenerator + Klassifikation + Assertions (nicht committet)
python3 /tmp/lenskit-validates-schema-audit.py
#   -> /tmp/lenskit-validates-schema-audit.json
```

Das Skript parst alle Python-Dateien des Base-Inventars per AST, erfasst alle
`validate`/`iter_errors`/`check_schema`-Callsites, gleicht die entdeckten
Produktionsmodule **exakt** gegen die manuell klassifizierte Tabelle ab und schließt
alle Summen durch Assertions (Sortierung, `len(items) == Σ class_counts`,
`schema_path ∈ inventory` für akzeptierte Relationen, gültige Klassen, keine
Ausschlussklasse unter den akzeptierten Produktionsrelationen,
`validated + load_only == 54`, AST/Review-Dateimengen identisch). Jede der 24
akzeptierten Beziehungen wurde zusätzlich manuell gegen den Quellcode verifiziert.
