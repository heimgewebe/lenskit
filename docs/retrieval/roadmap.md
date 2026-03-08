# Lenskit Retrieval Roadmap

Dieses Dokument ist das kanonische Steuerdokument für die Retrieval-Architektur in Lenskit.
Es trennt abgeschlossene Grundlagen, aktive Arbeit, spätere Phasen und offene Architekturfragen.
Jede aktive Einheit ist abhakbar und mit klaren Stop-Kriterien versehen.

---

## 0. Zielbild

Lenskit soll ein deterministisches Retrieval-System mit robuster lexikalischer Basis (BM25/FTS) und optionaler semantischer Zweitphase sein.

Leitplanken:

- deterministische Artefakte
- nachvollziehbare Provenienz
- maschinenlesbare Explain-Blöcke
- reproduzierbares Eval-Verhalten
- Lenskit-first, semantAH-ready
- keine stille Verschlechterung des Basispfads durch optionale Features

---

## 1. Abgeschlossene Grundlagen

Diese Punkte gelten als vorhanden und sind nicht mehr aktive Kernarbeit, sondern Basis.

### A. Artefakt- und Navigationsbasis
- [x] Bundle-/Dump-basierte Navigation ist etabliert.
- [x] Deterministische Chunk-IDs und Chunk-Artefakte existieren.
- [x] Kanonische Dump-/Index-Artefakte sind vorhanden.

### B. Range / Provenienz-Basis
- [x] Range-Resolver-Grundlage ist vorhanden.
- [x] Query-Resultate können `range_ref` tragen, sofern vorhanden.
- [x] Roundtrip-Grundlage für belegbare Retrieval-Treffer ist vorhanden.

### C. Query / Explain / Eval Basis
- [x] BM25/FTS Query-Pfad existiert.
- [x] Explain-Payload ist vorhanden.
- [x] Gold-Query / Eval-Basis ist vorhanden.
- [x] Stale-Policy / Validitätslogik ist vorhanden.

### D. PR-/Kontext-Basis
- [x] PR-bezogene Retrieval-/Explain-Grundlagen sind vorhanden.

### E. Semantik-Plumbing
- [x] F1a ist abgeschlossen:
  - semantic request marker
  - candidate overfetch
  - diagnostics
  - fail/ignore enforcement
  - CLI-/Policy-Wiring

### F. Graph-Basis
- [x] Graph-bezogene Retrieval-/Rerank-Bausteine sind mindestens teilweise angelegt.
- [x] Deterministische Tie-Break-Stabilisierung ist vorgesehen bzw. implementiert.

---

## 2. Aktive Arbeit

Nur diese Punkte sind aktuell operative Weiterentwicklung.

---

## 2.1 F1b Semantic Reranker Runtime

**Ziel:**
Ein lokaler semantischer Reranker ergänzt den BM25-Kandidatenpfad optional als zweite Phase.

**Prinzip:**
`BM25/FTS -> candidate set -> semantic rerank -> final ranking`

### Deliverables
- [ ] Lokaler semantischer Modellzugang ist integriert.
- [ ] Optional Dependency Pfad ist sauber dokumentiert und nutzbar.
- [ ] Nur unterstützte Konfigurationen werden akzeptiert:
  - [ ] `provider=local`
  - [ ] `similarity_metric=cosine`
- [ ] Nicht unterstützte Provider/Metriken liefern saubere Fehler oder sauberen Fallback gemäß Policy.
- [ ] Candidate-Texte für semantisches Reranking werden korrekt aus dem Retrieval-Pfad bezogen.
- [ ] Semantische Scores werden deterministisch in `final_score` überführt.
- [ ] Explain-/Diagnostics-Payload zeigt semantische Beteiligung sichtbar an.
- [ ] Basispfad ohne Semantik bleibt unverändert stabil.

### Nicht-Ziele
- [ ] Keine Produktivverdrahtung mit semantAH in diesem Schritt.
- [ ] Keine Multi-Provider-Orchestrierung.
- [ ] Keine vollumfängliche Dimensions-Validierung über alle Backends.
- [ ] Keine verpflichtende ML-Abhängigkeit für den Basispfad.

### Stop-Kriterien
- [ ] Lokaler semantischer Reranker läuft deterministisch.
- [ ] Fehlende optionale Dependency erzeugt keine neue Failure-Klasse im Basispfad.
- [ ] `fallback_behavior=fail|ignore` ist vollständig und korrekt durchgesetzt.
- [ ] Kein leerer Candidate-Text-Bug im semantischen Pfad.
- [ ] Keine Random Tie Flips durch semantisches Reranking.

---

## 2.2 F1b Eval Delta

**Ziel:**
Der Nutzen des semantischen Rerankers wird gegen die BM25-Baseline messbar gemacht.

### Deliverables
- [ ] `lenskit eval` kann Baseline und Semantic-Modus vergleichend ausführen.
- [ ] Output enthält getrennt:
  - [ ] `recall@k` baseline
  - [ ] `recall@k` semantic
  - [ ] `MRR` baseline
  - [ ] `MRR` semantic
  - [ ] `delta_recall`
  - [ ] `delta_mrr`
- [ ] Per-Query Vergleich ist sichtbar.
- [ ] Failure-Fälle werden explizit ausgewiesen.
- [ ] Deterministischer Test mit Mock-Reranker existiert.

### Nicht-Ziele
- [ ] Kein Dashboarding.
- [ ] Keine komplexe CI-Metrikplattform.
- [ ] Keine Modellbenchmark-Matrix über viele Modelle.

### Stop-Kriterien
- [ ] Improvement-Delta ist maschinenlesbar nachweisbar.
- [ ] Semantik verursacht keine neue Failure-Klasse gegenüber der Baseline.
- [ ] Eval bleibt ohne Netzwerk und ohne fragile Echtmodell-Abhängigkeit testbar.

---

## 2.3 Range_ref Propagation

**Ziel:**
Die bereits vorhandene `range_ref`-Mechanik wird generatorseitig bis auf Bundle-/Byte-Ebene sauber propagiert.

**Wichtig:**
Dies ist keine Neuerfindung von `range_ref`, sondern die Vervollständigung der Provenienzspur.

### Bereits vorhanden
- [x] Query-seitige `range_ref`-Emission ist grundsätzlich möglich.
- [x] Roundtrip-/Resolver-Grundlage existiert.

### Noch offen
- [ ] Generator-/Bundle-seitige Propagation der Herkunft ist vollständig.
- [ ] Chunk-Artefakte tragen verlässliche Herkunftsfelder aus der Erzeugung.
- [ ] Byte-Mapping in generierten Bundle-Artefakten ist sauber nachvollziehbar.

### Deliverables
- [ ] Generator erweitert Herkunftsmetadaten um:
  - [ ] `source_file`
  - [ ] `start_byte`
  - [ ] `end_byte`
  - [ ] `content_sha256`
- [ ] Query-Resultate können daraus konsistente, verifizierbare `range_ref`-Objekte ableiten.
- [ ] Bundle-gegen-Resolver-Roundtrip ist reproduzierbar testbar.

### Stop-Kriterien
- [ ] `range_ref` zeigt exakt und verifizierbar auf Bundle-Bytes.
- [ ] Treffer sind nicht nur plausibel, sondern artefaktisch belegbar.

---

## 2.4 Graph Index Artifact Completion

**Ziel:**
Graph-bezogene Informationen werden als reproduzierbares Artefakt bereitgestellt und mit bestehender Retrieval-/Explain-Logik konsistent gehalten.

### Deliverables
- [ ] `graph_index.json` wird reproduzierbar erzeugt.
- [ ] Das Artefakt enthält mindestens:
  - [ ] Nodes
  - [ ] Edges
  - [ ] Entrypoints
  - [ ] Distance Map
  - [ ] Metriken
- [ ] Bundle-/Artefakt-Einbindung ist konsistent.
- [ ] Explain-/Rerank-seitige Nutzung widerspricht dem Artefakt nicht.
- [ ] Tests decken Determinismus und Fallback ab.

### Nicht-Ziele
- [ ] Kein weiterer Ausbau zu einem vollständigen Call-Graph.
- [ ] Keine neue Graph-Architektur jenseits des aktuellen Retrieval-Nutzens.

### Stop-Kriterien
- [ ] `graph_index.json` ist stabil, deterministisch und valide.
- [ ] Bestehende graph-aware Features und Explain-Daten sind artefaktkonsistent.
- [ ] Kein Widerspruch zwischen Dokumentation, Artefakt und Retrieval-Verhalten.

---

## 3. Empfohlene Reihenfolge

Diese Reihenfolge ist verbindlich, solange keine neue technische Blockade sichtbar wird.

- [ ] Schritt 1: F1b Semantic Reranker Runtime abschließen
- [ ] Schritt 2: F1b Eval Delta abschließen
- [ ] Schritt 3: Range_ref Propagation abschließen
- [ ] Schritt 4: Graph Index Artifact Completion abschließen

**Begründung:**
Zuerst den lokalen semantischen Wertpfad stabilisieren, dann messen, dann Provenienz vervollständigen, dann Graph-Artefakt sauber konsolidieren.

---

## 4. Spätere Phasen (deferred, nicht aktiv)

Diese Phasen bleiben relevant, sind aber aktuell nicht operative Arbeit.

### P3 Contracts / Flows Atlas
- [ ] `contracts_graph.json`
- [ ] Dependency topology / schema flow tracing
- [ ] CI-/Drift-Regeln für Contract-Flüsse

### P4 Tree-sitter / Symbol Index
- [ ] sprachagnostische AST-Extraktion
- [ ] `symbol_index.json`
- [ ] Multi-Lang Parsing

### P5 Call Graph / CPG
- [ ] `call_graph.json`
- [ ] Execution Flow Retrieval
- [ ] Security / behavior reasoning auf höherer Strukturebene

---

## 5. Offene Architekturfragen

Diese Fragen blockieren die aktiven Punkte nicht zwingend, müssen aber vor späteren Phasen geklärt werden.

### Contracts-Pfad
- [ ] Kanonischen Ablageort für Retrieval-Schemas festlegen:
  - [ ] `contracts/`
  - [ ] `schemas/`
  - [ ] `retrieval/schemas/`

### Schema-Discovery
- [ ] Konvention festlegen:
  - [ ] `*.schema.json`
  - [ ] `*.json`
- [ ] Validator-Discovery dokumentieren.

### Artifact Role Naming
- [ ] Kanonische Benennung festlegen:
  - [ ] `graph_index_json`
  - [ ] `architecture_graph_json`
- [ ] Regeln für Kopplung zwischen Rolle, Contract-ID und Artefaktname festlegen.

### Chunk Index Erweiterbarkeit
- [ ] Prüfen, ob zusätzliche Felder schema-kompatibel integrierbar sind:
  - [ ] `symbol_name`
  - [ ] `node_id`
  - [ ] `entrypoint_distance`
  - [ ] `is_test_penalty`

---

## 6. Risiken und Leitplanken

### Technische Risiken
- [ ] Speicherwachstum durch lokale Embeddings kontrollieren.
- [ ] Keine fragile Testabhängigkeit von echten ML-Modellen in CI.
- [ ] Keine implizite NumPy-/Torch-Pflicht im Basispfad.

### Qualitätsrisiken
- [ ] Semantische Verbesserung nur mit Baseline-Vergleich behaupten.
- [ ] Explain-Blöcke müssen semantische und lexikalische Anteile sauber trennen.
- [ ] Keine stille Verschlechterung lexikalischer Trefferqualität.

### Architekturrisiken
- [ ] Keine vorschnelle Cross-Repo-Kopplung zu semantAH.
- [ ] Keine Artefakt-Drift zwischen Query-Logik, Eval und Bundle-Output.
- [ ] Kein Dokumentationsdrift zwischen Roadmap und tatsächlichem Stand.

---

## 7. Definition of Done für aktive PRs

Ein aktiver Schritt gilt erst dann als abgeschlossen, wenn alle vier Bedingungen erfüllt sind:

- [ ] Implementierung vorhanden
- [ ] Tests vorhanden und stabil
- [ ] Explain-/Diagnostics-Verhalten dokumentiert
- [ ] Stop-Kriterium explizit erfüllt

---

## 8. Strategischer Erweiterungspfad

Nach Abschluss der aktiven Arbeit kann Lenskit erweitert werden, ohne den Kern umzubauen.

### SemantAH-ready, aber nicht semantAH-abhängig
- [ ] Provider-Abstraktion später vorbereiten
- [ ] möglicher Adapterpfad: `provider=semantah_http`
- [ ] keine produktive Auslagerung vor Abschluss der lokalen F1b-Kette

---

## 9. Kurz-Essenz

Der nächste sinnvolle Ausbaupfad ist:

- [ ] lokaler semantischer Reranker sauber fertig
- [ ] Nutzen per Eval-Delta belegen
- [ ] Provenienz (`range_ref`) generatorseitig vervollständigen
- [ ] Graph-Artefakt stabil konsolidieren

Alles andere ist später.