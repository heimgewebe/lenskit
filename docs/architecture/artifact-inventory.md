# Lenskit Artefakt-Inventar

Dieses Inventar dokumentiert die primären und abgeleiteten Artefakte von Lenskit, wie sie aktuell in `merger/lenskit/` implementiert und durch Verträge (Contracts) abgesichert sind.

| Artefaktname / Dateiname | Rolle (Konzept) | Erzeuger (Producer) | Verbraucher (Consumer) | Verbundenes Schema | Manifest Visibility | Runtime Usage |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `*.canonical.md` | `canonical_md` | `core.merge` | Mensch, LLMs (direkt), Bundle Manifest | - | Ja | Indirekt (als Bundle-Fallback) |
| `chunk_index.jsonl` | `chunk_index_jsonl` | `core.chunker` | `retrieval.index_db` | - | Ja | Index-Aufbau |
| `index.sqlite` | `chunk_index_sqlite` | `retrieval.index_db` | `retrieval.query_core`, `eval_core` | - | Ja (als `.index.sqlite`) | FTS5 Ranking, Chunk Retrieval |
| `dump_index.json` | `dump_index_json` | `core.merge` | `retrieval.index_db` | - | Ja | Initialer Index-Bau |
| `index_sidecar.json` | `index_sidecar_json` | `core.merge` | Agents, WebUI, CLI, Lenskit Service | `bundle-manifest.v1.schema.json` | Meta | Verknüpfung der Artefakte |
| `graph_index.json` | `graph_index_json` | `architecture.graph_index` | `retrieval.query_core`, `eval_core` | `architecture.graph_index.v1.schema.json` | Ja | Graph Penalty/Bonus, Semantic Eval |
| `architecture_graph.json`| `artifact_graph_json` | `architecture.import_graph` | `architecture.graph_index` | `architecture.graph.v1.schema.json` | Ja | Erzeugung des Index |
| `query_context_bundle.json`| `query_context_bundle.json` | `retrieval.query_core` | CLI, WebUI, Agents | `query-context-bundle.v1.schema.json` | Nein (Runtime Output) | Context Expansion, UI Display |
| `query_trace.json` | `query_trace.json` | `retrieval.query_core` | Debug CLI, Evaluatoren | Teil von `query-result.v1.schema.json` | Nein (Runtime Output) | Ranking-Analyse (via `--trace`) |
| `retrieval_eval.json` | `eval_report` | `retrieval.eval_core` | CI, Entwickler | `retrieval-eval.v1.schema.json` | Nein | Evaluierungsmetriken |
| `pr-schau-delta.json` | `pr_schau_delta` | `core.pr_schau_bundle` | PR-Schau Frontends, Agents | `pr-schau-delta.v1.schema.json` | Optional | Code-Review Differentials |
| `entrypoints.json` | `entrypoints` | `architecture.entrypoints` | `architecture.graph_index` | `entrypoints.v1.schema.json` | Ja | Berechnung des Graph-Boosts |

## Anmerkungen zur Artefaktarchitektur

1. **`query_trace.json` vs. `context_bundle`:**
   In der aktuellen Implementierung ist der *Query Trace* konzeptionell als ein Teilfeld `query_trace` im `query-result.v1.schema.json` eingebettet und nicht primär als freistehendes Artefakt angelegt. Die Datei `query_trace.json` wird lediglich durch die CLI als Extrakt via `--trace` flag geschrieben.
2. **`query_context_bundle.json`:**
   Das Context Bundle fungiert als Erweiterung des rohen Treffer-Sets und liefert neben dem Hit auch das *Evidence* (den Snippet) und die umgebenden *Contexts* (wie `graph_context`). Es ist im `query-result.v1.schema.json` via `$ref` zu `query-context-bundle.v1.schema.json` formell erlaubt und wird auf Runtime-Level (`cmd_query.py` und Output-Profile) projiziert.
3. **Fehlende Phase-5-Artefakte:**
   `federation_index.json`, `cross_repo_links.json`, `federation_conflicts.json` existieren derzeit nicht. Föderationsmechanismen sind nicht implementiert.
