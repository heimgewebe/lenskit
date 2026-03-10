# Lenskit Upgrade Blaupause

## Zielbild
Lenskit entwickelt sich von einem Repository-Analyse-Tool zu einem **deterministischen Knowledge-Compiler mit Query-Runtime und portablem Knowledge-Bundle-Format**.

**Systemprinzipien:**
- Deterministic analysis
- Contracts first
- Artifact centric
- Reproducible bundles
- Agent ready outputs

Das System durchsucht Repositories nicht einfach; es kompiliert sie zu prüfbarem, nachvollziehbarem Wissen.

---

## Entwicklungsphasen & Roadmap

### Phase 0 – Konsolidierter Ist-Stand
*(Bereits vorhanden bzw. weitgehend belegt)*
- [x] Repo-Scanning
- [x] Path-Security
- [x] Extraction & Zone-Marker-/Offset-Logik
- [x] Chunking & JSONL-Chunk-Index
- [x] SQLite-FTS/BM25-Retrieval
- [x] Bundle-Manifest / Dump-Index / Derived-Index
- [x] Range-Resolution
- [x] Architektur-/Import-Analyse
- [x] Graph-Index-Erzeugung und Bundle-Einbindung
- [x] Graph-aware Runtime-Nutzung
- [x] WebUI/Service-Grundlage
- [x] Umfangreiche Tests

---

### Phase 1 – Contract- und Provenance-Härtung
**Ziel:** Artefakte semantisch und vertraglich präzise definieren.
- [ ] **Contract-Inventur:** Alle Artefakte inventarisieren, Owner/Produzenten/Konsumenten definieren und Contract-Lücken aufdecken.
- [ ] **Provenance-Vollständigkeit:** Explizite Trennung von `stored ref`, `derived ref` und `fallback ref` in Retrieval-Treffern implementieren.
- [ ] **Query-Result-Contracts schärfen:** Stabile Felder für `hit`, `score`, `why`, `range_ref`, `derived_range_ref`, `warnings` und `diagnostics` vorgeben.
- [ ] **Drift-Gates einrichten:** Tests/Guards gegen Contract-Drift und Schema-Validierung für alle Kernartefakte einführen.
- [ ] **Gate:** Kein zentrales Artefakt muss mehr "implizit verstanden" werden.

---

### Phase 2 – Retrieval-Qualität und Kontextpfad
**Ziel:** Nachvollziehbarer Kontextpfad für jede Query.
- [ ] **Query Trace:** Neues Artefakt (`query_trace.json`) mit Inputs, Filtern, Ranking Stages, Explain Features, Graph Usage, Warnings implementieren.
- [ ] **Context Bundle:** Neues Artefakt (`query_context_bundle.json`) mit Primary Hit, Resolved Text, Surrounding Context, Artifact Refs, Provenance Trail einführen.
- [ ] **Output-Profile etablieren:** Standardisierte Modi implementieren (`lookup_minimal`, `review_context`, `architecture_probe`, `debug_trace`).
- [ ] **Range-Ref-Disziplin durchsetzen:** `bundle-backed range_ref` nur contract-konform einsetzen, Split-Mode-Regeln explizit machen, Resolver-Kompatibilität sichern.
- [ ] **Gate:** Jede Query liefert nicht nur Ergebnisse, sondern ihren eigenen Belegpfad mit.

---

### Phase 3 – Graph-Runtime-Konsolidierung
**Ziel:** Graph als stabile, erklärbare Runtime-Schicht etablieren.
- [ ] **Graph-Contract finalisieren:** `graph_index.json` semantisch festziehen, Distanz- und Entrypoint-Definitionen verbindlich machen.
- [ ] **Explain-/Ranking-Konsistenz:** Graph-aware Explain-Felder vereinheitlichen, Graph Penalty/Boost mathematisch transparent machen.
- [ ] **Eval-Pfad komplettieren:** Graph-Nutzung in Eval robust ausweisen (Graph-aware vs. Non-Graph Compare).
- [ ] **Graph-Diagnostik:** Erkennung für Invalid Graph, Stale Graph, Missing Entrypoints, Partial Graph Coverage implementieren.
- [ ] **Gate:** Graph fungiert deterministisch und konsistent als überprüfbare Evidenzschicht.

---

### Phase 4 – Föderationsfundament
**Ziel:** Mehrere Bundles formal zusammenführen ohne Vermischung.
- [ ] **Federation Index:** Neues Artefakt (`federation_index.json`) inkl. Bundle/Repo-Sets, Fingerprints, Versioning, Scope/Tags integrieren.
- [ ] **Identity Layer:** Bundle-, Repo-, Path- und Symbol-Identity explizit modellieren.
- [ ] **Cross-Repo-Links:** Neues Artefakt (`cross_repo_links.json`) für Importe, geteilte Contracts, Producer/Consumer, Code/Docs und Entrypoint-Relationen definieren.
- [ ] **Conflict Model:** Artefakt (`federation_conflicts.json`) zur Strukturierung von Version-, Ownership-, Stale- oder Duplicate-Konflikten bereitstellen.
- [ ] **Gate:** Bundles sind zusammen adressierbar, ohne ihre jeweilige Herkunft zu verlieren oder stille Wahrheitsverschmelzung auszulösen.

---

### Phase 5 – Föderierte Query
**Ziel:** Bundle-übergreifende Suche mit lokaler Trennschärfe.
- [ ] **Federated Query Contract:** API-Schnittstelle definieren (Query, Bundle Scope, Repo Filter, Context Mode, Explain Level -> Hits/Bundle, Ranking, Provenance).
- [ ] **Föderiertes Ranking:** Lokale Scores beibehalten, globale Normalisierung und Tie-Breaks transparent aufbauen.
- [ ] **Cross-Repo-Context:** Primary Evidence, Related Evidence und Relation Context ermöglichen.
- [ ] **Federation Trace:** Trace-Artefakt (`federation_trace.json`) für föderierte Anfragen implementieren.
- [ ] **Gate:** Bundleübergreifende Suche funktioniert und meldet Konflikte explizit.

---

### Phase 6 – Agent Control Surface
**Ziel:** Kontrollierte, vertragsbasierte Agent-Nutzung.
- [ ] **Agent Query Contract:** Maschinenlesbare Request-/Response-Struktur für Agenten festlegen.
- [ ] **Bounded Tool Surface:** Erlaubte Operationen strikt auf Query, Context, Trace, Artifact Lookup, Federation Query, Diagnostics begrenzen.
- [ ] **Agent Session Trace:** Artefakt (`agent_query_session.json`) zur Nachvollziehbarkeit von Agent-Interaktionen einführen.
- [ ] **Uncertainty-/Provenance-Felder:** Maschinenlesbare Marker für Interpolation, Fallback-Nutzung, Resolver/Graph/Federation Status hinzufügen.
- [ ] **Guardrails:** Warnsystem für Stale Bundle, Fallback-only Provenance, Conflicts, Low Evidence Density aufbauen.
- [ ] **Gate:** Agenten nutzen Lenskit über formale Strukturen; Lenskit liefert reine Evidenz, nicht die Interpretation.

---

### Phase 7 – UI / Service / Produktisierung
**Ziel:** Operative Nutzbarkeit ohne Architekturverwässerung.
- [ ] **WebUI-Konsolidierung:** Bundle Navigation, Trace Ansicht, Explain Ansicht, Artifact Explorer integrieren.
- [ ] **Diagnostic Views:** Oberflächen für Graph Health, Federation Conflicts, Bundle Provenance, Query Trace bereitstellen.
- [ ] **Service-Endpunkte:** API-Endpunkte (`/query`, `/context`, `/trace`, `/artifact`, `/federation/query`, `/diagnostics`) härten.
- [ ] **Download-/Inspection-Flows:** Workflows für Traces, Bundles, Diagnostics einrichten.
- [ ] **Gate:** Lenskit ist operativ optimal einsetzbar und diagnostizierbar.

---

### Phase 8 – Semantische Erweiterung
**Ziel:** Semantik auf stabiler, nachvollziehbarer Architektur aufbauen.
- [ ] **Semantischer Reranker produktionsreif:** Modell, deterministische Policy und Fallback-Regeln etablieren.
- [ ] **Symbolische Auflösung:** Cross-Repo-Symbolbezüge und Referenzketten ausbauen.
- [ ] **Semantik + Graph kombiniert:** Relation-aware Rerank und Architecture-aware Expansion einführen.
- [ ] **Eval-Härtung:** Evaluierungspfade ausbauen (Baseline vs Semantic, Graph vs Non-Graph, Federated vs Local).
- [ ] **Gate:** Semantik dient als messbare Architekturverbesserung, evaluiert auf solider Grundlage.

---

## Empfohlene PR-Reihenfolge
- [ ] **PR 1:** Contract-/Provenance-Härtung
- [ ] **PR 2:** Query Trace + Context Bundle
- [ ] **PR 3:** Graph Runtime Konsolidierung
- [ ] **PR 4:** Federation Foundation
- [ ] **PR 5:** Federated Query + Ranking
- [ ] **PR 6:** Agent Control Surface
- [ ] **PR 7:** UI / Service Konsolidierung
- [ ] **PR 8:** Semantische Erweiterung
