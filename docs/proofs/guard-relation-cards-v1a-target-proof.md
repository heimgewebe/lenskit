# Guard Relation Cards v1a (Target Proof)

## Status und Auftrag

Dieser PR enthält einen diagnosis-only Target-Proof für den ersten Guard-Relation-Slice `tests_by_name`. 
Es ist **kein Produktionscode** enthalten. Der Scope ist strikt auf die Untersuchung einer namensbasierten Beziehung (`tests_by_name`) zwischen Testdateien und Zielpfaden begrenzt.
Der verwendete Base-SHA ist `58b8453ba6e355ab361743da75466dd6b0cc19a6`.

## Live-Preflight

- **Repo**: `/home/alex/repos/lenskit` (heimgewebe/lenskit)
- **Branch**: `docs/guard-relation-cards-v1a-target-proof`
- **Worktree**: `/home/alex/repos/lenskit-worktrees/guard-relation-cards-v1a-target-proof`
- **origin/main-SHA**: `58b8453ba6e355ab361743da75466dd6b0cc19a6`
- **Parallelitätsprüfung**: Keine überlappenden offenen PRs oder Branches gefunden.
- **Vorgängerstatus**: Relation Cards v1 sind gemergt und der Post-Merge-Zustand ist abgeschlossen (`docs/proofs/relation-cards-v1-target-proof.md` existiert und `TASK-RELATION-CARD-001` ist `done`). Keine Guard-Relationen sind aktuell implementiert.

## Belegter Ist-Zustand

- **Facet-Testklassifikation**: `merger/lenskit/core/lens_facets.py` akzeptiert `test_*.py`, `test_*.js`, `*_test.py`, `*.test.ts`, `*.spec.ts` als `test`-Marker. Dateipfade mit dem Segment `fixtures` werden ausdrücklich als Test ausgeschlossen. Die öffentliche API liefert Zuweisungen ohne Synthetik; `_normalize_path` bleibt lokal privat.
- **Pfadgrenzen**: C0/C1-Controls, surrogates, whitespace-only, absolute Pfade und Windows-Laufwerke werden am Eingang abgelehnt (Artifact-Boundary). Ordentliche Pfade werden von `_normalize_path` für die Validierung vollständig verarbeitet.
- **Relation-Card-v1-Grenzen**: Strikt `imports`-only. Die Relationskante `imports` ist fixiert. `S1` bleibt die Evidenzstufe und es findet keine eigenständige Erkennung statt.
- **Validator-Konvention**: Validatoren nutzen Dependency Diagnostics (z.B. jsonschema). Bei Fehlen erfolgt kein automatisches `skipped_unavailable` Minimal-Fallback, wenn es nicht implementiert ist, sondern es wird als Degradierung gemeldet.

## Falsifikation des breiten Plans

Die sechs Guard-Relation-Kandidaten (`tests_by_name`, `tests_by_path`, `validates_schema`, `checks_surface`, `checks_cli`, `checks_security`) gehören nicht in einen gemeinsamen ersten PR, weil jede Relation eine grundlegend andere Source-Heuristik aufweist (Namensgleichheit, Verzeichnisstruktur, JSON-Schema-Verweise, Funktionsaufrufe) und das Ambiguitäts-Risiko unterschiedlich ist. Eine gemeinsame Integration würde die Komplexität bezüglich Ambiguitätsauflösung, Contract-Design und Diagnose massiv erhöhen und die Evaluation durch die Consumermatrix behindern.

## Repository-Messung

Es wurden 589 getrackte Repository-Dateien ausgewertet.

| Kategorie | Pfade |
| --- | --- |
| Gesamte getrackte Pfade | 589 |
| Kontrollierte Testpfade | 209 |
| Ausgeschlossene Fixtures | 1 |

Die Test-Marker verteilen sich primär auf `test_*.py`, `test_*.js`, `*_test.py`, `*.test.ts`, `*.spec.ts`.

**Resolvervarianten**

| Variante | Erklärung | Eindeutige Matches (1) | Nichttreffer (0) | Ambiguität (>1) | 
| --- | --- | --- | --- | --- |
| A. Globaler Basename | `test_<name>.py` → `<name>.py` global im Inventar | 42 | 165 | 0 |
| B. Kontrollierte Root-Paare | Tests unter `/tests/` auf `core/` abbilden | 30 | 177 | 0 |
| C. Relativer Spiegel | `pkg/tests/test_foo.py` → `pkg/foo.py` | 3 | 204 | 0 |
| D. Explizite Registry | Manuelle `test_path` → `target_path` Liste | (exakt, aber manuell) | - | - |

**Bewertung der Varianten:**
- **Variante A** bietet die höchste Trefferquote (42), birgt jedoch zukünftig das größte Risiko für False Positives, wenn gleichnamige Module in verschiedenen Verzeichnissen existieren.
- **Variante B** erfordert ständige Pflege hartcodierter Root-Paar-Listen, deckt aber zumindest 30 Fälle sicher ab.
- **Variante C** findet im aktuellen Repository kaum Anwendung (3 Treffer), was zeigt, dass Testdateien und Zielmodule nicht in spiegelbildlich benachbarten Strukturen liegen.

**Mögliche False Positives**: Bei Variante A kann ein Test `test_foo.py` fälschlicherweise auf ein irrelevantes `foo.py` verweisen, falls der Name nicht distinktiv genug ist. 
**Reale Beispiele (Variante A)**: 
- Positiv: `merger/lenskit/tests/test_post_emit_health.py` → `merger/lenskit/core/post_emit_health.py`
- Negativ: `merger/lenskit/tests/test_graph_bundle_integration.py` → `[]` (Kein Ziel `graph_bundle_integration.py` vorhanden).

## Consumeranalyse

Es konnte **kein aktiver Consumer** für die Relation `tests_by_name` identifiziert werden. 
* Weder `Agent Reading Pack`, noch `Lens Cards`, `WebUI` oder `Retrieval` fragen aktuell formalisierte Test-Ziele ab.
* **Konkrete Frage**: "Welches Target wird von dieser Datei getestet?" kann zwar gestellt werden, aber es existiert kein Aufrufer, der diese Information persistiert über ein Card-Artefakt benötigt.
* **Persistenzbedarf**: Eine On-Demand-Berechnung zur Diagnose reicht vorerst völlig aus, da keine Pipeline die Auswertung voraussetzt. 
* Dies ist eine **epistemische Leerstelle**.

## Relationsrichtung

- **Target → Test**: Nützlich um zu fragen "Welche Tests sichern diese geänderte Datei ab?"
- **Test → Target**: Nützlich um zu fragen "Was testet diese Datei?"
- **Empfehlung**: **Target → Test** (oder "Welche Tests sind diesem Ziel zugeordnet"). Da viele Tests Integrationstests sind, ist die Zuordnung ohnehin oft m:n. Aus Sicht der Agenten-Bewertung ist oft das Target gegeben und die zugehörigen Test-Guards werden gesucht. Da kein belegter Bedarf für beide Richtungen vorliegt, sollte keine doppelte Card persistiert werden.
- **Gegenargument**: Die Heuristik arbeitet ausgehend vom Test-Namen, weshalb Test → Target die natürlichere Entdeckungsrichtung ist.

## Resolverentscheidung

**Empfehlung**: Die Variante **Globaler Basename (Variante A)** liefert die meisten Treffer, sollte aber **nur als Diagnose-Matcher** eingesetzt werden (keine Persistenz). Die Alternative **Explizite Registry (Variante D)** ist sicherer und sollte bevorzugt werden, wenn ein Contract eingeführt wird. Ohne Consumer sollte jedoch kein Resolver in einen Contract gegossen werden.

## Contractstrategie

**Empfehlung**: Option 3 – **Diagnose-only Matcher ohne Contract**.
- Es gibt keinen nachgewiesenen Consumer, der eine Card persistiert benötigt.
- Eine Erweiterung von `relation-card.v2` würde den strikten `imports-only`-Vertrag verwässern.
- Ein eigener `guard-relation-card.v1` Contract würde zusätzliche Artifact/Validator-Last erzeugen, ohne aktiven Nutzen.
Eine reine Diagnose-Funktionalität ermöglicht Evaluation, ohne sich architektonisch zu binden.

## Evidenzmodell

Eine S1-Evidenz aus `architecture.graph.v1` kann nicht übernommen werden, da Namensähnlichkeit keine statische Import-Evidenz ist. 
- Die Derivation ist `heuristic`.
- Ein eigenes Evidenzlevel ist für Namens-Matching kaum sinnvoll, sofern es nicht aus einer Registry (höhere Evidenz) stammt.
- Redundanz: Felder wie `source_basename` wären vollständig redundant zum Pfad ableitbar.

## Identität und Deduplizierung

- Ein Tupel `(relation, source, target)` ist ausreichend.
- Eine spätere Mehrfachregel-Generierung erfordert kein `source_rule` im Schlüssel, falls diese nicht unabhängig konsumiert wird.
- **Empfehlung**: Eine simple On-Demand-Regel zur Evaluation implementieren, keine persistierte Identität erzeugen.

## Input- und Pfadmodell

- **Inventarquelle**: Ein explizites Iterable aus repo-relativen Pfaden (Strings) statt eines direkten Git-Aufrufs im Producer.
- **Normalisierung**: Die bestehende `_normalize_path` Normalisierung der Facets sollte in eine öffentliche Repo-Path-API refaktoriert werden. 
- **Generatoren**: Das Inventar muss einmal zu einem Set dedupliziert und determnistisch sortiert materialisiert werden, da Iteratoren nur einmal konsumiert werden können.
- **String-Sonderfall**: Einzelne Strings dürfen nicht iteriert werden (TypeError).

## Ambiguität

- 0 Kandidaten → keine Relation
- 1 Kandidat → mögliche Relation
- \>1 Kandidat → keine Relation (Fail-Closed)
- Ungültige / Nicht-Test-Pfade am Eingang → keine Zuordnung.
- Es wird keine Fuzzy-Nähe oder Priorität zur Auflösung von Mehrdeutigkeiten verwendet. 
Ein fehlgeschlagenes Matching (0 oder >1) sollte diagnostisch begründbar sein, wird aber nicht emittiert.

## Validatorstrategie

Eine Checkkette würde lauten: `schema_validation`, `source_inventory_validation`, `source_producer_coherence`, `projection_preservation`.
- **Jsonschema-Ausfall**: Wenn jsonschema fehlt, wird die Schema-Prüfung nicht ausgeführt, eine maschinenlesbare Dependency-Diagnose wird emittiert und der Gesamtstatus ist `fail`.
- Es wird kein lokaler Minimal-Fallback empfohlen.

## Negativsemantik

Eine namensbasierte Heuristik (`tests_by_name`) **darf folgende Aspekte niemals etablieren**:
`truth`, `correctness`, `completeness`, `runtime_behavior`, `runtime_correctness`, `test_sufficiency`, `coverage_completeness`, `guard_effectiveness`, `regression_absence`, `semantic_importance`, `review_priority`, `change_impact`, `runtime_dependency`, `causality`, `security_assessment`.
Dies schließt Coverage- und Runtime-Aufwertungen strikt aus.

## Alternative Sinnachse

**On-Demand Matcher ohne persistiertes Card-Artefakt**:
Ein Diagnose-Tool, welches das Inventar lädt und On-Demand für ein Target dessen Test-Kandidaten liefert. Dies verursacht keine Artifact-Schulden und ist sofort evaluierbar.

## Empfehlung

**Richtung 4: Task stoppen.**
Da es keine absehbaren Consumer gibt und eine persistierte Card für eine bloße Namensheuristik ein zu hohes Ambiguitäts- und Redundanz-Risiko birgt, sollte die Entwicklung eines `guard-relation-card` Contracts für `tests_by_name` vorerst gestoppt werden. Die Untersuchung der Relationen zeigt, dass eine explizite Registry zielführender wäre. Alternativ (falls gewünscht) kann ein reiner Diagnose-only Matcher (Richtung 2) implementiert werden, aber es wird abgeraten, bevor ein echter Bedarf entsteht.

## Implementierungsgate

Vor dem Schreiben von Produktionscode müssen geklärt sein:
1. Konkrete Consumerfrage
2. Gewählte Relationsrichtung
3. Exakt definierte Match-Regel
4. Festgelegtes Ambiguitätsverhalten
5. Contractstrategie
6. Evidenzmodell
7. Identitätsregel
8. Inventar- und Pfadmodell
9. Jsonschema-Ausfallverhalten
10. Negativsemantik
11. Realistisches Goldset
12. Test- und CI-Scope
Da Punkt 1 (Consumer) fehlt, bleibt das Gate geschlossen.
