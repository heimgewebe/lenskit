# Rest-Liste: Retrieval Upgrade Roadmap

Diese Liste enthält alle noch offenen Aufgaben aus der Retrieval Roadmap (`docs/retrieval/roadmap.md`) und der Upgrade Roadmap (`docs/retrieval/upgrade-roadmap.md`).

## Phase F: Semantik als Re-Ranker (aus roadmap.md)

- [ ] **F1b) Semantik Re-Ranker (Model Integration)**
  - [ ] Eval: improvement delta vs non-semantic.
  - [ ] Stop-Kriterium: Messbare Verbesserung (improvement delta) ohne neue Failure-Klasse.
  - [ ] F1b Implementation Scope: provider: local, similarity metric: cosine, optional dependency: sentence-transformers, dimensions currently not validated

## Empfohlene Reihenfolge (nächste Aktionen) (aus roadmap.md)

- [ ] F später

## PR 4: graph_index compile + graph-aware rerank (P2) (aus upgrade-roadmap.md)

**Deliverables:**
- [ ] `graph_index.json` (Adjacency + Entrypoint Distances + Metrics).

## PR 5: range_ref (Proof-Carrying Retrieval) (aus upgrade-roadmap.md)

- [ ] Tracking of source bytes into generated bundle artifacts inside `generate_chunk_artifacts` (requires deeper generator refactoring and is deferred to subsequent PRs).

## Weitere Phasen (P3-P5) (aus upgrade-roadmap.md)

- [ ] **P3** Contracts/Flows-Atlas (Alternative Achse) + CI/Drift Regeln
- [ ] **P4** Multi-Lang Parsing (Tree-sitter) + Symbol-Index v2
- [ ] **P5** Call-Graph/CPG v2 (S2)

## Offene Fragen zur Repository-Realität (Open Questions) (aus upgrade-roadmap.md)

- [ ] Klärung: Vertrags-Pfad: Wo liegt das offizielle `contracts/`-Verzeichnis für die neuen JSON-Schemas und wo sind die Validatoren angesiedelt?
- [ ] Klärung: Artefakt-Rollen: Entsprechen die neuen Artefakt-Rollen (wie `architecture_graph_json`) den etablierten Konventionen im `bundle.manifest.json`?
- [ ] Klärung: Erweiterung von Chunk Index: Sind Erweiterungen wie `symbol_name`, `node_id` und `is_test_penalty` im aktuellen `chunk_index.jsonl` Schema direkt integrierbar oder verletzen sie Strict-Type Checks?
- [ ] Klärung: Schema-Dateinamen/Discovery: `*.schema.json` vs `*.json` – how does the validator discover and version schemas?
