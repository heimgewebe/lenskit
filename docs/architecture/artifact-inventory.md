# Lenskit Artefakt-Inventar

Dieses Inventar dokumentiert die primären und abgeleiteten Artefakte von Lenskit, wie sie aktuell in `merger/lenskit/` implementiert und durch Verträge (Contracts) abgesichert sind.

Die Spalten **Authority** und **Canonicality** entsprechen den optionalen Feldern in `bundle-manifest.v1.schema.json` (Phase 1 der Artifact-Integrity-Blaupause). Sie machen maschinenlesbar, *was* ein Artefakt sein darf:

- `canonical_content` / `content_source` — der Inhalt selbst.
- `navigation_index` / `index_only` — zeigt, beweist nicht.
- `retrieval_index` / `derived` — die Quelle für Retrieval, abgeleitet aus dem Inhalt.
- `runtime_cache` / `cache` — beschleunigt Suche, ist nicht der Ursprung.
- `diagnostic_signal` / `diagnostic` — warnt, beweist nicht.
- `runtime_observation` / `observation` — Spur eines Laufs, kein Beleg über das Repository.

Dateiendung ist Kleidung; Autorität ist Identität.

| Artefaktname / Dateiname | Artefaktrolle / Dateiform | Authority | Canonicality | Erzeuger (Producer) | Verbraucher (Consumer) | Verbundenes Schema | Manifest Visibility | Runtime Usage |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `<stem>.canonical.md` | `canonical_md` | `canonical_content` | `content_source` | `core.merge` | Mensch, LLMs (direkt), Bundle Manifest | - | Ja | Indirekt (als Bundle-Fallback) |
| `<stem>.chunk_index.jsonl` | `chunk_index_jsonl` | `retrieval_index` | `derived` | `core.chunker` | `retrieval.index_db` | - | Ja | Index-Aufbau |
| `<stem>.index.sqlite` | `sqlite_index` | `runtime_cache` | `cache` | `retrieval.index_db` | `retrieval.query_core`, `eval_core` | - | Ja (als `.index.sqlite`) | FTS5 Ranking, Chunk Retrieval |
| `<stem>.dump_index.json` | `dump_index_json` | `navigation_index` | `index_only` | `core.merge` | `retrieval.index_db` | - | Ja | Initialer Index-Bau |
| `<stem>.json` (Sidecar) | `index_sidecar_json` | `navigation_index` | `index_only` | `core.merge` | Agents, WebUI, CLI, Lenskit Service | `bundle-manifest.v1.schema.json` | Meta | Verknüpfung der Artefakte |
| `<base>.derived_index.json` | `derived_manifest_json` | `navigation_index` | `derived` | `core.merge` | Bundle-Konsumenten | - | Ja | Verlinkt abgeleitete Artefakte |
| `<stem>.graph_index.json` | `graph_index_json` | _(Phase 1: nicht annotiert)_ | _(Phase 1: nicht annotiert)_ | `architecture.graph_index` | `retrieval.query_core`, `eval_core` | `architecture.graph_index.v1.schema.json` | Ja | Graph Penalty/Bonus, Semantic Eval |
| `<stem>.architecture_graph.json`| `architecture_summary` | _(Phase 1: nicht annotiert)_ | _(Phase 1: nicht annotiert)_ | `architecture.import_graph` | `architecture.graph_index` | `architecture.graph.v1.schema.json` | Nein (nicht im Bundle Manifest) | Erzeugung des Index |
| `query_context_bundle.json`| - (Runtime Payload) | _(Phase 4)_ | _(Phase 4)_ | `retrieval.query_core` | CLI, WebUI, Agents | `query-context-bundle.v1.schema.json` | Nein (Runtime Output) | Context Expansion, UI Display |
| `query_trace.json` | - (Runtime Payload) | _(Phase 4)_ | _(Phase 4)_ | `retrieval.query_core` | Debug CLI, Evaluatoren | extrahiert aus `query-result.v1.schema.json` | Nein (Runtime Output) | Ranking-Analyse (via `--trace`) |
| `<stem>.retrieval_eval.json` | `retrieval_eval_json` | _(Phase 1: nicht annotiert)_ | _(Phase 1: nicht annotiert)_ | `retrieval.eval_core` | CI, Entwickler | `retrieval-eval.v1.schema.json` | Optional | Evaluierungsmetriken |
| `pr-schau-delta.json` | `delta_json` | _(Phase 1: nicht annotiert)_ | _(Phase 1: nicht annotiert)_ | `core.pr_schau_bundle` | PR-Schau Frontends, Agents | `pr-schau-delta.v1.schema.json` | Optional | Code-Review Differentials |
| `<stem>.entrypoints.json` | - (Hilfs-/Zwischenartefakt) | _(Phase 1: nicht annotiert)_ | _(Phase 1: nicht annotiert)_ | `architecture.entrypoints` | `architecture.graph_index` | `entrypoints.v1.schema.json` | Nein | Berechnung des Graph-Boosts |

## Anmerkungen zur Artefaktarchitektur

1. **`query_trace.json` vs. `context_bundle`:**
   In der aktuellen Implementierung ist der *Query Trace* konzeptionell als ein Teilfeld `query_trace` im `query-result.v1.schema.json` eingebettet und nicht primär als freistehendes Artefakt angelegt. Die Datei `query_trace.json` wird lediglich durch die CLI als Extrakt via `--trace` flag geschrieben.
2. **`query_context_bundle.json`:**
   Das Context Bundle fungiert als Erweiterung des rohen Treffer-Sets und liefert neben dem Hit auch das *Evidence* (den Snippet) und die umgebenden *Contexts* (wie `graph_context`). Es ist im `query-result.v1.schema.json` via `$ref` zu `query-context-bundle.v1.schema.json` formell erlaubt und wird auf Runtime-Level (`cmd_query.py` und Output-Profile) projiziert.
3. **Fehlende Phase-5-Artefakte:**
   `federation_index.json`, `cross_repo_links.json`, `federation_conflicts.json` existieren derzeit nicht. Föderationsmechanismen sind nicht implementiert.
4. **Begriffs-Dissonanzen (Repo-Kanonik vs. Dateinamen):**
   Einige Rollenbegriffe weichen historisch gewachsen von den Dateinamen ab. Um Semantic Drift zu vermeiden, dokumentiert dieses Inventar streng die in `merger/lenskit/core/constants.py` und `bundle-manifest.v1.schema.json` hartcodierten `ArtifactRole` Enums.
   - `index.sqlite` wird systemintern als `sqlite_index` geführt (statt `chunk_index_sqlite`).
   - `architecture_graph.json` wird systemintern als `architecture_summary` geführt. Dies ist ein konzeptioneller Modellwechsel (Graph != Summary), entspricht aber dem aktuellen Code-Stand.
   - `pr-schau-delta.json` wird als `delta_json` deklariert.
5. **Authority/Canonicality-Felder (Phase 1):**
   Die Felder `authority`, `canonicality`, `regenerable` und `staleness_sensitive` sind in `bundle-manifest.v1.schema.json` optional. `authority` und `canonicality` sind pro Rolle wertbeschränkt (z.B. darf `sqlite_index` keine `canonical_content`-Autorität tragen, `architecture_summary` keinen `content_source`-Status). `regenerable` und `staleness_sensitive` werden in Phase 1 vom Producer emittiert und bleiben zunächst typgeprüft. `staleness_sensitive` beschreibt Bundle-interne Drift, nicht Aktualität gegenüber dem Live-Repository. Der Producer (`merger/lenskit/core/merge.py`, `AUTHORITY_REGISTRY`) emittiert diese Felder aktuell für sechs Rollen: `canonical_md`, `index_sidecar_json`, `dump_index_json`, `derived_manifest_json`, `chunk_index_jsonl`, `sqlite_index`. Für `retrieval_eval_json`, `delta_json`, `graph_index_json`, `architecture_summary` und Runtime-Artefakte folgen die Annotationen in späteren Phasen (3, 4, 5). `architecture_summary` wird vom aktuellen Producer (`write_reports_v2`) nicht in das Bundle Manifest aufgenommen; der entsprechende Schema-Constraint bleibt als zulässige Zukunftsform stehen.
