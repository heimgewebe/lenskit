# Target Proof (Phase 4 - Context-Bundle/Query-Trace)

### 1. Schema-Beleg
- Pfad: `merger/lenskit/contracts/query-context-bundle.v1.schema.json`
- Wichtigste required Felder pro Hit: `hit_identity`, `file`, `path`, `range`, `score`, `resolved_code_snippet`, `provenance_type`, `bundle_source_references`

### 2. Runtime-Beleg
- `build_context_bundle`: Definiert in `merger/lenskit/retrieval/query_core.py`. Trennt strikt Hit-Metadaten von `resolved_code_snippet` (Evidence) und `surrounding_context` (Context).
  - Das problematische `_raw_content` Feld leakt nicht mehr in die Treffer, sondern wird als explizites lokales Mapping (`raw_contents`) übergeben.
- `_expand_context`: Definiert in `merger/lenskit/retrieval/query_core.py`. Nutzt SQL-Queries auf den `chunks_fts` und `chunks` Tabellen, um `exact`, `window`, und `file` konsistent abzuleiten.
  - Hinweis: Der Modus `block` ist aktuell als reines Pass-through ohne zusätzliche Expansion implementiert (gibt `None` zurück), da echtes Block-Parsing im Chunking vorgeschaltet stattfindet.
- Integration: In `execute_query` wird das Bundle abhängig von `build_context=True` am Ende des Suchvorgangs erzeugt und sauber in den `query-result.v1.schema.json` Contract eingebettet.

### 3. CLI-Beleg
- Flags in `cmd_query.py` und `main.py`: `--output-profile`, `--context-mode`, `--context-window-lines`
- `build_context` Logik in `cmd_query.py` ist unabhängig vom Vorhandensein eines Output-Profiles und reagiert auch, wenn lediglich `--context-mode` oder `--context-window-lines` aktiviert werden.
- Reduktions-Logik in `cmd_query.py`:
  - `agent_minimal`: Reduziert das kanonische Context-Bundle, indem `explain`, `graph_context` und ein leerer `surrounding_context` pro Hit entfernt werden.
  - `ui_navigation`: Behält das komplette kanonische Bundle als Datenmodell für die Ansicht bei.
  - Das Basis-Bundle bleibt davon unberührt. Profile sind reine Ausgabe-Projektionen (Render-Schicht).

### 4. Test-Beleg
- Test-Datei: `merger/lenskit/tests/test_context_bundle.py`
- Alle 7 Tests sind erfolgreich (`PYTHONPATH=. pytest merger/lenskit/tests/test_context_bundle.py` liefert 7 passed):
  - `test_context_bundle_contains_evidence_and_context`
  - `test_context_bundle_preserves_provenance`
  - `test_context_expansion_exact_vs_block_vs_window`
  - `test_ui_payload_excludes_internal_fields`
  - `test_agent_minimal_profile_contract`
  - `test_context_bundle_extracts_snippet_correctly`
  - `test_cli_rejects_window_lines_without_window_mode`

### 5. Abgrenzung / Status
- [x] **Erledigt:**
  - `query_trace.json` Schema-Feld ist vorhanden und wird durch die Runtime generiert.
  - Grundlegendes `query_context_bundle.json` Schema (eingebettet im Query-Result) samt Build-Logik (`build_context_bundle`, `_expand_context`) ist vorhanden und separiert Evidence von Context.
  - `--output-profile` CLI-Flags für initiale Projection-Logik.
- [ ] **Noch offen / Nicht in diesem PR (Phase 4 bleibt als Gesamtziel un-abgehakt):**
  - Eigenständige Context-Bundle Artefaktisierung (außerhalb des Query-Results als komplett eigenständiges Repo-Artefakt).
  - API/Service-Integration und echtes Context-Bundle Eval.
  - Phase 4 bleibt in der Roadmap als Ganzes offen, bis alle Sub-Ziele (wie API-Readiness) implementiert sind.
