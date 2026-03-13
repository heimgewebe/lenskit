# Lenskit Contracts-Matrix

Diese Matrix dokumentiert die Verbindungen zwischen Systemrollen, Schemata, Abhängigkeiten und Drift-Risiken, wie sie aktuell in `merger/lenskit/contracts/` abgebildet sind.

## Schema-Abhängigkeiten und Enum-Vollständigkeit

| Schema Name | Zweck | Typische Attribute | Verwendete Typen / Enumerationen | Referenzen (`$ref`) | Relevanz / Drift-Risiko |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `bundle-manifest.v1.schema.json` | Kern-Manifest für Lenskit Artefakte. | `artifacts`, `role`, `sha256` | `artifactRole` (z.B. `canonical_md`, `chunk_index_jsonl`, `graph_index_json`) | - | Sehr hoch. Enum Drift zwischen Code und Schema führt zum Build-Ausfall. |
| `query-result.v1.schema.json` | Formales Ranking- und Hit-Ergebnis. | `results`, `context_bundle`, `query_trace` | - | `query-context-bundle.v1.schema.json`, `range-ref.v1.schema.json` | Hoch. Basis für Agenten und Evaluierung. |
| `query-context-bundle.v1.schema.json` | Arbeitsmaterial für Hits (Hit + Evidence + Context). | `snippet`, `graph_context`, `provenance_type` | `provenance_type` (`explicit`, `derived`) | `range-ref.v1.schema.json` | Hoch. Kontext-Expansion (exact, window) muss mit Feldern matchen. |
| `range-ref.v1.schema.json` | Definiert präzise Quelltext-Bereiche. | `file`, `start_line`, `end_line`, `kind` | `kind` (`file`, `class`, `function`, `method`, etc.) | - | Mittel. Muss mit Extraktor-Outputs synchron bleiben. |
| `architecture.graph_index.v1.schema.json` | Graph-Signal für die Query Runtime. | `kind`, `version`, `distances`, `metrics` | `kind` (must be `lenskit.architecture.graph_index`) | - | Mittel. Distanzformate müssen von `query_core` verstanden werden. |
| `retrieval-eval.v1.schema.json` | Output von `eval_core` für Regression-Tracking. | `metrics`, `details`, `baseline`, `graph` | - | `query-result.v1.schema.json` (für `why`/`explain` Details) | Gering. Metriken sind stabil. |
| `pr-schau-delta.v1.schema.json` | Delta-Manifest für PR Reviews. | `commit_sha`, `diff_artifacts` | - | `pr-schau.v1.schema.json` | Mittel. Integrationstiefe in Agents prüfen. |
| `entrypoints.v1.schema.json` | Startpunkte im Graph für Boosts. | `entrypoints`, `weights` | - | - | Gering. |

## Canonical Pfade und Pflichtfelder

1.  **`canonical_md` in `bundle-manifest`:** Muss exakt ein Artefakt sein. Multi-Part Dumps deklarieren nur eines als kanonisch (`core/merge.py` via `resolve_canonical_md`).
2.  **`range_ref` vs. `derived_range_ref` in `query-result`:**
    *   `range_ref`: Darf nur gesetzt werden, wenn der `range_resolver` den Bereich im Bundle (`chunk_index_sqlite`) deterministisch gefunden hat.
    *   `derived_range_ref`: Source-backed Fallback.
    *   **Invariante:** Darf nie vermischt werden. Das `query-context-bundle` Schema macht dies transparent über `provenance_type`.
3.  **`explain` Block im `query-result`:**
    *   Strikter Vertrag: `additionalProperties: false`. Graph-Diagnostiken müssen in `why.diagnostics.graph` liegen, nie direkt in `why`.
    *   Muss exakt den Score widerspiegeln (`final_score` = `lexical` + `semantic` + `graph_bonus` + `penalties`).

## Drift-Schutz

- Ein **`Role-Completeness-Check`** (`test_role_completeness.py`) vergleicht `core/constants.py` (ArtifactRoles) mit `bundle-manifest.v1.schema.json`.
- Schemas werden im Build-Prozess und in Tests mit `jsonschema` validiert.

## Bekannte Lücken (Contract Matrix)

-   Kein Vertrag für Föderation (`federation_index.v1.schema.json` fehlt). Identitäten über Repositories hinweg (Phase 5) sind noch nicht strukturell geklärt.