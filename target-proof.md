# Target Proof (Phase 4 - Context-Bundle/Query-Trace)

### 1. Schema-Beleg
- Pfad: `merger/lenskit/contracts/query-context-bundle.v1.schema.json`
- Wichtigste required Felder pro Hit: `hit_identity`, `file`, `path`, `range`, `score`, `resolved_code_snippet`, `provenance_type`, `bundle_source_references`

### 2. Runtime-Beleg
- `build_context_bundle`: Definiert in `merger/lenskit/retrieval/query_core.py` (Zeile 618+). Trennt strikt Hit-Metadaten von `resolved_code_snippet` (Evidence) und `surrounding_context` (Context).
- `_expand_context`: Definiert in `merger/lenskit/retrieval/query_core.py` (Zeile 584+). Nutzt deterministische SQL-Queries auf den `chunks_fts` und `chunks` Tabellen, um `exact`, `block`, `window`, und `file` konsistent abzuleiten.
- Integration: In `execute_query` wird das Bundle abhängig von `build_context=True` deterministisch am Ende des Suchvorgangs erzeugt (Zeile 547+).

### 3. CLI-Beleg
- Flags in `cmd_query.py` und `main.py`: `--output-profile`, `--context-mode`, `--context-window-lines`
- Reduktions-Logik in `cmd_query.py`:
  - `agent_minimal`: Reduziert das kanonische Context-Bundle, indem `explain`, `graph_context` und ein leerer `surrounding_context` pro Hit entfernt werden.
  - `ui_navigation`: Behält das komplette kanonische Bundle als Datenmodell für die Ansicht bei.
  - Das Basis-Bundle bleibt davon unberührt. Profile sind reine Ausgabe-Projektionen (Render-Schicht).

### 4. Test-Beleg
- Test-Datei: `merger/lenskit/tests/test_context_bundle.py`
- Alle 6 Tests sind erfolgreich (`PYTHONPATH=. pytest merger/lenskit/tests/test_context_bundle.py` liefert 6 passed):
  - `test_context_bundle_contains_evidence_and_context`
  - `test_context_bundle_preserves_provenance`
  - `test_context_expansion_exact_vs_block_vs_window`
  - `test_ui_payload_excludes_internal_fields`
  - `test_agent_minimal_profile_contract`
  - `test_context_bundle_roundtrip_with_resolver`

### 5. Abgrenzung / Status
- [x] **Erledigt (Phase 4):**
  - `query_trace.json` (wurde bereits im vorherigen PR eingeführt, jetzt verifiziert im Kontext).
  - `query_context_bundle.json` Schema und Build-Logik.
  - Trennung Hit/Evidence/Context (`build_context_bundle`).
  - Deterministische Context-Expansion (`_expand_context`).
  - Provenance-first (explizit `range_ref` vs `derived_range_ref` und `provenance_type` im Context-Bundle).
  - Output-Profile als reine Projektionen (`agent_minimal`, `ui_navigation`).
- [ ] **Noch offen / Nicht in diesem Scope:**
  - API/Service-Integration (`API/UI-ready Struktur` ist zwar vorbereitet als Output, aber die echten Service-Endpunkte kommen erst in Phase 7).
