# Lenskit Test-Matrix

Diese Matrix ordnet die in `merger/lenskit/tests/` existierenden Tests nach abgedeckten Invarianten, nicht nach Dateien, um nachvollziehbar zu dokumentieren, welche Kernverträge durch isolierte Unit- oder Integrationstests belegt sind.

| Kategorie / Invariante | Betroffene Testdateien / Tests | Kartiertes Verhalten | Status (Phase 0 Audit) | Offene Punkte |
| :--- | :--- | :--- | :--- | :--- |
| **Bundle Integrity** | `test_bundle_manifest_integration.py`, `test_bundle_manifest_schema.py`, `test_role_completeness.py` | Ein Artefakt ohne Manifestrolle ist Drift. Manifesteintrag ohne gültiges Schema ist Drift. | **Substanziell abgedeckt.** | Keine bekannten Enum-Lücken. |
| **Range Integrity** | `test_range_resolver.py`, `test_range_roundtrip.py`, `test_query_schema_range_ref.py` | `range_ref` und `derived_range_ref` werden typisiert geliefert. Split-Mode respektiert den Contract-Umfang. | **Durch vorhandene Tests strukturell belegt.** | Keine vollständige End-to-End-Absicherung. |
| **Graph Integrity** | `test_graph_index.py`, `test_graph_bundle_integration.py` | Graph-Artefakte (`architecture_graph.json` -> `graph_index.json`) bauen deterministisch. Schema-Konformität des Index wird erzwungen. Fehlende Graphen werfen markierte Fallback-Signale. | **Durch vorhandene Tests strukturell belegt.** | Fail-Closed Loader. |
| **Retrieval Integrity (Scoring & Explain)** | `test_retrieval_query.py` (insbesondere `test_query_explain_graph_fields_match_scoring`, `test_graph_bonus_is_bounded`) | Query-Explain-Ausgaben zeigen die Scores (z.B. `bm25 + graph_bonus`), die auch vom Ranking verarbeitet wurden. Graph-Werte werden mathematisch gecappt. | **Durch vorhandene Tests strukturell belegt.** | Der Graph-Score-Term ist strukturell im Code belegt. |
| **Retrieval Integrity (Eval)** | `test_retrieval_eval.py`, `test_graph_eval.py` (`test_eval_graph_delta_reporting`) | Eval nutzt Runtime-Pfade wie Query. Eval berichtet Deltas (`baseline` vs `graph_enabled`) in den Metriken. | **Durch vorhandene Tests strukturell belegt.** | Deltas (`delta_mrr`) sind testbar. |
| **Context Bundle & Output Profiles** | `test_context_bundle.py` (`test_context_bundle_contains_evidence_and_context`, `test_context_bundle_preserves_provenance`, `test_ui_payload_excludes_internal_fields`, `test_agent_minimal_profile_contract`) | Context Builder trennt Hit, Evidence und Context strukturell. Provenance Type bleibt stabil. Output-Profile filtern interne Payload-Daten heraus. | **Durch vorhandene Tests strukturell belegt.** | Keine inhaltliche "Nutzbarkeitsprüfung" über den JSON-Schema-Check hinaus. |
| **Path Security** | `test_atlas_windows_paths.py`, `test_include_paths.py` | Atlas CWD Fallbacks sind reguliert. Absolute Paths werden deterministisch auf Basis Directories gelöst. | **Durch vorhandene Tests strukturell belegt.** | Traversalschutz ist aktiv. |
| **Backwards Compatibility** | `test_contract_version_guards.py`, `test_jsonschema_degradation.py`, `test_context_bundle.py::test_cli_backward_compatibility` | Abwärtskompatibilität wirft Fehler oder nutzt saubere Fallbacks, statt Scheinfakten zu generieren. | **Durch vorhandene Tests strukturell belegt.** | Keine vollständige End-to-End-Absicherung. |
| **Federation & Cross-Repo** | - | - | **Offen.** | Es existieren keine Tests für Föderation (`test_federation_index_builds_deterministically`, `test_cross_repo_links` etc.). |
| **API/UI Integration** | `test_webui_payload.py` | Stellt sicher, dass minimale Playwright-Webseiten-Checks strukturell durchlaufen. | **Lückenhaft.** | API/UI-Strukturen sind nicht umfassend end-to-end gesichert oder als produktionsreif testbar. |

## Zusammenfassung der Test-Abdeckung

Die Testsuite (`merger/lenskit/tests/`) belegt die Grundlagen für die Ingestion (Phase 1), die Core-Runtime (Phase 2), die Graph-Integration (Phase 3) sowie die strukturellen Erwartungen an Context-Bundles (Phase 4).
Diese Belege sichern spezifische Teilziele methodisch ab, decken jedoch weder die API-Sicherheit weitreichend ab, noch prüfen sie die tatsächliche Agent-Tauglichkeit der ausgegebenen Kontexte qualitativ.

Die Test-Matrix verifiziert, dass für die Single-Repo/Single-Bundle Use Cases eine solide Grundlage herrscht. **Phase 5 (Cross-Repo-Knowledge-Layer)** ist vollkommen unbelegt.