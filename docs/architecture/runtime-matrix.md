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
| **`service.app` (API Backend)** | `index.sqlite` (via Runner Jobs), UI Files | HTTP JSON Responses, static UI; Runtime-Artefakte `query_trace`, `context_bundle`, `agent_query_session` im `QueryArtifactStore` | Ja (für Job Management) | API Contracts (Pydantic Models) | Job Cancel/Fail Status. HTTP 404, 500. | Explizit. API gibt `JobResponse` mit Log-Referenz zurück. |
| **`cli.cmd_query` (CLI)** | `index.sqlite`, Query Args | stdout/JSON, optionale Projektionen (`query_trace.json`, `query_context_bundle.json`) | Nein | Wandelt Result in CLI Formate um. | Output Profile Fallbacks (z.B. Context Window ignorieren wenn Mode nicht `window`). | Explizit. |

## API Endpoint Storage Matrix

Welche Artefakte werden pro Endpunkt gespeichert und unter welcher Bedingung:

| Endpunkt | `query_trace` gespeichert | `context_bundle` gespeichert | `agent_query_session` gespeichert | `artifact_refs.query_trace_id` |
| :--- | :--- | :--- | :--- | :--- |
| `/api/query` | Ja, bei `trace=true` und konfiguriertem `QueryArtifactStore` | Ja, wenn ein Context Bundle im Ergebnis vorhanden ist und (`trace=true` oder `build_context_bundle=true`) bei konfiguriertem `QueryArtifactStore` | Ja, wenn `trace=true`, ein Context Bundle (wrapper-form) vorhanden ist, die Session gebaut wird und `QueryArtifactStore` konfiguriert ist | Entspricht `artifact_ids.query_trace`, wenn gespeichert |
| `/api/federation/query` | **Nein** (kein standalone Federation Query Trace) | Ja, wenn ein Context Bundle im Ergebnis vorhanden ist und (`trace=true` oder `build_context_bundle=true`) bei konfiguriertem `QueryArtifactStore` | Ja, wenn `trace=true`, ein Context Bundle vorhanden ist, die Session gebaut wird und `QueryArtifactStore` konfiguriert ist | **Immer null** (kein standalone trace) |
| `/api/artifact_lookup` | — (Lookup-Endpunkt, kein Speichern) | — | Löst `agent_query_session` per `artifact_ids.agent_query_session` auf | — |

Hinweis: `artifact_refs.agent_query_session_id` ist **immer null** in gespeichertem Payload und Response (Zirkel-Self-ID). Die Store-ID ist ausschließlich über `artifact_ids.agent_query_session` im API-Response-Toplevel zugänglich. `trace=true` allein garantiert kein gespeichertes `context_bundle`, wenn kein Context Bundle im Ergebnis vorhanden ist. Persistenz setzt in allen Fällen einen konfigurierten `QueryArtifactStore` voraus.

## Bemerkungen zur Runtime

1.  **Graph Loader (`load_graph_index`):**
    Nutzt eine Fail-Closed Validierung: Schlägt Schema-Check, JSON-Format oder Staleness-Check fehl, crasht das Programm nicht, sondern markiert das Signal mit `graph_used = False` und dem jeweiligen `graph_status` (`not_found`, `invalid_schema` etc.). Der Ranker läuft daraufhin mit der Baseline weiter. Dieses Verhalten wird im Explain über `graph_used` und `graph_status` signalisiert.
2.  **Context Builder (`query_core`):**
    Trennt zwischen "Hit" (Ranking-Modell), "Evidence" (Matched Chunk/Snippet) und "Context" (Surrounding, Graph-Neighbors).
3.  **Output Profiles:**
    Output-Profile (z.B. `agent_minimal`, `ui_navigation`, `human_review`) verändern nicht das zugrunde liegende Ranking, sondern filtern die Projektion (Reduktionslogik in `query_core`).

## Bekannte Lücken (Runtime Matrix)

-   **Phase 5 (Cross-Repo-Föderation):** `federation_index.json` und föderierte Queries (`/api/federation/query`) sind implementiert (minimale Multi-Bundle-Aggregation). `federation_conflicts.json` ist heuristisch/minimal implementiert: Runtime-Emission in `federation_query.py`, CLI-Persistenz in `cmd_federation.py`, schema-validiert per `test_federation_cli.py`; offen bleibt eine belastbare Identity-Engine jenseits einfacher Heuristiken. `cross_repo_links.json` wird als minimaler Co-Occurrence-Output emittiert (nur gemeinsame Query-Präsenz in finalen Ergebnissen) und per CLI `--trace` persistiert. Offen: vollständige föderierte Ranking-Semantik und weitergehende, explizit getrennte Identity-Logik.
-   **Agent Control Surface (Phase 6):** `agent_query_session` Provenienz-Härtung und `/api/artifact_lookup`-Roundtrip sind belegt. Offen: Agent-Orchestrierung, Feedback-Schleifen, MCP-Anbindung.

### Runtime-Artefakt-Lebensdauer (Lifecycle Metadata v1)

Runtime-Artefakte (`query_trace`, `context_bundle`, `agent_query_session`) tragen aktuell folgende Lifecycle-Felder:

| Feld | Wert |
| :--- | :--- |
| `retention_policy` | `"unbounded_currently"` |
| `lifecycle_status` | `"active"` |
| `expires_at` | `null` |

**Noch kein GC. Noch keine TTL. Noch keine automatische Löschung.**
Lifecycle-Felder sind Vorarbeit für spätere Retention-, MCP- und Agent-Orchestrierungslogik.
