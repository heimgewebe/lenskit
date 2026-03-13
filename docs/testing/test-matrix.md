# Lenskit Test-Matrix

Diese Matrix ordnet die in `merger/lenskit/tests/` existierenden Tests nach abgedeckten Invarianten, nicht nach Dateien, um sicherzustellen, dass zentrale Architekturprinzipien bewiesen sind.

| Kategorie / Invariante | Betroffene Testdateien / Tests | Bewiesenes Verhalten | Status (Phase 0) | Offene Punkte |
| :--- | :--- | :--- | :--- | :--- |
| **Bundle Integrity** | `test_bundle_manifest_integration.py`, `test_bundle_manifest_schema.py`, `test_role_completeness.py` | Ein Artefakt ohne Manifestrolle ist Drift. Manifesteintrag ohne gültiges Schema ist Drift. | **Belegt.** | Keine. Rollen werden streng geprüft. |
| **Range Integrity** | `test_range_resolver.py`, `test_range_roundtrip.py`, `test_query_schema_range_ref.py` | `range_ref` und `derived_range_ref` dürfen nie implizit überschreiben. Split-Mode respektiert den Contract. | **Belegt.** | Keine. |
| **Graph Integrity** | `test_graph_index.py`, `test_graph_bundle_integration.py` | Graph-Artefakte (`architecture_graph.json` -> `graph_index.json`) bauen deterministisch. Schema-Konformität des Index wird erzwungen. Fehlende Graphen werfen klar markierte Fehler. | **Belegt.** | Keine. Fail-Closed Prinzip ist aktiv. |
| **Retrieval Integrity (Scoring & Explain)** | `test_retrieval_query.py` (insbesondere `test_query_explain_graph_fields_match_scoring`, `test_graph_bonus_is_bounded`) | Query-Explain muss dieselben Scores erklären, die das Ranking erzeugt. Graph beeinflusst das Ranking transparent. | **Belegt.** | Keine. `score_pre = bm25 + graph_bonus` ist mathematisch stabil. |
| **Retrieval Integrity (Eval)** | `test_retrieval_eval.py`, `test_graph_eval.py` (`test_eval_graph_delta_reporting`) | Eval darf Runtime-Pfade nicht anders behandeln als Query. Eval berichtet Deltas (`baseline` vs `graph_enabled`). | **Belegt.** | Keine. |
| **Context Bundle & Output Profiles** | `test_context_bundle.py` (`test_context_bundle_contains_evidence_and_context`, `test_context_bundle_preserves_provenance`, `test_ui_payload_excludes_internal_fields`, `test_agent_minimal_profile_contract`) | Context Builder trennt Hit, Evidence und Context. Provenance Type bleibt stabil. Output-Profile (Agent Minimal, UI Navigation) filtern interne State-Variablen sauber aus. | **Belegt.** | Keine. `query_trace` und `context_bundle` sind Output-sicher. |
| **Path Security** | `test_atlas_paths.py`, `test_atlas_windows_paths.py`, `test_include_paths.py` | Atlas CWD Fallbacks sind streng reguliert. Absolute Paths werden deterministisch auf Basis Directories gelöst. | **Belegt.** | Keine. Traversalschutz ist aktiv. |
| **Backwards Compatibility** | `test_contract_version_guards.py`, `test_jsonschema_degradation.py`, `test_cli_backward_compatibility` | Abwärtskompatibilität darf keine Scheinfakten erzeugen. Degradierung erfolgt "graceful". | **Belegt.** | Keine. Fallbacks sind dokumentiert. |
| **Federation & Cross-Repo** | - | - | **Offen.** | Es existieren keine Tests (und kein Code) für Föderation (`federation_index_builds_deterministically` etc.). |

## Zusammenfassung der Test-Abdeckung

Die Testsuite (`merger/lenskit/tests/`) deckt die Phase 0 (Diagnose), Phase 1 (Contracts), Phase 2 (Query-Runtime), Phase 3 (Graph-Runtime) und Phase 4 (Context-Bundle / Retrieval-Produktisierung) vollständig und belastbar ab.
Alle "Gates" für Phase 1 bis 4 (siehe `lenskit-upgrade-blaupause.md`) lassen sich durch konkrete, grüne Tests belegen.

Die Test-Matrix zeigt jedoch klar, dass **Phase 5 (Cross-Repo-Knowledge-Layer)** komplett fehlt, was konsistent mit dem Implementierungsstand ist.