# PR Delta Cards v1 - Gap Report

## 1. Vorhandene Delta-Source
Die Delta-Quelle wird vom `pr_schau_bundle.py` Loader bereitgestellt oder existiert als `pr-schau-delta.v1.schema.json` konformes `delta.json`. Es beinhaltet `files[]` mit Dateipfaden, einem `status` (`added`, `changed`, `removed`), sowie Hash- und Lexikal-Heuristik-Werten.

## 2. Vorhandene Lens-Card-Source
`merger/lenskit/core/lens_cards.py` bietet `produce_lens_card(path)`, welche einen gegebenen String-Pfad verarbeitet, den `Facet Model v1` Produzenten `infer_facets` aufruft, den Pfad validiert und eine normierte Lens-Card (mit `authority="navigation_index"`, `canonicality="derived"`, `primary_lens` und negativen Semantiken) erstellt.

## 3. Fehlende Zielimplementierung
Eine Verknüpfung beider Welten: Wir benötigen ein Artefakt ("PR Delta Card"), das für jeden geänderten Pfad in einem PR-Schau-Delta eine kontrolliert abgeleitete Lens-Einordnung bietet.

## 4. Source-Authority und Grenzen
- Die abgeleitete Card darf nicht als objektive Wahrheit oder als Risikobewertung ausgegeben werden.
- PR-Schau Bundles haben `canonical_content` Authority, während Lens-Cards rein navigative (`navigation_index`) Authority besitzen. Wir übernehmen für die Lens-Projektion die bestehende Authority der Lens Cards.
- Die Card darf keine neue Authority erfinden. Sie gibt lediglich an: "Dieser Pfad hat diesen Status und wird von dieser Lens abgedeckt."

## 5. Kardinalität
Genau eine PR Delta Card pro Dateieintrag (`files[]`) in der Source-Delta-Struktur.

## 6. Identitäts- und Provenienzentscheidung
- **Identität**: `path` innerhalb eines expliziten Delta-Kontexts (`source_kind`, `repo`, `generated_at`). Es ist keine universelle Hash-Identität.
- **Provenienz**: Optional kann ein Source-Hash (`source_delta_sha256`) übernommen werden, dieser ist jedoch kein Identitätsbeweis oder GitHub-PR-Beweis.

## 7. Outputshape-Entscheidung
Wir wählen Variante A (flache kontrollierte Projektion), da der Validator Parität erzwingen kann und sie wesentlich kompakter ist. 
Wir projizieren: `path`, `change_status`, `primary_lens`, `matched_rule`, `facets`, und `navigation_refs`.
Ebenfalls übernehmen wir die strikte Negativsemantik (`does_not_establish`).

## 8. Inputgrenze
`produce_pr_delta_cards` akzeptiert ein vollständig formatiertes Delta-Dictionary (mit `repo`, `generated_at`, `files`), ohne dabei selbst File-I/O oder Parsing durchzuführen. Standalone-Deltas werden unterstützt.

## 9. Bewusst ausgeschlossene Felder
Ausgeschlossen sind alle Judgment- und Impact-Felder: GitHub-PR-Nummer, Base/Head-Commit, Merge-Base, Rename-Identität, Hunks, Zeilenbereiche, Symbole, Kausalität, Impact, `suspicious_patterns` und `affected_chunk_ids`.

## 10. Contract- und Validatorstrategie
Wir erstellen `pr-delta-card.v1.schema.json` als JSON Schema (Draft-07 konsistent zu `lens-card.v1`), verbieten zusätzliche Eigenschaften, und fordern strikte Enums für Change-Status und Authority.
Der Validator in `pr_delta_card_validate.py` prüft getrennt:
1. formale JSON-Schema Gültigkeit.
2. die Übereinstimmung der Lens-Projektion gegen `produce_lens_card(path)`.
3. die Konsistenz des Delta-Kontexts und Change-Status.

## 11. Teststrategie
- Contracttests: min/max Kardinalität, Status-Enums, Authority-Enums, keine neuen Felder, Negativsemantik-Sortierung.
- Producertests: Determinismus, Input/Output-Kardinalität, Statusbehandlung (insbesondere bei `removed`), Leeres Delta, korrekte Facetten-Einordnung.
- Validatortests: Fehlschlag bei abweichender Primary-Lens oder Navigation, fehlende Judgments.

## 12. Verbleibende Folgearbeiten
- Keine automatische Emission im CLI in diesem PR.
- Keine automatische Bundle-/Manifest-Integration in diesem PR.
- PR-Schau Frontends müssen noch auf die neuen Cards angepasst werden.
