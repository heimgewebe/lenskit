# Lenskit Retrieval Roadmap

Dieses Dokument ist das kanonische Steuerdokument für die Retrieval-Architektur in Lenskit. Es trennt abgeschlossene Grundlagen, aktive Arbeit, spätere Phasen und offene Architekturfragen. Jede aktive Einheit ist abhakbar und mit klaren Stop-Kriterien versehen.

**Statusübersicht:**
- **Basis abgeschlossen:** Lexikalisches Retrieval (BM25/FTS), Navigation, Range-/Provenienz-Basis, Explain/Eval-Grundlagen.
- **Aktive Arbeitspakete:** 1. F1b Runtime, 2. F1b Eval Delta, 3. Range_ref Propagation, 4. Graph Index Artifact + Runtime Consistency.
- **Spätere Phasen:** P3 (Contracts Atlas), P4 (Symbol Index), P5 (Call Graph).

---

## 0. Zielbild

Lenskit soll ein deterministisches Retrieval-System mit robuster lexikalischer Basis (BM25/FTS) und optionaler semantischer Zweitphase sein.
Leitplanken: deterministische Artefakte, nachvollziehbare Provenienz, maschinenlesbare Explain-Blöcke, reproduzierbares Eval-Verhalten. (Lenskit-first, semantAH-ready).

---

## 1. Abgeschlossene Grundlagen

Diese Punkte gelten als vorhanden und bilden das stabile Fundament für die weitere operative Arbeit.

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

### D. Semantik-Plumbing (F1a)
- [x] Semantic Request Marker, Candidate Overfetch und Diagnostics sind abgeschlossen.
- [x] CLI-/Policy-Wiring (`fallback_behavior=fail|ignore`) ist aktiv.

---

## 2. Aktive Arbeit

Nur diese vier Pakete definieren die aktuelle operative Weiterentwicklung. *Ein Arbeitsschritt gilt erst als abgeschlossen, wenn Implementierung, Tests, Explain-Dokumentation und das Stop-Kriterium erfüllt sind.*

### 2.1 F1b Semantic Reranker Runtime

**Ziel:**
Ein lokaler semantischer Reranker ergänzt den BM25-Kandidatenpfad optional als zweite Phase.
`BM25/FTS -> candidate set -> semantic rerank -> final ranking`

**Deliverables:**
- [ ] Lokaler semantischer Modellzugang ist integriert.
- [ ] Optional Dependency Pfad ist sauber dokumentiert.
- [ ] Nur unterstützte Konfigurationen (`provider=local`, `similarity_metric=cosine`) werden akzeptiert; Rest liefert Fehler/Fallback.
- [ ] Candidate-Texte für semantisches Reranking werden korrekt aus dem SQL-Pfad bezogen.
- [ ] Semantische Scores werden deterministisch in `final_score` überführt.
- [ ] Explain-/Diagnostics-Payload zeigt semantische Beteiligung an.

**Nicht-Ziele:**
- Keine Produktivverdrahtung mit semantAH.
- Keine Multi-Provider-Orchestrierung.

**Stop-Kriterien:**
- [ ] Lokaler semantischer Reranker läuft deterministisch.
- [ ] Fehlende optionale Dependency erzeugt keine neue Failure-Klasse im Basispfad.
- [ ] Kein leerer Candidate-Text-Bug im semantischen Pfad.

### 2.2 F1b Eval Delta

**Ziel:**
Der Nutzen des semantischen Rerankers wird gegen die BM25-Baseline messbar gemacht.

**Deliverables:**
- [x] `lenskit eval` führt Baseline und Semantic-Modus vergleichend aus.
- [x] Output enthält getrennt: `recall@k` (baseline/semantic), `MRR` (baseline/semantic), `delta_recall`, `delta_mrr`.
- [x] Per-Query Vergleich ist sichtbar; Failure-Fälle werden explizit ausgewiesen.
- [x] Deterministischer Test mit Mock-Reranker existiert.

**Stop-Kriterien:**
- [x] Improvement-Delta (`delta_mrr > 0` oder `delta_recall@k > 0`) ist maschinenlesbar nachweisbar.
- [x] Semantik verursacht keine neue Failure-Klasse gegenüber der Baseline in der Evaluierung.

### 2.3 Range_ref Propagation

**Ziel:**
Die bereits vorhandene `range_ref`-Mechanik wird generatorseitig bis auf Bundle-/Byte-Ebene vollständig propagiert.

**Deliverables:**
- [ ] Generator erweitert Chunk-Metadaten um `source_file`, `start_byte`, `end_byte` und `content_sha256`.
- [ ] Query-Resultate können daraus konsistente, verifizierbare `range_ref`-Objekte ableiten.
- [ ] Bundle-gegen-Resolver-Roundtrip ist reproduzierbar testbar.

**Stop-Kriterien:**
- [ ] `range_ref` zeigt exakt und verifizierbar auf die generierten Bundle-Bytes.

### 2.4 Graph Index Artifact + Runtime Consistency

**Ziel:**
Topologische Metadaten (Graph) werden als reproduzierbares Artefakt erzeugt und die bestehende Rerank-/Explain-Logik wird darauf konsolidiert.

**Deliverables:**
- [ ] `graph_index.json` wird reproduzierbar erzeugt (Nodes, Edges, Entrypoints, Distance Map).
- [ ] Bundle-/Artefakt-Einbindung ist konsistent.
- [ ] Explain- und Rerank-seitige Nutzung (wie Distanz-Metriken oder Tie-Break-Stabilisierung) greifen konsistent auf dieses Artefakt zu.

**Stop-Kriterien:**
- [ ] `graph_index.json` ist stabil, deterministisch und valide im Bundle vorhanden.
- [ ] Bestehende graph-aware Features widersprechen dem Artefakt nicht.

---

## 3. Operative Abarbeitungsreihenfolge

Diese Reihenfolge ist operativ bindend:
1. [x] F1b Semantic Reranker Runtime
2. [x] F1b Eval Delta
3. [ ] Range_ref Propagation
4. [ ] Graph Index Artifact + Runtime Consistency

---

## 4. Spätere Phasen (deferred)

- **P3 Contracts / Flows Atlas:** `contracts_graph.json` (Dependency topology / schema flow tracing).
- **P4 Tree-sitter / Symbol Index:** Sprachagnostische AST-Extraktion für `symbol_index.json`.
- **P5 Call Graph / CPG:** `call_graph.json` für Execution Flow Retrieval.

---

## 5. Offene Architekturfragen

Diese Fragen blockieren die aktiven Punkte nicht, müssen aber für spätere Phasen geklärt werden:
- **Contracts-Pfad:** Kanonischer Ablageort für Schemas (`contracts/` vs. `retrieval/schemas/`).
- **Schema-Discovery:** Konvention für Validatoren (`*.schema.json` vs. `*.json`).
- **Artifact Role Naming:** Konsolidierung von `graph_index_json` und `architecture_graph_json`.
- **Chunk Index:** Schema-Kompatibilität neuer Metadatenfelder (`symbol_name`, `node_id`).

---

## 6. Risiken und Leitplanken

- **Technische Risiken:** Speicherwachstum durch lokale Embeddings muss kontrolliert bleiben; keine fragile Abhängigkeit von echten ML-Modellen in der CI.
- **Qualitätsrisiken:** Semantische Verbesserung darf nur mit Baseline-Vergleich behauptet werden; keine stille Verschlechterung lexikalischer Treffer.
- **Architekturrisiken:** Keine vorschnelle Produktivkopplung zu semantAH (Lenskit-first bleibt Maßgabe).
