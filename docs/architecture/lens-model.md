---
doc_type: architecture
status: active
---

# Deterministic Lens Model

## 1. Dokumentrolle

Dieses Dokument normiert Begriffe und Schichtengrenzen der deterministischen Linsenarchitektur.
Es ist keine Runtime-Evidence.
Es ist kein Contract.
Es ist kein Beweis, dass alle Zuordnungsregeln vollständig oder optimal sind.

## 2. Verbindlicher Kernsatz

Eine Lenskit-Linse ist eine deterministische, abgeleitete Sicht auf Repo-Artefakte.
Sie besitzt eine Herkunftsregel und eine explizite Geltungsgrenze.
Sie dient der Navigation und erzeugt kein eigenes Wahrheits-, Review-, Sicherheits- oder Impact-Urteil.

## 3. Primary Lens

Jeder auditierbare Repo-Pfad erhält genau eine Primary Lens.
Die Primary Lens beschreibt ausschließlich die primäre technische Rolle des Pfads.

Die kanonischen IDs bleiben:
- `entrypoints`
- `core`
- `interfaces`
- `data_models`
- `pipelines`
- `ui`
- `guards`

Die Primary Lens wird aktuell über die bestehende deterministische Heuristik `infer_lens()` bestimmt.
Der Primary Lens Audit erklärt diese Zuordnung über `matched_rule`.
Audit und Erklärung dürfen die bestehende Zuordnung nicht überschreiben.

Primary Lens beantwortet:
> Was ist dieser Pfad primär?

Primary Lens beantwortet ausdrücklich nicht:
- Warum ist der Pfad für einen bestimmten PR relevant?
- Ist der Pfad semantisch wichtig?
- Welche Änderung wirkt auf welche Runtime?
- Sind Tests ausreichend?
- Ist ein Review vollständig?
- Ist eine Änderung sicher?

## 4. Facet

Ein Facet ist eine additive Sichtachse.
Ein Pfad darf null, ein oder mehrere Facets besitzen.
Facets verändern die Primary Lens nicht.
Facets dürfen keine zweite konkurrierende Primary-Lens-Ebene bilden.

Jede Facet-Zuordnung braucht später mindestens:
- `target_path`
- `name`
- `source_rule`
- `confidence_class`
- `does_not_establish`

Facets müssen deterministisch aus repo-belegten Regeln ableitbar sein.
Facets sind Navigation, keine Inhaltswahrheit.

**Kandidaten für Facet Model v1** (noch nicht als implementierter oder endgültiger Contract normiert):
- `contract`
- `artifact_surface`
- `diagnostic`
- `retrieval`
- `claim_boundary`
- `security`
- `test_guard`

Begriffe wie `impact`, `test_relevance` und `runtime_causality` bleiben ausdrücklich keine Primary Lenses und keine unbelegten v1-Facets.

## 5. Confidence Class

Confidence Class beschreibt die Herkunftsqualität der Zuordnung.
Sie ist keine Wahrscheinlichkeit und kein Korrektheitswert. Numerische Confidence Scores sind nicht vorgesehen.

### `direct`
Die Zuordnung folgt unmittelbar aus einer kontrollierten Eigenschaft, beispielsweise:
- expliziter Pfad
- Dateisuffix
- bekannte Contract-Datei
- deklarierte Artifact Role
- direkt vorliegender Schema- oder Manifestwert

### `derived`
Die Zuordnung wird deterministisch aus vorhandenen strukturierten Artefakten oder mehreren direkten Signalen abgeleitet.

### `heuristic`
Die Zuordnung folgt einer dokumentierten, deterministischen Heuristik, ist aber kein Beweis für semantische Bedeutung oder Vollständigkeit.

## 6. Relation

Eine Relation verbindet zwei adressierbare Repo- oder Bundle-Artefakte.
Eine Relation braucht Quelle, Ziel, Relationstyp und Herkunft.
Direkte, abgeleitete und heuristische Relations müssen unterscheidbar bleiben.
Eine Relation beweist keine Kausalität und keinen Change Impact.
Pfadnähe, Importnähe oder gemeinsame Benennung allein dürfen nicht als Runtime-Wirkung ausgegeben werden.

Relation beantwortet:
> Welche deterministisch belegte oder ausdrücklich heuristische Verbindung ist sichtbar?

Relation beantwortet nicht:
> Was bricht, wenn sich die Quelle ändert?

## 7. State

Ein State beschreibt einen epistemischen oder Auflösungszustand einer Zuordnung, Relation oder Evidence-Adresse.

Beispielkandidaten:
- `missing_evidence`
- `heuristic_assignment`
- `unresolved_reference`

States sind keine Dateirollen und keine Primary Lenses.

Ein State wie `missing_evidence` bedeutet nicht automatisch:
- Aussage falsch
- Implementierung defekt
- Test fehlgeschlagen
- Änderung unsicher

Die konkrete State-Taxonomie bleibt einem späteren Contract vorbehalten.

## 8. Task Context

Task Context erklärt, warum ein Artefakt für eine bestimmte Aufgabe navigativ relevant ist.

Beispiele:
- `pr_review`
- `contract_change_review`
- `artifact_surface_review`
- `security_review`
- `roadmap_status_claim`

Abgrenzung:
- Task Context ändert nicht die Primary Lens.
- Task Context ist nicht dauerhaft mit dem Pfad identisch.
- Task Context ist eine Consumer-/Aufgabensicht.
- Relevanz für eine Aufgabe beweist keinen Change Impact oder Review-Befund.

Bestehende Required-Reading-Profile werden nicht als Lens-Taxonomie umdefiniert.

## 9. Lens Card

Eine Lens Card ist eine kleine, abgeleitete Navigationseinheit.
Sie kann später Primary Lens, Facets, Navigation-Refs, States und begrenzte Relations zusammenführen.

Sie bleibt:
- `authority = navigation_index`
- `canonicality = derived`

Sie ersetzt weder `canonical_md` noch die zugrunde liegenden Contracts oder Evidence-Ranges.
Sie enthält keine automatischen Findings oder Fix-Vorschläge.

Verbotene unqualifizierte Card-Semantik:
`verdict`, `approved`, `safe`, `complete`, `covered`, `critical`, `impact`, `breaks`, `requires_fix`

## 10. Relation Card und Guard Relation

Diese sind spätere Spezialisierungen und werden in v1 nicht implementiert.

### Relation Card
Kleine Navigationseinheit für eine Relation mit Herkunft und Evidence-Grenze.

### Guard Relation
Spezialisierte Relation zwischen einem Ziel und einem Guard-, Test-, Validator- oder CI-Pfad.
Guard Relation bedeutet nicht:
- Testabdeckung vollständig
- Guard wirksam
- CI ausreichend
- Regression ausgeschlossen

## 11. Agent Consumption Trace korrekt einordnen

Der Agent Consumption Trace ist keine Lens-Primitive.
Korrekte Einordnung:
- angrenzende Consumption-/Compliance-Fläche
- erklärt deklarierte Nutzung von Artefakten
- kann Lens Cards später konsumieren
- ist selbst weder Primary Lens, Facet, Relation noch State
- beweist kein tatsächliches Lesen oder Repo-Verständnis

## 12. Schichtenmodell

| Schicht      | Kardinalität pro Pfad | Zweck                           | Darf nicht behaupten |
| ------------ | --------------------: | ------------------------------- | -------------------- |
| Primary Lens |               genau 1 | primäre technische Rolle        | Wichtigkeit, Impact  |
| Facet        |                  0..n | additive Sichtachsen            | Wahrheit, Priorität  |
| Relation     |                  0..n | sichtbare Verbindung            | Kausalität, Bruch    |
| State        |                  0..n | epistemischer/Auflösungszustand | Fehlerurteil         |
| Task Context |       0..n je Aufgabe | aufgabenspezifische Navigation  | Review-Befund        |
| Lens Card    |            abgeleitet | kompakte Navigation             | Inhaltsautorität     |

## 13. Negativsemantik

Als gemeinsame Mindestgrenze für zukünftige Lens-/Facet-/Relation-/Card-Artefakte gilt:

```json
{
  "does_not_establish": [
    "truth",
    "correctness",
    "completeness",
    "runtime_behavior",
    "test_sufficiency",
    "regression_absence",
    "semantic_importance",
    "review_priority",
    "change_impact"
  ]
}
```

Hinweis: Bestehende Contracts dürfen andere Feldnamen wie `does_not_mean`, `does_not_prove` oder `claim_boundaries` verwenden. Dieser PR migriert oder vereinheitlicht bestehende Contracts nicht. Die semantische Grenze soll konsistent sein; die Feldnamenmigration ist kein Ziel.

## 14. Determinismus-Invarianten

1. Gleicher Repo-Zustand und gleiche Regeln erzeugen dieselben Zuordnungen.
2. Ausgaben werden stabil sortiert.
3. Mehrfachzuordnungen werden deterministisch dedupliziert.
4. Keine Netzwerkanfrage ist für die Klassifikation erforderlich.
5. Keine LLM- oder Embedding-Auswertung ist erforderlich.
6. Keine Systemzeit darf die Zuordnung verändern.
7. Heuristische Regeln werden explizit benannt.
8. Unbekannte Begriffe werden nicht still zu bekannten Facets umgedeutet.
9. Neue Facets ändern keine bestehende Primary Lens.
10. Abgeleitete Karten bleiben regenerierbar.

## 15. Authority- und Truth-Grenze

`canonical_md` bleibt die einzige Inhaltswahrheit eines Dump-Bundles.
Primary Lens Audit, Facets, Relations, States und Lens Cards sind abgeleitete Navigation.
Health- und Surface-Pässe beweisen weder Repo-Verständnis noch Claim-Wahrheit.

## 16. Sequenzierung

Der verbindliche Folgepfad:
1. Primary Lens Audit v1 — Core/Contract/Tests umgesetzt
2. Lens Model — dieser PR
3. Facet Model v1 — nächster Implementierungsslice
4. Lens Cards v1
5. PR Delta Cards
6. Relation Cards
7. Guard Relation Cards

Klarstellung:
- Der Primary Lens Audit wird derzeit nicht automatisch als neues Bundle-Artefakt emittiert, sofern dies im aktuellen Code nicht implementiert ist. Dieser PR fügt keine solche Emission hinzu.
- Facet Model v1 ist der nächste Code-Slice.

## 17. Open decisions for Facet Model v1

Folgende Entscheidungen bleiben bewusst vertagt und sind Teil des Facet Model v1 PRs:
1. exakte minimale v1-Facet-Liste
2. exakte JSON-Output-Form
3. ob ein Gesamtbericht oder einzelne Zuordnungen erzeugt werden
4. Sortier- und Deduplizierungsregeln im Contract
5. erlaubte `source_rule`-Taxonomie
6. ob Evidence-Refs in v1 Pflicht oder optional sind
7. Bundle-/Manifest-Sichtbarkeit
8. CLI und automatische Emission
9. Verhalten bei unbekannten Facet-Namen
10. Verhältnis zwischen `claim_boundary` und allgemeiner Unsicherheitssemantik
