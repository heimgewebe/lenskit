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
| `<stem>.graph_index.json` | `graph_index_json` | `retrieval_index` | `derived` | `architecture.graph_index` | `retrieval.query_core`, `eval_core` | `architecture.graph_index.v1.schema.json` | Ja | Graph Penalty/Bonus, Semantic Eval |
| `<stem>_architecture.md` | `architecture_summary` | _(Schema-Zukunftsform: `diagnostic_signal`)_ | _(Schema-Zukunftsform: `diagnostic`)_ | `write_reports_v2` / `generate_architecture_summary` | Mensch, LLMs, Report-Konsumenten | - | Nein (nicht im Bundle Manifest) | Lesbare Architektur-Zusammenfassung |
| `query_context_bundle.json`| - (Runtime Payload) | _(Phase 4)_ | _(Phase 4)_ | `retrieval.query_core` | CLI, WebUI, Agents | `query-context-bundle.v1.schema.json` | Nein (Runtime Output) | Context Expansion, UI Display |
| `query_trace.json` | - (Runtime Payload) | _(Phase 4)_ | _(Phase 4)_ | `retrieval.query_core` | Debug CLI, Evaluatoren | extrahiert aus `query-result.v1.schema.json` | Nein (Runtime Output) | Ranking-Analyse (via `--trace`) |
| `<stem>.retrieval_eval.json` | `retrieval_eval_json` | `diagnostic_signal` | `diagnostic` | `retrieval.eval_core` | CI, Entwickler | `retrieval-eval.v1.schema.json` | Ja (wenn vorhanden) | Evaluierungsmetriken |
| `pr-schau-delta.json` | `delta_json` | _(Schema-Zukunftsform: `diagnostic_signal`)_ | _(Schema-Zukunftsform: `diagnostic`)_ | `core.pr_schau_bundle` (separater pr-schau-Bundle, nicht `bundle-manifest.v1`) | PR-Schau Frontends, Agents | `pr-schau-delta.v1.schema.json` | Nein (nicht im `bundle-manifest.v1`) | Code-Review Differentials |
| `<stem>.entrypoints.json` | - (Hilfs-/Zwischenartefakt) | _(Phase 1: nicht annotiert)_ | _(Phase 1: nicht annotiert)_ | `architecture.entrypoints` | `architecture.graph_index` | `entrypoints.v1.schema.json` | Nein | Berechnung des Graph-Boosts |

## Verwandte Architekturregeln

- Two-Layer Artifact Pattern: [docs/architecture/two-layer-artifact-pattern.md](./two-layer-artifact-pattern.md)
- Artifact Drift Matrix: [docs/architecture/artifact-drift-matrix.md](./artifact-drift-matrix.md)

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
   - `architecture_graph.json` und `architecture_summary` sind getrennt zu behandeln: `architecture_graph.json` bezeichnet Graph-/Importdaten, `architecture_summary` die lesbare `_architecture.md`-Zusammenfassung.
   - `pr-schau-delta.json` wird als `delta_json` deklariert.
5. **Authority/Canonicality-Felder (Phase 1 + 3.5):**
   Die Felder `authority`, `canonicality`, `regenerable` und `staleness_sensitive` sind in `bundle-manifest.v1.schema.json` optional. `authority` und `canonicality` sind pro Rolle wertbeschränkt (z.B. darf `sqlite_index` keine `canonical_content`-Autorität tragen, `architecture_summary` keinen `content_source`-Status). `regenerable` und `staleness_sensitive` werden vom Producer emittiert und bleiben typgeprüft. `staleness_sensitive` beschreibt Bundle-interne Drift, nicht Aktualität gegenüber dem Live-Repository.

   **Vom Producer (`merger/lenskit/core/merge.py`, `AUTHORITY_REGISTRY`) aktiv emittiert (acht Rollen):**
   `canonical_md`, `index_sidecar_json`, `dump_index_json`, `derived_manifest_json`, `chunk_index_jsonl`, `sqlite_index`, `retrieval_eval_json` (Phase 3.5), `graph_index_json` (Phase 3.5).

   **Im Schema als Zukunftsform per-role-constrained, aber nicht vom `bundle-manifest.v1`-Producer emittiert:**
   - `architecture_summary` — wird von `write_reports_v2` *nicht* als Manifest-Artefakt aufgenommen; der `_write_architecture_summary`-Pfad schreibt die Datei, aber `_add_artifact` wird für diese Rolle nicht aufgerufen. Schema-Constraint (`diagnostic_signal` / `diagnostic`) bleibt als zulässige Zukunftsform.
   - `delta_json` — lebt im pr-schau-Bundle (`core.pr_schau_bundle`), das ein **eigenes** Manifest gemäß `pr-schau.v1.schema.json` produziert. Im `bundle-manifest.v1`-Pfad gibt es keinen `_add_artifact(... ArtifactRole.PR_DELTA_JSON ...)`-Aufruf. Schema-Constraint (`diagnostic_signal` / `diagnostic`) verhindert, dass extern gebaute Manifeste delta_json fälschlich als kanonischen Inhalt deklarieren.

   **Außerhalb des Bundle-Manifest-Pfads (keine Schema-Constraints):**
   `query_context_bundle.json`, `query_trace.json` — Runtime-Payloads. `entrypoints.json`, `architecture_graph.json` — Zwischenartefakte für `build_derived_artifacts`. `source_file` — Range-Resolver-Konzept (`core.range_resolver`), nicht im Manifest.

   Folgepunkte (außerhalb dieser PR-Stufe): Annotation für Runtime-Artefakte (Phase 4) und föderierte Artefakte (Phase 5).
