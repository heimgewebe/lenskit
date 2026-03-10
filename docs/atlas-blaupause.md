# Atlas-Blaupause

Atlas soll kein Repo-Spezialscanner mit etwas Dateisystemdeko werden, sondern ein maschinenweiter Dateiatlas mit Zeitgedächtnis: PC, Heimserver, externe Platten, Backups, später auch weitere Hosts.

**Die tragfähige Lösung ist:**
Atlas = physische Wahrnehmungsschicht + Snapshot-Gedächtnis + optionale Inhaltserschließung.

Darauf setzen Retrieval, Analyse, Visualisierung und Agentenlogik auf. Lenskit bleibt die Denkmaschine; Atlas bleibt das Beobachtungsorgan. Atlas ist im README ausdrücklich als vom Repository-Inspektionspfad getrennte Dateisystem-Erkundung beschrieben, inklusive Root-Modell für `preset`, `token` und `abs_path`.

---

## Teil 1: Mandat, Zielbild, Invarianten, Bounded Context

### 1. Ausgangslage: Was Atlas laut aktuellem Repo bereits ist
Atlas ist bereits als Filesystem Exploration Tool angelegt, nicht primär als Repo-Scanner. Das README trennt Atlas explizit von der Repository-Aufbereitung und nennt das Scannen ganzer Systeme als Ziel. Gleichzeitig werden volatile/pseudo-Dateisysteme standardmäßig ausgeschlossen.

Im aktuellen Stand existieren außerdem bereits:
- Ein formales Root-Modell (`preset`, `token`, `abs_path`) statt stiller Fallbacks, inklusive strikter Ablehnung relativer/manipulativer Pfade auf API-Ebene; die WebUI fängt ungültige manuelle Eingaben bereits vor dem Request ab.
- Eine Atlas-Planungsschicht `merger/lenskit/atlas/planner.py`, die Artefakte nach `scan_mode` plant:
  - `inventory` → summary + inventory + dirs
  - `topology` → summary + topology
  - `content` → summary + inventory + content
  - `workspace` → summary + workspaces + hotspots
- Testabdeckung für diese Modus-Artefakte in `test_atlas_planner.py`, inklusive `write_mode_outputs` für Topology-, Content-, Workspaces- und Hotspots-Artefakte.
- Insgesamt ein stark testdominiertes Repo.

### 2. Primärmandat von Atlas

#### 2.1 Kernauftrag
Atlas soll die physische Realität der Maschinen explizit und historisierbar erfassen:
- Welche Dateien gibt es?
- Wo liegen sie?
- Wie groß sind sie?
- Was hat sich verändert?
- Was ist textuell/inhaltlich zugänglich?
- Welche Maschinen- und Root-Kontexte gehören dazu?

Atlas ist Dateisystem-Observatorium, nicht Repo-Kognition.

#### 2.2 Sekundäraufträge
Sekundär darf Atlas:
- Repos und Workspaces erkennen
- Inhalte extrahieren
- Hotspots berechnen
- Topologien ableiten
- Deltas zwischen Snapshots berechnen
- Agenten mit Rohwirklichkeit versorgen

Das sind Aufbauten, nicht das Mandat selbst.

#### 2.3 Was Atlas ausdrücklich nicht sein soll
Atlas soll primär **nicht** sein:
- Git-Analyse-Engine
- Code-Intelligence-Monolith
- IDE-Ersatz
- Monolithischer Agenten-Orchestrator
- Bloßer Repo-Bundler mit Dateisystem-Nebenfunktion

Ein wenig Repo-/Workspace-Erkennung ist legitim, aber nur als Annotation auf einem globalen Dateiatlas.

### 3. Zielbild: Atlas als Maschinen-Gedächtnis

Atlas soll zum globalen Dateisystem-Gedächtnis der Infrastruktur werden.
Nicht nur: "Was ist jetzt da?"
Sondern:
- "Was war da?"
- "Was ist gewachsen?"
- "Was fehlt zwischen Maschine A und B?"
- "Welche Wissensräume existieren physisch?"
- "Welche Inhalte sind neu, alt, doppelt, vergessen, relevant?"

Atlas speichert Zustände, vergleicht Zeiten und macht Dateirealität historisch navigierbar. Scanner ohne Gedächtnis sind austauschbar. Gedächtnisse nicht.

### 4. Die drei verbindlichen Architekturentscheidungen

#### 4.1 Entscheidung A: Atlas ist zustandsbehaftet
Atlas ist kein bloßer Lauf, sondern erzeugt persistente Zustände: `scan_result`, `snapshot`, `delta`, später evtl. `history_view`.
Jeder Scan muss in diese Denkform gebracht werden: `scan -> snapshot -> optional compare/delta -> index/derive`.

#### 4.2 Entscheidung B: Atlas ist dateizentriert
Der stabile Kern ist: Pfad, Datei, Verzeichnis, Größe, Zeit, Eigentümer, Typ, Hash, Root, Maschine.
Inhalte, Semantik, Klassifikation sind optionale obere Schichten. `content` darf nie Pflichtkern der Erfassung werden.

#### 4.3 Entscheidung C: Atlas ist Pipeline, kein Monolith
Die richtige Form ist:
1. Discovery
2. Snapshot/Persistenz
3. Enrichment
4. Derivation
5. Indexing
6. Serving / Retrieval / Automation

### 5. Bounded Context: Wofür Atlas zuständig ist

**A. Physische Dateirealität**
Dateibäume, Verzeichnisse, Root-Kontexte, Dateimetadaten, Größen- und Zeitrealität.

**B. Historisierung**
Snapshots, Deltas, Datei-Historien, Root-Historien, Maschinenvergleiche.

**C. Selektive Inhaltserschließung**
Textklassifikation, MIME/Encoding, line_count, Volltext-Extraktion, Chunking-Vorbereitung, minimale Medienmetadaten.

**D. Systemanalytik**
Top-Dirs, große Dateien, Duplikate, alte Dateien, orphaned Bereiche, Hotspots.

**E. Exportierte Artefakte**
inventory, dirs inventory, summary, topology, content, workspaces, hotspots, später snapshots/deltas/history/search-indizes.

*(Nicht zuständig für: Semantische Tiefeninterpretation, politische Systemlogik, vollständige Git-Historienanalyse, UI-zentrierte Wahrheitsdefinition).*

### 6. Kerninvarianten
1. **Atlas ist maschinenweit**: Darf nie stillschweigend auf "Repo = Welt" reduziert werden.
2. **Roots sind explizit**: Kein stilles Fallback (Root-Modell).
3. **Discovery bleibt vom Enrichment trennbar**: Ein schneller, grober Scan muss möglich sein.
4. **Snapshot vor Erklärung**: Erst Realität speichern, dann interpretieren.
5. **Repo-/Workspace-Erkennung ist Annotation**: Nicht Primärobjekt.
6. **Höhere Artefakte sind ableitbar**: Hotspots, Topology, etc. müssen aus Kernartefakten hervorgehen.
7. **Atlas bleibt Source-of-Truth für physische Dateiwirklichkeit**.

### 7. Ontologie von Atlas

#### 7.1 Primäre Entitäten
- **Machine**: `machine_id`, `hostname`, `kind`, `os_family`, `arch`, `observed_at`.
- **Root**: `root_id`, `machine_id`, `root_kind`, `root_value`, `filesystem`, `mountpoint`, `label`.
- **Snapshot**: `snapshot_id`, `machine_id`, `root_id`, `created_at`, `scan_config_hash`, `inventory_ref`, `dirs_ref`, `stats_ref`, ...
- **FileEntity** (optional/später): Über Zeit wiedererkennbare Datei-Entität (`entity_id`, `canonical_rel_path`, `stable_fingerprint`).
- **FileObservation**: Beobachtung einer Datei in einem Snapshot (`snapshot_id`, `rel_path`, `size`, `mtime`, `is_symlink`, etc.).
- **DirectoryObservation**: `snapshot_id`, `rel_path`, `depth`, `kept_file_count`, `recursive_bytes`, `child_dirs`.
- **Delta**: `from_snapshot_id`, `to_snapshot_id`, `new_files`, `removed_files`, `changed_files`, `summary`.

#### 7.2 Sekundäre Entitäten
WorkspaceAnnotation, HotspotReport, TopologyProjection, DuplicateSet, SearchIndexArtifact, KnowledgeClusterProjection.

### 8. Schichtenmodell
- **Schicht A – Discovery Layer**: Erfasst Pfade, Dateitypen, Basisstats (`inventory.jsonl`, `dirs.jsonl`, `summary.md`).
- **Schicht B – Snapshot Layer**: Persistiert Zustände (`snapshot_meta.json`, Snapshot-Registry, Delta-Registry).
- **Schicht C – Enrichment Layer**: Zusatzwissen pro Datei (`content.json`, `media.json`, `workspace_annotations.json`).
- **Schicht D – Derivation Layer**: Abgeleitete Sichten (`topology.json`, `hotspots.json`, `duplicates.json`, `history_views.json`).
- **Schicht E – Index Layer**: Suchen, Filtern (`FTS`, `Chunk-Index`, `Semantik-Index`).
- **Schicht F – Integration Layer**: Exports für andere Agenten, UI.

---

## Teil 2: Datenmodell, Artefaktformate, Speicher- und Indexschichten

### 1. Architektur-Prinzipien
1. **Append-first statt mutate-first**: Beobachtungen als neue Zustände speichern.
2. **Artefaktzentrierung**: Alles Relevante existiert als explizites Artefakt.
3. **Ableitbarkeit vor Sonderwissen**: Höhere Sichten aus Kernartefakten ableiten.
4. **Host-/Root-/Snapshot-Trennung**: Maschine, Root und Zeitpunkt dürfen nie verschwimmen.
5. **Kleine Wahrheit zuerst**: Rohinventar vor Semantik, Snapshot vor Analyse, Analyse vor UI.

### 2. Snapshot-Mechanik
Jeder Scan erzeugt ein `scan_result`, daraus wird ein persistenter Snapshot.
- **Snapshot-ID-Strategie**: `snap_<machine_id>__<root_id>__<UTC timestamp>__<short config hash>` (z. B. `snap_heim-pc__home__2026-03-10T053519Z__83b1`).
- **Snapshot-Registry**: Eine zentrale Registry-Datei oder Tabelle (SQLite als Registry, Artefakte als Dateien).

### 3. Delta-Mechanik
- **Snapshot-to-Snapshot Delta**: Vergleich zweier Snapshots desselben Roots.
- **Cross-machine Delta**: Vergleich zweier Roots auf unterschiedlichen Maschinen.
- **Time-window Delta**: Vergleich "erste vs letzte Beobachtung in Zeitraum".
- *Rename-Erkennung* ist zunächst nicht Pflichtkern.

### 4. Speicherstrategie
- **Dateien**: Für große Inventare (JSONL), exportierbare Artefakte, versionsfreundliche Outputs.
- **SQLite**: Für Snapshot-Registry, Root-/Machine-Registry, Suchindex, schnelle Metadatenabfragen.

---

## Teil 3: Ausbaupfade und Kernfeatures

### Die 12 Kernfeatures in Priorisierung

1. **Snapshot Registry (kritisch)**: Ohne Registry kein Zeitmodell.
2. **Incremental Scan (kritisch)**: Effiziente Updates durch Vergleiche gegen letzten Snapshot.
3. **File History (sehr hoch)**: Lebenszyklus einer Datei (Erstsichtung, letzte Änderung).
4. **Content Search (sehr hoch)**: Volltextsuche, Preview, strukturierte Parsergebnisse.
5. **Cross-Machine Diff (sehr hoch)**: Vergleich von Roots über verschiedene Maschinen hinweg.
6. **Duplicate Detection (hoch)**: Duplikatgruppen über Maschinen/Roots finden.
7. **Watch-Mode (hoch)**: Live-Erkennung (nach Incrementalität).
8. **Storage Hotspots (hoch)**: Largest dirs, growth hotspots.
9. **Orphan Detection (mittel-hoch)**: Forgotten downloads, dead dirs.
10. **Knowledge Clusters (mittel)**: Navigation und Agenten-Wert.
11. **Semantic File Tags (mittel)**: Document, media, archive, repo.
12. **System Knowledge Map (spät)**: Systemweite Visualisierung.

---

## Teil 4: Verbindliche Architekturentscheidungen und Abhakbare Roadmap

### 1. ADR-artige Setzungen
- **ADR-001**: Atlas is filesystem-first, not repo-first.
- **ADR-002**: Atlas is stateful and snapshot-driven.
- **ADR-003**: Atlas uses pipeline stages, not monolithic scan flows.
- **ADR-004**: Repo/workspace detection is annotation only.
- **ADR-005**: Registry in SQLite, large artifacts as files.
- **ADR-006**: Content enrichment is optional and mode-dependent (`is_text` wird nicht universell garantiert).

### 2. Empfohlene Verzeichnisstruktur
```text
atlas/
  registry/
    atlas_registry.sqlite
  machines/
    heim-pc/
      machine.json
      roots/
        home/
          root.json
          snapshots/
            snap_heim-pc__home__.../
              snapshot_meta.json
              summary.md
              inventory.jsonl
              ...
  indexes/
    fts.sqlite
```

### 3. Abhakbare Roadmap

#### Phase 0 — Konstitution und Contracts
- [ ] ADR-001 bis ADR-006 anlegen.
- [ ] Machine Contract definieren.
- [ ] Root Contract definieren.
- [ ] Snapshot Contract definieren.
- [ ] Inventory Contract definieren.
- [ ] Delta Contract definieren.
- [ ] Mode Output Contract definieren.
- [ ] `is_text`-Garantie explizit dokumentieren.
- [ ] Verzeichnisstruktur offiziell festlegen.

#### Phase 1 — Registry-Kern
- [ ] `atlas_registry.sqlite` einführen.
- [ ] Machine Registry implementieren.
- [ ] Root Registry implementieren.
- [ ] Snapshot Registry implementieren.
- [ ] Snapshot-Status (running/complete/partial/failed) implementieren.
- [ ] Snapshot-Artefakt-Refs konsistent speichern.
- [ ] Snapshot-ID-Schema stabilisieren.
- [ ] CLI: `atlas machines`
- [ ] CLI: `atlas roots`
- [ ] CLI: `atlas snapshots`

#### Phase 2 — Zeitgedächtnis
- [ ] Snapshot-to-Snapshot Delta formal einführen.
- [ ] Delta Registry ergänzen.
- [ ] `from_snapshot_id` / `to_snapshot_id` standardisieren.
- [ ] Sortierte Delta-Listen garantieren.
- [ ] CLI: `atlas diff <snapA> <snapB>`
- [ ] CLI: `atlas history <path>`
- [ ] Datei-Historienmodell definieren.
- [ ] Root-Historienmodell definieren.
- [ ] Zeitfenster-Vergleiche konzipieren.
- [ ] Fehler-/Partial-Delta-Verhalten standardisieren.

#### Phase 3 — Incrementalität
- [ ] Re-Scan gegen letzten Snapshot vorbereiten.
- [ ] mtime-/size-Heuristik definieren.
- [ ] inode/device optional einbeziehen.
- [ ] Selektives Hashing-Modell festlegen.
- [ ] Unveränderte Teilbäume überspringen können.
- [ ] `scan_config_hash` wirksam in Reuse-Logik einbeziehen.
- [ ] Performance-Metriken erfassen.
- [ ] CLI: `atlas scan --incremental`
- [ ] Regressionstests für inkrementelles Verhalten ergänzen.

#### Phase 4 — Suchschicht
- [ ] SQLite-FTS evaluieren und festziehen.
- [ ] Metadaten-Suchschema definieren.
- [ ] Path-Search implementieren.
- [ ] Name-Search implementieren.
- [ ] Extension-/MIME-Search implementieren.
- [ ] Größen-/Datumsfilter implementieren.
- [ ] Content-Search implementieren.
- [ ] Scope-Filter (machine, root, snapshot) implementieren.
- [ ] CLI: `atlas search`
- [ ] Preview-/Snippet-Format definieren.

#### Phase 5 — Inhaltsanreicherung
- [ ] MIME-Typ-Erkennung verbessern.
- [ ] Encoding-Erkennung einführen.
- [ ] `line_count` erfassen.
- [ ] Parser für JSON/YAML/TOML/Markdown/CSV/HTML.
- [ ] Medien-Minimalmetadaten (Bilddimensionen, Audio-/Video-Dauer).
- [ ] Preview-/Chunk-Artefakte definieren.
- [ ] Content-Policy pro Root ermöglichen.
- [ ] Binary-/Huge-file-Strategie klären.
- [ ] Tests für modeabhängige Inhaltsfelder ergänzen.

#### Phase 6 — Analyseartefakte
- [ ] Hotspots erweitern um Growth-/Change-Achsen.
- [ ] Duplicate Detection (size prefilter + hash confirm).
- [ ] `duplicates.json` definieren.
- [ ] Orphan Detection definieren.
- [ ] `analyze disk` standardisieren.
- [ ] `analyze duplicates` implementieren.
- [ ] `analyze orphan` implementieren.
- [ ] Oldest-/Largest-Files-Artefakte vereinheitlichen.
- [ ] Cross-root growth reports definieren.

#### Phase 7 — Multi-Machine-Atlas
- [ ] Mehrere Machines sauber registrieren.
- [ ] Root-Namenskonventionen zwischen Hosts vereinheitlichen.
- [ ] Cross-machine snapshot diff definieren.
- [ ] CLI: `atlas diff heim-pc:/home heimserver:/home`
- [ ] Backup-gap-Analyse definieren.
- [ ] Remote-Collector-/SSH-Modell festlegen.
- [ ] Konfliktfälle (gleiches root label, andere Pfade) definieren.
- [ ] Maschinen-Health-/Last-Seen-Sicht ergänzen.

#### Phase 8 — Watch-Mode und Chronik-Anbindung
- [ ] Watch-Mode-Modell definieren.
- [ ] inotify/fanotify-Strategie evaluieren.
- [ ] Event-Schema für Dateiänderungen definieren.
- [ ] Debounce-/Batching-Logik definieren.
- [ ] Chronik-kompatiblen Exportpfad bauen.
- [ ] CLI: `atlas watch /path`
- [ ] Snapshot-/Event-Verhältnis klären.
- [ ] Watch-Failure-Recovery definieren.

#### Phase 9 — Wissenskarte
- [ ] Knowledge-Cluster-Modell definieren.
- [ ] Systemweite Kategorien bestimmen.
- [ ] `atlas map` Output-Format festlegen.
- [ ] Root-/Machine-Karten definieren.
- [ ] Cluster-Heuristiken bauen.
- [ ] Semantische Dateitags ergänzen.
- [ ] UI-/Exportformate für Karten vorbereiten.
