# Lenskit Retrieval Roadmap

## Dialektische Einordnung

### These
Eine Restliste soll operative Klarheit schaffen: Welche PR kommt als nächstes, mit welchem Stop-Kriterium, anhand welcher Artefakte prüfbar. Das sinnvollste F1b-Upgrade ist ein kleines, lokales Lenskit-Upgrade mit optionaler semantischer Schicht. Die Roadmap definiert F1b als Model Integration mit lokalem Provider, Cosine-Ähnlichkeit, optionaler sentence-transformers-Abhängigkeit und noch nicht validierten dimensions.

### Antithese
Die aktuelle Liste mischt reale Implementationsarbeit, strategische Phasen und offene Architekturfragen. Man könnte F1b auch direkt an semantAH andocken, weil semantAH bereits einen Dienst für indexing and semantic search hat und Embeddings/Beobachtung sauber modelliert.

### Synthese
Eine ideale Restliste trennt strikt:
- **ACTIVE WORK**
- **DEFERRED WORK**
- **ARCHITECTURE QUESTIONS**

Implementiere F1b jetzt in Lenskit selbst (lokaler Reranker jetzt), aber so, dass ein späterer semantAH-Adapter trivial bleibt (Backend-Auslagerung später). Das ist der beste Kompromiss zwischen Fortschritt und Architekturhygiene. Damit wird die Roadmap operational statt narrativ.

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
**Ziel:** Semantisches Ranking als zweite Retrievalphase. Lenskit bleibt zuständig für BM25/FTS-Kandidaten, Filter, Explain-Block, deterministische Ergebnisform und Eval. F1b ergänzt ein optionales semantisches Reranking auf Top-K mit sauberen Fallbacks und messbarer Delta-Evaluation (keine neue Failure-Klasse im Basispfad).

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

## 3-Stufiges F1b-Upgrade

### Stufe 1 — Produktionsfähiger lokaler Semantic Reranker (PR A)
**Jetzt umsetzen.**
- **Was:** In `query_core.execute_query(...)`:
  1. BM25/FTS liefert `fetch_k = max(k, 50)` Kandidaten.
  2. Nur wenn `embedding_policy` (provider=local, similarity_metric=cosine) gesetzt ist: Candidate-Text aus SQL holen, Embeddings erzeugen, Cosine-Score berechnen, `final_score` deterministisch überschreiben.
- **Wie:** Optional dependency via `requirements-semantic.txt`.
- **Regeln:** SQL-Projektion sauber (kein leerer String-Bug), keine harte NumPy-Abhängigkeit im Basis-Setup, Konfigurationsgrenzen explizit validieren, Explain-Block konsistent ausbauen.

### Stufe 2 — Eval-Upgrade mit Improvement Delta (PR B)
**Direkt danach.**
- **Was:** `lenskit eval` bekommt einen Vergleichsmodus (baseline vs. semantic)
- **Output:** `recall@k` (baseline/semantic), `MRR` (baseline/semantic), `delta_recall`, `delta_mrr`, failed queries.
- **Stop-Kriterium:** `delta_mrr > 0` oder `delta_recall@k > 0`, keine neuen Failure-Klassen, saubere Fallbacks bei fehlender Dependency.

### Stufe 3 — Adapter-Vorbereitung für semantAH (PR C)
**Noch nicht jetzt produktiv verdrahten.**
- **Was:** `embedding_policy.provider` abstrahieren (`local` bleibt Default, `semantah_http` als Slot vorbereiten). Keine Cross-Repo-Kopplung für den F1b-Abschluss.

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

- **PR 6 / PR A:** F1b Runtime stabilisieren (Lokaler Reranker)
- **PR 6b / PR B:** Eval-Delta ergänzen
- **PR 7:** Range-ref propagation
- **PR 8:** Graph Index artifact
- **Danach:** semantAH Adapter (PR C), P3 → P4 → P5

---

## Risikoanalyse

**Technisch**
- *Embedding Integration:* Risiko memory growth, index size
- *Test-Risiko:* echte Modelle in CI machen alles langsam und fragil

**Architektur**
- *Range_ref Tracking:* Risiko generator refactor
- *Qualitätsrisiko:* semantische Scores ohne Baseline-Vergleich wirken klüger, ohne es zu sein

**Organisatorisch**
- *Graph Index:* Risiko Reranker coupling
- *Drift-Risiko:* Modellwechsel ohne sichtbare Revision erschwert Vergleich über Zeit

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
*Grund:* Codepipeline nicht komplett sichtbar, Graph-Rerank evtl runtime-only.

**Interpolationsgrad:** 0.19
*Annahmen:* Beste Upgrade-Reihenfolge abgeleitet aus Roadmap, semantAH-Rolle und PR-Mustern.

---

## Essenz

Die ideale Restliste besteht aus drei Kernarbeiten:
1. **PR6** semantic reranker (Lenskit-first: Runtime fertigbauen + separater Eval-Delta PR)
2. **PR7** range_ref propagation
3. **PR8** graph_index artifact

Alles andere ist Future Phase oder Architecture Question. Hebel: F1b lokal sauber fertigbauen, statt sofort systemübergreifend zu verknoten (Lenskit-first, semantAH-ready).
