# Lenskit Runtime-Matrix

Diese Matrix dokumentiert den tatsächlichen, aktuellen Implementierungsstand im Repository (`merger/lenskit/`). Sie erfasst, welche Module welche Artefakte aufnehmen, verarbeiten, ausgeben, und welche Fallback-Pfade oder Fehlerbehandlungsmechanismen existieren.

| Modul (Prozess) | Liest (Artefakt / Daten) | Schreibt (Artefakt / Output) | Manifest-Nutzung | Contract-Nutzung | Fallback / Fehlertyp | Stiller oder expliziter Fehler |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`core.merge` (Ingestion)** | Repository Dateisystem, Profilkonfigurationen | `canonical_md`, `dump_index.json`, `index_sidecar.json`, `.index.sqlite` | Ja (Baut `index_sidecar.json`) | Validiert Rollen gegen Constants. | CWD-Fallback (bei absolutem CWD-Mode). | Explizit. Fehler in der Extraktion (z.B. ParseError) werden geloggt, aber fortgesetzt. |
| **`retrieval.index_db` (DB Build)** | `chunk_index.jsonl`, `dump_index.json` | `index.sqlite` | Nein | Minimal (DB Schema) | Keine. Bricht bei defekten Chunks/JSONL ab. | Explizit. |
| **`architecture.graph_index`** | `architecture_graph.json` | `graph_index.json` (bzw. Dictionary-Memory) | Nein | Valides Schema (`architecture.graph_index.v1.schema.json`) | Status-Codes: `not_found`, `invalid_schema`, `invalid_json`, `stale_or_mismatched` | **Explizit (Status im Explain).** |
| **`retrieval.query_core` (Ranking)** | `index.sqlite`, `graph_index.json`, User Query | `query-result.v1.schema.json` compliant Dict, `query_context_bundle.json` | Nein (Direkt DB) | Output Profiling (Context Bundle) | FTS5 Query Expansion Fallback (OR). Graph Fallback (Status Flag). | Explizit. Stiller Fallback bei lexikalischem Token-Mangel, aber markiert im Explain. |
| **`retrieval.eval_core` (Eval)** | `index.sqlite`, `graph_index.json`, `eval_queries.md` | `retrieval_eval.json` (Metrik Report) | Nein | Output Validierung (`retrieval-eval.v1.schema.json`) | Graph Missing (Baseline wird evaluiert, Graph Skip). | Explizit. Deltas werden in Metriken gezeigt (`baseline_mrr` vs `graph_mrr`). |
| **`core.range_resolver`** | `.index.sqlite` (oder File System), `range_ref` | Snippets (Resolved Code) | Indirekt (Nutzt `.index.sqlite`) | Prüft `range-ref.v1.schema.json` Attribute | Source-Backed-Fallback (`derived_range_ref`) wenn Bundle-Backed fehlschlägt. | Explizit (Provenance Type wechselt). |
| **`service.app` (API Backend)** | `index.sqlite` (via Runner Jobs), UI Files | HTTP JSON Responses, static UI | Ja (für Job Management) | API Contracts (Pydantic Models) | Job Cancel/Fail Status. HTTP 404, 500. | Explizit. API gibt `JobResponse` mit Log-Referenz zurück. |
| **`cli.cmd_query` (CLI)** | `index.sqlite`, Query Args | stdout/JSON, Context Bundle (`query_trace`) | Nein | Wandelt Result in CLI Formate um. | Output Profile Fallbacks (z.B. Context Window ignorieren wenn Mode nicht `window`). | Explizit. |

## Bemerkungen zur Runtime

1.  **Graph Loader (`load_graph_index`):**
    Nutzt eine Fail-Closed Validierung: Schlägt Schema-Check, JSON-Format oder Staleness-Check fehl, crasht das Programm nicht, sondern markiert das Signal mit `graph_used = False` und dem jeweiligen `graph_status` (`not_found`, `invalid_schema` etc.). Der Ranker läuft daraufhin mit der Baseline weiter. Dieses Verhalten wird im Explain über `graph_used` und `graph_status` signalisiert.
2.  **Context Builder (`query_core`):**
    Trennt zwischen "Hit" (Ranking-Modell), "Evidence" (Matched Chunk/Snippet) und "Context" (Surrounding, Graph-Neighbors).
3.  **Output Profiles:**
    Output-Profile (z.B. `agent_minimal`, `ui_navigation`, `human_review`) verändern nicht das zugrunde liegende Ranking, sondern filtern die Projektion (Reduktionslogik in `query_core`).

## Bekannte Lücken (Runtime Matrix)

-   **Phase 5 (Cross-Repo-Föderation):** Föderierte Queries existieren nicht in der Runtime. Eine Query-Föderation (`federation_index`, `federated_query`) über mehrere Bundles hinweg ist nicht implementiert. Die Runtime ist isoliert pro Repository/Bundle.