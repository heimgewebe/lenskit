# Retrieval Project Roadmap

Tracking the evolution of lenskit retrieval from basic artifacts to an intelligent "Retrieval OS".

## Vision
**Maximale "Agent-Readiness":** Ein maschinelles Retrieval- und Navigationssystem mit klaren Contracts, deterministischen Offsets, erklärbarer Suche und optionalem Semantik-Re-Ranking.

## Blueprint Status

### Phase 0: Invarianten & Zielmetriken
- [x] **Goal:** Reproducibility & Forensics
- [x] **Artifacts:**
    - `docs/retrieval/queries.md` (Gold Queries)
    - `dump_index.json` (Canonical Entry Point)
    - Deterministic chunk IDs (in `chunk_index.jsonl`)

### Phase 1: Artefakt-Schicht (Wahrheit + Navigation)
- [x] **Goal:** Agent can navigate without heuristics.
- [x] **Implemented:**
    - `chunk_index.jsonl` with deterministic fields.
    - `dump_index.json` linking all artifacts.
    - Reading Policy sentinels in MD and JSON.
    - JSON Sidecar with `features` list.

### Phase 2: Lexikalische Retrieval-Schicht (FTS)
- [x] **Goal:** Explainable, fast search.
- [x] **Implemented:**
    - **CLI:** `lenskit index` & `lenskit query`.
    - **Engine:** SQLite FTS5 (`chunks_fts` virtual table).
    - **Scoring:** `bm25` (standard, explainable).
    - **Docs:** `docs/retrieval/recipes.md`.
    - **Safety:** Stale index detection via hash linkage.
- [x] **Implemented:** Eval Runner (TTR/Recall measurement) via `lenskit eval`.

### Phase 3: Semantik als Re-Ranker (Future)
- [ ] **Goal:** Meaning over Keywords.
- [ ] **Plan:**
    - [ ] `embedding-policy.json` (Define what is embedded).
    - [ ] Local embedding generation (Top-K Re-ranking).
    - [ ] Hybrid Search (FTS + Vector).

### Phase 4: PR-Verstehen "auf Steroiden" (Future)
- [ ] **Goal:** Delta & Impact Analysis.
- [ ] **Plan:**
    - [ ] `symbol_index.json` (AST-based definition/reference graph).
    - [ ] `delta.json` schema refinement (linking changed chunks).
    - [ ] Graph navigation ("Find usages of changed symbol").

## Current Milestones
- **Status:** Phase 2 Implemented (v1), Eval pending.
- **Next Up:** Eval run (measure Recall@10 on Gold Queries) -> Decision on Phase 3.
