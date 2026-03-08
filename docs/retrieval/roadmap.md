# Lenskit Retrieval Roadmap

## Zweck und Zielbild

Dieses Dokument ist das kanonische Steuerdokument für die Retrieval-Architektur in Lenskit. Es definiert die Entwicklungsrichtung, grenzt aktive Arbeitspakete von künftigen Phasen ab und legt klare Stop-Kriterien fest.

**Zielbild:**
Lenskit operiert als deterministisches Retrieval-System mit einer robusten lexikalischen Basis (BM25/FTS) und einer optionalen semantischen Zweitphase. Zentral sind dabei nachvollziehbare Provenienz, maschinenlesbare Explain-Blöcke und reproduzierbares Evaluierungsverhalten. Lenskit bleibt primär lokal und robust ("Lenskit-first"); Backend-Auslagerungen (wie an semantAH) sind spätere, kompatible Erweiterungspfade ("semantAH-ready").

---

## Aktive Arbeit

### 1. F1b Semantic Reranker Runtime

**Ziel:**
Einführung eines lokalen semantischen Rankings als optionale zweite Retrievalphase auf Basis der BM25-Kandidaten.

**Deliverables:**
- Model Loader (`merger/lenskit/retrieval/semantic.py`) für lokales `sentence-transformers` Setup.
- Embedding Cache (`embedding_index.json`) zur Vermeidung von Neuberechnungen pro Query.
- Integration in `retrieval/query.py`: `candidates = bm25_top_k(query) → reranked = cosine_similarity`.
- Explain-/Diagnostics-Pfad für semantische Scores und Fallbacks.

**Nicht-Ziel:**
- Produktivverdrahtung mit semantAH.
- Multi-provider Orchestrierung.
- Vollausbau der Dimensions-Validierung.
- Schaffung neuer großer Artefaktfamilien ohne unmittelbaren Reranking-Nutzen.

**Stop-Kriterium:**
- Semantischer Reranker läuft lokal mit deterministischem Verhalten.
- Saubere Fallbacks bei fehlender (optionaler) Dependency greifen ohne neue Failure-Klasse.

### 2. F1b Eval Delta

**Ziel:**
Erweiterung der Evaluierung zur Messbarmachung der Reranker-Qualität.

**Deliverables:**
- Vergleichsmodus für `lenskit eval` (baseline: BM25-only vs. semantic: BM25 + semantic rerank).
- Metriken-Output: `recall@k` (baseline/semantic), `MRR` (baseline/semantic), `delta_recall`, `delta_mrr`.
- Testfall mit deterministischem Mock-Reranker.

**Nicht-Ziel:**
- Komplexe CI/CD Integration oder Dashboarding.

**Stop-Kriterium:**
- Messbare Verbesserung (`delta_mrr > 0` oder `delta_recall@k > 0`) gegen die Baseline ist nachweisbar.

### 3. Range_ref Propagation

**Ziel:**
Chunk-Artefakte behalten ihre exakte Herkunft auf Bundle-Ebene (Byte-Mapping).

**Deliverables:**
- Erweiterung von `generate_chunk_artifacts()` um `source_file`, `start_byte`, `end_byte` und `content_sha256`.

**Nicht-Ziel:**
- Komplettes Refactoring der Dump-Architektur.

**Stop-Kriterium:**
- Query-Resultate enthalten eine `range_ref`, die exakt und verifizierbar auf die Bundle-Bytes zeigt.

### 4. Graph Index Artifact

**Ziel:**
Bereitstellung topologischer Metadaten für zukünftige Reranking-Features (z. B. Distanz zu Entrypoints).

**Deliverables:**
- Generator-Script (`scripts/graph/build_graph_index.py`).
- JSON-Artefakt `graph_index.json` mit Nodes, Edges, Entrypoints und Distance-Map.

**Nicht-Ziel:**
- Sofortige Integration in die Query-Scoring-Logik (Reranking auf Basis des Graphen folgt später).

**Stop-Kriterium:**
- Das Bundle enthält reproduzierbar eine valide `graph_index.json`.

---

## Spätere Phasen (Deferred Phases)

Diese Phasen sind architektonisch relevant, aber aktuell nicht in der Umsetzung.

- **P3 — Contracts / Flows Atlas:** Generierung von `contracts_graph.json` für Dependency Topology und Schema Flow Tracing.
- **P4 — Tree-sitter Parsing:** Sprachagnostische AST-Extraktion für einen `symbol_index.json`.
- **P5 — Call Graph / CPG:** Generierung von `call_graph.json` für Execution Flow Retrieval und Security Reasoning.

---

## Offene Architekturfragen

Diese Fragen müssen vor dem Beginn der späteren Phasen geklärt werden, blockieren aber die aktive Arbeit nicht.

- **Contracts Pfad:** Wo liegen Retrieval-Schemas dauerhaft (`contracts/`, `schemas/`, oder `retrieval/schemas/`)?
- **Schema Discovery:** Welche Dateinamenskonvention (`*.schema.json` vs. `*.json`) wird vom Validator genutzt?
- **Artifact Role Naming:** Wie wird die Namenskonvention zwischen `architecture_graph_json` und `graph_index_json` konsolidiert?
- **Chunk Index Erweiterung:** Sind neue Felder wie `symbol_name` oder `node_id` schema-kompatibel (Strict-Type Checks)?

---

## Empfohlene Reihenfolge

Die Umsetzung der aktiven Arbeit erfolgt thematisch:
1. F1b runtime (Lokaler Reranker)
2. F1b eval (Delta-Messung)
3. range_ref propagation
4. graph_index artifact

*Backend-Auslagerungen (z. B. semantAH-Adapter) oder verteilte Architekturen sind spätere, kompatible Erweiterungspfade, die erst nach Abschluss dieser Kette evaluiert werden.*

---

## Risiken und Leitplanken

- **Embedding Integration:** Speicherwachstum (Memory Growth) und Indexgröße müssen beim lokalen Reranking kontrolliert bleiben.
- **Test-Stabilität:** Echte ML-Modelle in der CI sind zu vermeiden; stattdessen auf deterministische Mocks setzen.
- **Qualitätssicherung:** Semantische Scores dürfen ohne Baseline-Vergleich (Eval Delta) nicht als "Verbesserung" deklariert werden.
- **Architektur-Drift:** Modellwechsel ohne explizite Revisionsverwaltung zerstören die zeitliche Vergleichbarkeit der Retrieval-Güte.