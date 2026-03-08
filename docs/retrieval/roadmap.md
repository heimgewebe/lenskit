# Lenskit Retrieval Roadmap

## Dialektische Einordnung

### These
Eine Restliste soll operative Klarheit schaffen: Welche PR kommt als nächstes, mit welchem Stop-Kriterium, anhand welcher Artefakte prüfbar.

### Antithese
Die aktuelle Liste mischt drei Kategorien:
1. reale Implementationsarbeit
2. strategische Phasen
3. offene Architekturfragen

Das erzeugt ein klassisches Planungsproblem: Agents beginnen plötzlich „Fragen“ zu implementieren.

### Synthese
Eine ideale Restliste trennt strikt:
- **ACTIVE WORK**
- **DEFERRED WORK**
- **ARCHITECTURE QUESTIONS**

Damit wird die Roadmap operational statt narrativ.

---

## Statusgrundlage (Dump)

Das Bundle enthält aktuell u. a.:
- canonical dump
- chunk index
- dump index
- derived index
- sqlite BM25 index
- architecture summary

Die Architekturübersicht bestätigt die Module:
- chunker
- merge
- extractor
- range_resolver

Wichtige Artefakte fehlen dagegen:
- `graph_index.json`
- `embedding_index`
- `symbol_index`
- `call_graph`

---

## REST-LISTE (OPERATIV)

### A — Retrieval Evolution (AKTIVE ARBEIT)

#### F1b Semantic Reranker (Model Integration)
**Ziel:** Semantisches Ranking als zweite Retrievalphase.

**Pipeline:**
`BM25 → candidate set → semantic rerank → final ranking`

**Scope:**
- provider: local
- model: sentence-transformers
- metric: cosine similarity
- dependency: optional

**Implementationsaufgaben:**

**1️⃣ Model Loader**
- Datei: `merger/lenskit/retrieval/semantic.py`
- Funktionen:
  - `load_model()`
  - `embed_query()`
  - `embed_chunks()`

**2️⃣ Embedding Cache**
- Ziel: keine Embedding-Neuberechnung pro Query
- Artefakt: `embedding_index.json`
- Struktur:
  ```json
  {
    "chunk_id": "...",
    "embedding": [...]
  }
  ```

**3️⃣ Semantic Rerank**
- Pipeline:
  - `candidates = bm25_top_k(query)`
  - `reranked = cosine_similarity(query_embedding, chunk_embeddings)`

**4️⃣ Integration Retrieval Pipeline**
- Datei: `retrieval/query.py`
- Feature Flag: `semantic_rerank_enabled`
- Fallback: BM25 only

**Stop-Kriterien:**
- measurable improvement vs BM25
- keine neue Failure-Klasse
- deterministisches Ranking
- Pipeline fallback stabil

---

### B — Generator Improvements

#### PR: Range_ref bundle propagation

**Aktueller Zustand:** Range refs existieren nur im Retrieval-Layer.
**Fehlt:** bundle-level provenance tracking
**Problem:** Bundles verlieren Byte-Mapping.

**Ziel:** Chunk-Artefakte behalten Herkunft.
```text
bundle
 └ source_file
     └ start_byte
     └ end_byte
```

**Änderung:**
- Datei: `generate_chunk_artifacts()`
- Neue Felder: `source_file`, `start_byte`, `end_byte`, `content_sha256`

**Stop-Kriterium:**
- Query result enthält: `range_ref`, das exakt auf Bundle-Bytes zeigt.

---

### C — Index Erweiterungen

#### Graph Index Artifact
**Fehlt derzeit im Bundle.**

**Ziel:** `graph_index.json`
**Struktur:**
```json
{
  "nodes": [],
  "edges": [],
  "entrypoints": [],
  "distance_map": {}
}
```

**Nutzen (Reranking Features):**
- distance_to_entrypoint
- test_penalty
- dependency_score

**Generator:**
- Datei: `scripts/graph/build_graph_index.py`

**Stop-Kriterium:**
- Bundle enthält: `graph_index.json`

---

## DEFERRED PHASES (NICHT AKTIV)

### P3 — Contracts / Flows Atlas
- **Artefakt:** `contracts_graph.json`
- **Nutzen:** dependency topology, schema flow tracing

### P4 — Tree-sitter Parsing
- **Ziel:** language agnostic AST extraction
- **Artefakt:** `symbol_index.json`

### P5 — Call Graph / CPG
- **Artefakt:** `call_graph.json`
- **Nutzen:** execution flow retrieval, security reasoning

---

## ARCHITEKTURFRAGEN (NOCH NICHT IMPLEMENTIEREN)

**Contracts Pfad**
- **Frage:** Wo liegen retrieval schemas?
- **Optionen:** `contracts/`, `schemas/`, `retrieval/schemas/`

**Schema Discovery**
- **Frage:** `*.schema.json` vs `*.json`

**Artifact Role Naming**
- **Frage:** `architecture_graph_json` vs `graph_index_json`

**Chunk Index Erweiterung**
- **Neue Felder:** `symbol_name`, `node_id`, `test_penalty`
- **Risiko:** Schema strictness.

---

## Empfohlene PR-Reihenfolge

- **PR 6:** Semantic Reranker (F1b)
- **PR 7:** Range-ref propagation
- **PR 8:** Graph Index artifact
- **Danach:** P3 → P4 → P5

---

## Risikoanalyse

**Technisch**
- *Embedding Integration:* Risiko memory growth, index size

**Architektur**
- *Range_ref Tracking:* Risiko generator refactor

**Organisatorisch**
- *Graph Index:* Risiko Reranker coupling

---

## Alternative Denkachse

Statt Roadmap-Tasks: **Artefakt-Gap-Analyse**

**Sollte existieren:**
- `graph_index.json`
- `symbol_index.json`
- `call_graph.json`
- `embedding_index.json`

**Existiert:**
- `chunk_index`
- `sqlite_index`

**Differenz = nächste PRs.**

---

**Unsicherheitsgrad:** 0.16
*Grund:*
- Codepipeline nicht komplett sichtbar
- Graph-Rerank evtl runtime-only

**Interpolationsgrad:** 0.14
*Annahmen:*
- typische Retrieval Architektur
- Embedding Cache Design

---

## Essenz

Die ideale Restliste besteht aus nur drei echten Arbeiten:
1. **PR6** semantic reranker
2. **PR7** range_ref propagation
3. **PR8** graph_index artifact

Alles andere ist Future Phase oder Architecture Question.

*Zum Schluss eine kleine Beobachtung aus der Praxis: Die meisten Software-Roadmaps scheitern nicht an fehlendem Code – sondern daran, dass niemand mehr weiß, welche Kästchen eigentlich noch echt sind.*