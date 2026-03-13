# Offene Inkonsistenzen-Liste (Lenskit Phase 0)

Stand: Phase 0 Re-Audit (nach Abschluss Phase 4 Implementierung)

Diese Liste dokumentiert systematisch die Lücken zwischen der visionären Zielarchitektur (Blaupause), der aktuellen Code-Basis (`merger/lenskit/`) und der tatsächlichen Testabdeckung. Ziel ist es, den Ist-Zustand belastbar darzustellen, bevor weitere Komplexität (z.B. Cross-Repo-Föderation in Phase 5) hinzugefügt wird.

## 1. Was ist implementiert, dokumentiert und belastbar getestet?
*(Diese Aspekte gelten als architektonisch sicher und sind durch "Gates" in der Blaupause gedeckt)*

*   **Artefakt-Zentrierung & Contracts (Phase 1):** Die Kernartefakte (`canonical_md`, `chunk_index.jsonl`, `index.sqlite`, `dump_index.json`, `index_sidecar.json`) werden konsistent und deterministisch erzeugt. Die Manifest-Rollen (`ArtifactRoles`) decken sich exakt mit dem `bundle-manifest.v1.schema.json`. Ein `Role-Completeness-Check` verhindert Enum-Drift.
*   **Query-Runtime & Explain (Phase 2):** Die `execute_query` Pipeline in `query_core.py` ist sauber gestuft (Parse, Retrieve, Rerank, Provenance, Explain). Der Score (z.B. BM25) deckt sich exakt mit den Explain-Daten. Stille Fehlerpfade wurden durch explizite Fallback-Marker ersetzt (z.B. wenn der Graph fehlt).
*   **Graph-Runtime Konsolidierung (Phase 3):**
    *   `load_graph_index` lädt und normalisiert den Graphen zentral (Fail-Closed).
    *   Der Score-Term (`graph_bonus`) ist mathematisch definiert (`raw_graph_bonus = w_g * graph_proximity + w_e * entrypoint_boost`, capped).
    *   Das Explain-Objekt zeigt `graph_used`, `graph_status`, `distance` und `graph_bonus` präzise an.
    *   Eval (`test_eval_graph_delta_reporting`) berichtet Deltas (`baseline_mrr` vs `graph_mrr`).
    *   Staleness/Konsistenz (`canonical_dump_index_sha256`) wird beim Laden verifiziert (`stale_or_mismatched`).
*   **Context-Bundle & Output-Profile (Phase 4):**
    *   Hit, Evidence (Snippet) und Context (`graph_context`) sind klar getrennt.
    *   Context-Expansion (exact, window) ist implementiert und erzeugt gültige `query_context_bundle.json` Projektionen.
    *   Die Provenance (explicit `range_ref` vs derived `derived_range_ref`) bleibt stabil.
    *   Output-Profile (`human_review`, `agent_minimal`, `ui_navigation`) filtern interne Status-Variablen sicher heraus (`test_ui_payload_excludes_internal_fields`, `test_agent_minimal_profile_contract`).
    *   API-Endpunkte (FastAPI, `service/app.py`) stellen die Runtime-Artefakte HTTP-sicher bereit (`/api/artifacts`, `/api/artifacts/{id}/download`).
    *   Ein rudimentäres WebUI (`app.js`, `index.html`) visualisiert Treffer, Explain, Graph-Status (Badges) und bietet Download-Möglichkeiten.

## 2. Was ist in der Blaupause abgehakt, aber "nur" strukturell oder unvollständig belegt?
*(Hier drohte Architektur-Drift durch vorzeitige "Fertig"-Meldungen)*

*   **"Phase 4 ist fertig" (Gate 4):**
    *   *Korrektur:* Das Gate wurde im Audit belassen (oder neu gesetzt), weil die Tests für *Context-Nutzbarkeit* (`test_context_bundle.py`) die Output-Profile tief genug validieren (dass z.B. das Profil "agent_minimal" keine Interna leakt und Provenance bewahrt). Die API-Struktur ist stabil. Die WebUI ist "nicht als Spielzeug" konzipiert, da sie Artefakt-Downloads (`key=primaryJsonKey` etc.) und Badge-Systeme (`lexical`, `graph`, `failed`) voll integriert. Phase 4 gilt als "weitgehend belastbar", nicht nur strukturell.

## 3. Was fehlt komplett (Echte Inkonsistenzen / Nicht-Ziele)?
*(Diese Aspekte sind in der Blaupause definiert, aber im Code nicht existent. Sie dürfen nicht übersprungen werden, wenn sie benötigt werden)*

*   **Phase 5 (Cross-Repo-Knowledge-Layer):** Weder Modelle (`federation_index.json`, `cross_repo_links.json`, `federation_conflicts.json`) noch Code für föderierte Queries (`federated_query`) existieren. Lenskit ist Stand jetzt eine strikt lokalisierte (Single-Repo/Single-Bundle) Query-Runtime.
*   **Phase 6 (Agent Control Surface - Session Trace):** Ein explizites `agent_query_session.json` (Session Trace) Artefakt wird noch nicht geschrieben, obwohl der API-Endpoint (`/query`) existiert.

## 4. Fazit & Empfehlung für Phase 5
Lenskit ist für isolierte Bundles (Phase 1-4) deterministisch, contract-sicher und runtime-stabil. Der Übergang zu Phase 5 (Föderation) ist nun sicher möglich, da die Grundlagen (wie der Graph, Context-Bundles und Explain-Konsistenz) nicht mehr "driften" können. Phase 0 liefert ab sofort die statische Referenzkarte für alle folgenden Multi-Bundle-Erweiterungen.