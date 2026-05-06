# Lenskit Contracts-Matrix

Diese Matrix dokumentiert die Verbindungen zwischen Systemrollen, Schemata, Abhängigkeiten und Drift-Risiken, wie sie aktuell in `merger/lenskit/contracts/` abgebildet sind.

## Schema-Abhängigkeiten und Enum-Vollständigkeit

| Schema Name | Zweck | Typische Attribute | Verwendete Typen / Enumerationen | Referenzen (`$ref`) | Relevanz / Drift-Risiko |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `bundle-manifest.v1.schema.json` | Kern-Manifest für Lenskit Artefakte. | `artifacts`, `role`, `sha256` | `artifactRole` (z.B. `canonical_md`, `chunk_index_jsonl`, `graph_index_json`) | - | Sehr hoch. Enum Drift zwischen Code und Schema führt zum Build-Ausfall. |
| `query-result.v1.schema.json` | Formales Ranking- und Hit-Ergebnis. | `results`, `context_bundle`, `query_trace` | - | `query-context-bundle.v1.schema.json`, `range-ref.v1.schema.json` | Hoch. Basis für Agenten und Evaluierung. |
| `query-context-bundle.v1.schema.json` | Arbeitsmaterial für Hits (Hit + Evidence + Context). | `resolved_code_snippet`, `graph_context`, `provenance_type` | `provenance_type` (`explicit`, `derived`) | `range-ref.v1.schema.json` | Hoch. Kontext-Expansion (exact, window) muss mit Feldern matchen. |
| `range-ref.v1.schema.json` | Definiert präzise Quelltext-Bereiche. | `file`, `start_line`, `end_line`, `kind` | `kind` (`file`, `class`, `function`, `method`, etc.) | - | Mittel. Muss mit Extraktor-Outputs synchron bleiben. |
| `architecture.graph_index.v1.schema.json` | Graph-Signal für die Query Runtime. | `kind`, `version`, `distances`, `metrics` | `kind` (must be `lenskit.architecture.graph_index`) | - | Mittel. Distanzformate müssen von `query_core` verstanden werden. |
| `retrieval-eval.v1.schema.json` | Output von `eval_core` für Regression-Tracking. | `metrics`, `details`, `baseline`, `graph` | - | `query-result.v1.schema.json` (für `why`/`explain` Details) | Gering. Metriken sind stabil. |
| `pr-schau-delta.v1.schema.json` | Delta-Manifest für PR Reviews. | `commit_sha`, `diff_artifacts` | - | `pr-schau.v1.schema.json` | Mittel. Integrationstiefe in Agents prüfen. |
| `entrypoints.v1.schema.json` | Startpunkte im Graph für Boosts. | `entrypoints`, `weights` | - | - | Gering. |
| `agent-query-session.v2.schema.json` | Provenienz-Wrapper für Agent Query Sessions (Runtime-Artefakt). | `session_authority`, `context_source`, `artifact_refs`, `claim_boundaries` | `session_authority` (const: `"agent_context_projection"`); `context_source` (enum: `projected`, `federated`, `mixed`, `unknown`); `artifact_refs` required: `query_trace_id`, `context_bundle_id`, `agent_query_session_id` (alle `string\|null`); `claim_boundaries` required: `proves`, `does_not_prove` | - | Hoch. `session_authority` und `claim_boundaries` definieren, was eine Session beweisen darf und was nicht. Drift hier würde falsche epistemische Grenzen erzeugen. |
| `federation-index.v1.schema.json` | Contract für den Föderations-Index (Liste verbundener Bundles). | `kind`, `version`, `federation_id`, `created_at`, `updated_at`, `bundles` | - | - | Hoch. Contract vorhanden und Runtime-implementiert (minimale Multi-Bundle-Aggregation); vollständige föderierte Ranking-Semantik noch offen. |
| `cross-repo-links.v1.schema.json` | Contract für minimale Cross-Repo-Co-Occurrence-Links (keine Identitäts-/Abhängigkeitsaussage). | `source_repo`, `target_repo`, `link_type`, `evidence_refs`, `confidence` | `link_type` (const: `co_occurrence`); `confidence` (const: `inferred`) | - | Hoch. Runtime-Producer implementiert (federierte Query), CLI-Trace-Persistenz aktiv. |
| `federation-conflicts.v1.schema.json` | Contract für föderierte Konfliktspuren (Array von Konfliktobjekten). | Item-Felder: `conflict_id`, `type`, `involved_results`, `description`, `resolution` | `type` (enum: `identity`, `path`, `symbol`, `evidence`, `provenance`); `resolution` (enum: `unresolved`) | - | Mittel bis hoch. Heuristisch/minimal emittiert (Runtime-Emission in `federation_query.py`, CLI-Persistenz in `cmd_federation.py`); semantische Konfliktlogik noch offen. |

## Canonical Pfade und Pflichtfelder

1.  **`canonical_md` in `bundle-manifest`:** Muss exakt ein Artefakt sein. Multi-Part Dumps deklarieren nur eines als kanonisch (`core/merge.py` via `resolve_canonical_md`).
2.  **`range_ref` vs. `derived_range_ref` in `query-result`:**
    *   `range_ref`: Darf nur gesetzt werden, wenn der `range_resolver` den Bereich im Bundle (`sqlite_index`) deterministisch gefunden hat.
    *   `derived_range_ref`: Source-backed Fallback.
    *   **Invariante:** Darf nie vermischt werden. Das `query-context-bundle` Schema macht dies transparent über `provenance_type`.
3.  **`explain` Block im `query-result`:**
    *   Strikter Vertrag: `additionalProperties: false`. Graph-Diagnostiken müssen in `why.diagnostics.graph` liegen, nie direkt in `why`.
    *   Muss exakt den Score widerspiegeln (`final_score` = `lexical` + `semantic` + `graph_bonus` + `penalties`).

## Drift-Schutz

- Ein **`Role-Completeness-Check`** (`test_role_completeness.py`) vergleicht `core/constants.py` (ArtifactRoles) mit `bundle-manifest.v1.schema.json`.
- Schemas werden im Build-Prozess und in Tests mit `jsonschema` validiert.

## Bekannte Lücken (Contract Matrix)

-   Formale Schemas für `cross_repo_links.json` und `federation_conflicts.json` sind vorhanden (`cross-repo-links.v1.schema.json`, `federation-conflicts.v1.schema.json`). `cross_repo_links` ist als minimaler, heuristischer Co-Occurrence-Output im föderierten Query-/Trace-Pfad emittiert und per CLI-Trace persistierbar. Semantische Grenzen bleiben explizit: keine Identitäts-, Abhängigkeits- oder Gleichheitsaussage; belegt wird nur gemeinsame Query-Präsenz in finalen Ergebnissen. Hinweis zur Vertragsgeschichte: `cross-repo-links.v1` war zuvor ein nicht stabil runtime-konsumierter Placeholder; die Root-Form wurde auf das tatsächlich emittierte Array-Format korrigiert.
-   `agent-query-session.v2.schema.json` ist eingetragen und belegt; offen bleiben: Lifecycle/Retention-Kontrakt, MCP-Binding-Schema.
