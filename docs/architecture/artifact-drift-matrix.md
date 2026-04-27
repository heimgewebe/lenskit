# Artifact Drift Matrix

Diese Matrix dokumentiert paarweise Drift-Risiken zwischen Lenskit-Artefakten
und ordnet jeder Paarung Autorität, Guard und Regenerationspfad zu. Sie ist
zunächst **diagnostisch**: sie macht bestehende Ankerpunkte sichtbar, ohne
neue Blocking-Guards einzuführen.

Sie ergänzt das
[Two-Layer Artifact Pattern](./two-layer-artifact-pattern.md) und das
[Artefakt-Inventar](./artifact-inventory.md): das Pattern legt Schichten fest,
das Inventar listet Artefakte, diese Matrix beschreibt die Übergänge.

## Matrix

| Quelle A | Quelle B | Konfliktfall | Autorität | Guard / Test / Coverage-Status | Regeneration |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `canonical_md` | `index_sidecar_json` | Sidecar verweist auf fehlende oder verschobene Section | `canonical_md` für Inhalt, Sidecar nur Navigation | `test_sidecar_contracts.py`, `test_report_parsing.py` | Sidecar regenerieren |
| `bundle_manifest` | Artefakte | Manifest-SHA passt nicht zum Artefakt | Artefaktinhalt + Manifest müssen konsistent sein | Aktuell nur Producer-/Schema-Anker: `test_bundle_manifest_integration.py`; dedizierter SHA-Recompute-Guard fehlt | Manifest regenerieren |
| `dump_index_json` | `derived_manifest_json` | `canonical_dump_index_sha256` mismatch | `dump_index_json` | Aktuell nicht vollständig abgedeckt; später dedizierter derived-manifest staleness Guard | derived index regenerieren |
| `chunk_index_jsonl` | `sqlite_index` | SQLite aus altem Chunk-Index | `chunk_index_jsonl` | `test_stale_check.py`, `test_sqlite_capabilities.py` | SQLite regenerieren |
| `query_trace` | `context_bundle` | Trace beschreibt andere Treffer als Context Bundle | gemeinsame Run-ID und Query Trace | `test_artifact_lookup.py`, `test_trace_lookup.py`, `test_context_lookup.py` | Runtime-Artefakte neu erzeugen |
| `context_bundle` | `agent_query_session` | Session verweist auf anderen Kontext | `context_bundle` + `artifact_refs` | `test_agent_session_builder.py` | Session neu erzeugen |
| `architecture_summary` | architecture graph / `graph_index` | Summary behauptet nicht belegte Kante | Graph Contract / Graph Index, Summary nur Diagnose | `test_graph_eval.py`, `test_graph_index.py` | Summary regenerieren |
| PR-Schau JSON | PR-Schau Markdown | JSON meldet vollständig, Markdown fehlt oder ist unvollständig | Markdown Content + Completeness Block | `pr_schau_verify` als Verifier-Pfad; dedizierter Completeness-Test fehlt. `test_pr_schau_consumer_gate.py` prüft nur Consumer-Zugriff | PR-Schau Bundle neu bauen |

## Rollout-Regel

Diese Matrix ist zunächst diagnostisch. Neue Blocking-Guards dürfen erst
entstehen, wenn:

1. der Producer stabil emittiert,
2. Fixtures aktualisiert sind,
3. mindestens ein diagnostischer Lauf grün war,
4. Consumer zusätzliche Felder tolerieren.

Eine Guard-Promotion (Diagnose → Blocking) erfolgt pro Zeile getrennt, nicht
für die gesamte Matrix auf einmal. Damit bleibt das Drift-Inventar wachsbar,
ohne die CI in einem Schritt zu verschärfen.
