# Atlas-Blaupause

## These
Atlas soll kein Repo-Spezialscanner mit etwas Dateisystemdeko werden, sondern ein maschinenweiter Dateiatlas mit Zeitgedächtnis: PC, Heimserver, externe Platten, Backups, später auch weitere Hosts.

## Antithese
Wenn Atlas zu viel auf einmal tut, droht der klassische Werkzeugtod: ein Scanner, der alles können soll und deshalb vor allem langsam, teuer und epistemisch verwirrt wird. Der Dateibaum wird dann zum Opfer seiner eigenen Ambitionen – eine Art digitaler Messie mit Index.

## Synthese
Die tragfähige Lösung ist:
**Atlas = physische Wahrnehmungsschicht + Snapshot-Gedächtnis + optionale Inhaltserschließung**

Darauf setzen Retrieval, Analyse, Visualisierung und Agentenlogik auf. Lenskit bleibt die Denkmaschine; Atlas bleibt das Beobachtungsorgan. Das passt auch zum aktuellen Repo-Stand: Atlas ist im README ausdrücklich als vom Repository-Inspektionspfad getrennte Dateisystem-Erkundung beschrieben, inklusive Root-Modell für `preset`, `token` und `abs_path`.

---

# Teil 1/4: Mandat, Zielbild, Invarianten, Bounded Context

Dieses Fundament sichert ab, dass spätere Features stabil aufgebaut werden können.

## 1. Ausgangslage: Was Atlas laut aktuellem Repo bereits ist
Der aktuelle Stand im Repo zeigt: Atlas ist bereits als Filesystem Exploration Tool angelegt, also gerade nicht primär als Repo-Scanner. Das README trennt Atlas explizit von der Repository-Aufbereitung und nennt das Scannen ganzer Systeme als Ziel. Gleichzeitig werden volatile/pseudo-Dateisysteme standardmäßig ausgeschlossen.

Im aktuellen Stand existieren außerdem bereits:
* ein formales Root-Modell (`preset`, `token`, `abs_path`) statt stiller Fallbacks, inklusive strikter Ablehnung relativer/manipulativer Pfade auf API-Ebene; die WebUI fängt ungültige manuelle Eingaben bereits vor dem Request ab.
* eine Atlas-Planungsschicht `merger/lenskit/atlas/planner.py`, die Artefakte nach `scan_mode` plant:
  * `inventory` → summary + inventory + dirs
  * `topology` → summary + topology
  * `content` → summary + inventory + content
  * `workspace` → summary + workspaces + hotspots
* Testabdeckung für diese Modus-Artefakte in `test_atlas_planner.py`, inklusive `write_mode_outputs` für Topology-, Content-, Workspaces- und Hotspots-Artefakte.
* insgesamt ein stark testdominiertes Repo: 113 Testdateien bei 254 Textdateien laut Architektur-Snapshot.

Die Blaupause dockt an diese vorhandenen Achsen an.

## 2. Primärmandat von Atlas

### 2.1 Kernauftrag
Atlas soll die physische Realität deiner Maschinen explizit und historisierbar erfassen:
* Welche Dateien gibt es?
* Wo liegen sie?
* Wie groß sind sie?
* Was hat sich verändert?
* Was ist textuell/inhaltlich zugänglich?
* Welche Maschinen- und Root-Kontexte gehören dazu?

Atlas ist damit Dateisystem-Observatorium, nicht Repo-Kognition.

### 2.2 Sekundäraufträge
Sekundär darf Atlas:
* Repos und Workspaces erkennen
* Inhalte extrahieren
* Hotspots berechnen
* Topologien ableiten
* Deltas zwischen Snapshots berechnen
* Lenskit/Heimgeist/HausKI mit Rohwirklichkeit versorgen

Das sind Aufbauten, nicht das Mandat selbst.

### 2.3 Was Atlas ausdrücklich nicht sein soll
Atlas soll nicht primär sein:
* Git-Analyse-Engine
* Code-Intelligence-Monolith
* IDE-Ersatz
* monolithischer Agenten-Orchestrator
* bloßer Repo-Bundler mit Dateisystem-Nebenfunktion

Ein wenig Repo-/Workspace-Erkennung ist legitim, aber nur als Annotation auf einem globalen Dateiatlas. Sobald Repo-Strukturen die primäre Ontologie werden, ist Atlas konzeptionell bereits halb auf Abwegen. Der aktuelle Repo-Stand zeigt zwar Workspace-/Hotspot-/Topology-Artefakte, aber das README hält die Trennung zur Repo-Pipeline weiterhin klar fest. Das ist als Invariante zu konservieren.

## 3. Zielbild: Atlas als Maschinen-Gedächtnis

### 3.1 Kurzform
Atlas soll zum globalen Dateisystem-Gedächtnis deiner Infrastruktur werden.

Nicht nur: *„Was ist jetzt da?“*
Sondern:
* „Was war da?“
* „Was ist gewachsen?“
* „Was fehlt zwischen Maschine A und B?“
* „Welche Wissensräume existieren physisch?“
* „Welche Inhalte sind neu, alt, doppelt, vergessen, relevant?“

### 3.2 Die entscheidende Sinnachse
Es gibt zwei mögliche Zielachsen:
* **Achse A – Scanner-Logik**: Atlas scannt Dateibäume und liefert Inventare.
* **Achse B – Gedächtnis-Logik**: Atlas speichert Zustände, vergleicht Zeiten und macht Dateirealität historisch navigierbar.

Die Blaupause entscheidet sich klar für **Achse B**. Scanner ohne Gedächtnis sind austauschbar. Gedächtnisse nicht. Der Computer weiß sonst immer nur „jetzt“. Atlas soll „jetzt“, „vorher“ und „Veränderung“ zugleich wissen.

## 4. Die drei verbindlichen Architekturentscheidungen

### 4.1 Entscheidung A: Atlas ist zustandsbehaftet
Atlas ist kein bloßer Lauf, sondern erzeugt persistente Zustände: `scan_result`, `snapshot`, `delta`, später evtl. `history_view`.

Jeder Scan muss also mindestens in diese Denkform gebracht werden:
`scan -> snapshot -> optional compare/delta -> index/derive`

**Konsequenz**: Ohne Snapshot-IDs, Root-IDs und Machine-IDs wird Atlas später nicht wachsen, sondern nur größer werden.

### 4.2 Entscheidung B: Atlas ist dateizentriert
Der stabile Kern ist nicht „Bedeutung“, sondern: Pfad, Datei, Verzeichnis, Größe, Zeit, Eigentümer, Typ, Hash, Root, Maschine.
Inhalte, Semantik, Klassifikation sind optionale obere Schichten.

**Konsequenz**: `content` darf nie Pflichtkern der Erfassung werden. Sonst kippt Performance, Speicherverbrauch und Komplexität.

### 4.3 Entscheidung C: Atlas ist Pipeline, kein Monolith
Die richtige Form ist:
1. Discovery
2. Snapshot/Persistenz
3. Enrichment
4. Derivation
5. Indexing
6. Serving / Retrieval / Automation

Der aktuelle `scan_mode`-Ansatz geht bereits in diese Richtung, weil unterschiedliche Artefakte gezielt geplant und geschrieben werden. Diese Tendenz sollte ausgebaut werden.

## 5. Bounded Context: Wofür Atlas zuständig ist

### 5.1 Atlas ist zuständig für
* **A. Physische Dateirealität**: Dateibäume, Verzeichnisse, Root-Kontexte, Dateimetadaten, Größen- und Zeitrealität
* **B. Historisierung**: Snapshots, Deltas, Datei-Historien, Root-Historien, Maschinenvergleiche
* **C. Selektive Inhaltserschließung**: Textklassifikation, MIME/Encoding, line_count, Volltext-Extraktion, Chunking-Vorbereitung, minimale Medienmetadaten
* **D. Systemanalytik**: Top-Dirs, große Dateien, Duplikate, alte Dateien, orphaned Bereiche, Hotspots
* **E. Exportierte Artefakte**: inventory, dirs inventory, summary, topology, content, workspaces, hotspots, später snapshots/deltas/history/search-indizes

### 5.2 Atlas ist nicht zuständig für
* **A. Semantische Tiefeninterpretation**: Dafür sind Lenskit, Heimgeist, HausKI besser geeignet.
* **B. Politische oder organisatorische Systemlogik**: Nicht Atlas’ Aufgabe.
* **C. Vollständige Git-Historienanalyse**: Atlas darf Repos erkennen, aber nicht in seinem Kern von Git abhängen.
* **D. UI-zentrierte Wahrheitsdefinition**: Die WebUI ist Konsument, nicht Kanon.

## 6. Kerninvarianten

1. **Invariante 1 – Atlas ist maschinenweit**: Atlas darf nie stillschweigend auf „Repo = Welt“ reduziert werden.
2. **Invariante 2 – Roots sind explizit**: Kein stilles Fallback, keine implizite Magie. Das aktuelle Root-Modell wird beibehalten.
3. **Invariante 3 – Discovery bleibt vom Enrichment trennbar**: Ein schneller, grober Scan muss immer möglich sein.
4. **Invariante 4 – Snapshot vor Erklärung**: Erst Realität speichern, dann interpretieren.
5. **Invariante 5 – Repo-/Workspace-Erkennung ist Annotation**: Nicht Primärobjekt.
6. **Invariante 6 – Höhere Artefakte sind ableitbar**: Hotspots, Topology, Content, Workspaces dürfen keine isolierten Sonderwelten sein, sondern müssen aus Kernartefakten oder klaren Enrichment-Stufen hervorgehen.
7. **Invariante 7 – Atlas bleibt source-of-truth für physische Dateiwirklichkeit**: Nicht Git, nicht Index-UI, nicht Agentenlogik.

## 7. Ontologie von Atlas

### 7.1 Primäre Entitäten

* **Machine**: Eine physische oder virtuelle Maschine. Felder: `machine_id`, `hostname`, `kind`, `os_family`, `arch`, `observed_at`.
* **Root**: Ein expliziter Scan-Root. Felder: `root_id`, `machine_id`, `root_kind`, `root_value`, `filesystem`, `mountpoint`, `label`.
* **Snapshot**: Ein persistenter Zustand eines Roots zu einem Zeitpunkt. Felder: `snapshot_id`, `machine_id`, `root_id`, `created_at`, `scan_config_hash`, `inventory_ref`, `dirs_ref`, `stats_ref`, `content_ref?`, `topology_ref?`, `workspaces_ref?`, `hotspots_ref?`.
* **FileEntity**: Die über Zeit wiedererkennbare Datei-Entität. Felder: `entity_id`, `machine_id`, `root_id`, `canonical_rel_path`, `inode?`, `device?`, `stable_hash?`.
* **FileObservation**: Beobachtung einer Datei in einem Snapshot. Felder: `snapshot_id`, `rel_path`, `size`, `mtime`, `ctime?`, `owner`, `group`, `permissions`, `ext`, `mime`, `is_symlink`, `is_text?`, `encoding?`, `line_count?`, `checksum?`.
* **DirectoryObservation**: Beobachtung eines Verzeichnisses.
* **Delta**: Differenz zwischen zwei Snapshots. Felder: `from_snapshot_id`, `to_snapshot_id`, `new_files`, `removed_files`, `changed_files`, `renamed_files?`, `summary`.

### 7.2 Sekundäre Entitäten
* WorkspaceAnnotation
* HotspotReport
* TopologyProjection
* DuplicateSet
* SearchIndexArtifact
* KnowledgeClusterProjection

## 8. Schichtenmodell

* **Schicht A – Discovery Layer**: Erfasst Pfade, Dateitypen, Basisstats (`inventory.jsonl`, `dirs.jsonl`, `summary.md`).
* **Schicht B – Snapshot Layer**: Persistiert Zustände als identifizierbare Snapshots (`snapshot_meta.json`, Snapshot-Registry, Delta-Registry).
* **Schicht C – Enrichment Layer**: Zusatzwissen pro Datei/Verzeichnis (`content.json`, `media.json`, `workspace_annotations.json`).
* **Schicht D – Derivation Layer**: Abgeleitete Sichten (`topology.json`, `hotspots.json`, `duplicates.json`, `history_views.json`).
* **Schicht E – Index Layer**: Suchen, Filtern, Retrieval (`FTS`, `Chunk-Index`, `Semantik-Index`).
* **Schicht F – Integration Layer**: Exports für Lenskit, Heimgeist, HausKI, Chronik, UI.

## 9. Soll-Ist-Abgleich zum aktuellen Repo-Stand

* **Bereits vorhanden**: Root-Modell (`preset`, `token`, `abs_path`), Scan-Modi (`inventory`, `topology`, `content`, `workspace`), Artefakt-Planung per `planner.py`, Artefakt-Ausgabe für Topology/Content/Workspaces/Hotspots, Testpfad für Atlas-Modi und Planner-Ausgaben.
* **Teilweise vorhanden / im Übergang**: Workspace-/Hotspot-/Topology-Ableitungen im Scannerpfad, Content-Statistik selektiv nach `scan_mode=content`, Snapshot-/Delta-Denken ist konzeptionell angelegt, aber noch nicht als vollständiges Zeitmodell durchgezogen.
* **Fehlend / blaupausenreif**: Multi-Machine-Root-Registry, explizite Snapshot-Registry, konsistente File-Entity-Identität, Datei-Historie über viele Snapshots, Cross-machine diff, Duplicate Detection, Watch-Mode, inkrementelles Re-Scanning, Suchschicht mit Query-API, Trennung zwischen Root-Atlas und Repo-Annotation noch expliziter machen.

## 10. Entscheidungsmatrix & Essenz Teil 1

Atlas ist das historische, maschinenweite Gedächtnis der physischen Dateiwelt; Repo-/Workspace-Strukturen sind darin nur bedeutungsvolle Sonderformen, nicht die Leitontologie.
1. Atlas ist zustandsbehaftetes Maschinen-Gedächtnis.
2. Kern ist dateizentriert.
3. Enrichment ist optional.
4. Pipeline über Monolith.
5. Repos sind Annotation, nicht Weltmodell.

---

# Teil 2/4: Datenmodell, Artefaktformate, Snapshot-/Delta-Mechanik, Storage-Strategie

## 1. Architektur-Prinzipien für Teil 2
1. **Append-first statt mutate-first**: Beobachtungen werden bevorzugt als neue Zustände gespeichert.
2. **Artefaktzentrierung**: Alles Relevante existiert als explizites Artefakt (`inventory`, `dirs`, `snapshot meta`, `delta`, `topology`, `content`, `hotspots`, `workspaces`, index artifacts).
3. **Ableitbarkeit vor Sonderwissen**: Höhere Sichten sollen aus Kernartefakten ableitbar sein.
4. **Host-/Root-/Snapshot-Trennung**: Maschine, Root und Zeitpunkt dürfen nie ineinander verschwimmen.
5. **Kleine Wahrheit zuerst**: Rohinventar vor Semantik, Snapshot vor Analyse, Analyse vor UI.

## 2. Kanonisches Datenmodell

### 2.1 Identitäten
* **Machine**: Repräsentiert eine Maschine. Felder: `machine_id`, `hostname` (Pflicht), `kind`, `os_family`, `arch`, `labels`, `last_seen_at` (Optional).
* **Root**: Ein expliziter Scanbereich auf einer Maschine. Felder: `root_id`, `machine_id`, `root_kind`, `root_value` (Pflicht), `filesystem`, `mountpoint`, `label`, `allow_content`, `priority` (Optional).
* **Snapshot**: Historischer Zustand eines Roots. Felder: `snapshot_id`, `machine_id`, `root_id`, `created_at`, `scan_config_hash`, `inventory_ref`/`dirs_ref` (Pflicht). `content_ref`, `topology_ref`, `hotspots_ref`, `workspaces_ref` (Optional).
* **File Entity**: Die über Zeit erkennbare Dateiidentität. Für Phase 1/2 ist `FileObservation` wichtiger. Später: `entity_id`, `machine_id`, `root_id`, `first_seen_snapshot_id`, `canonical_rel_path`, `stable_fingerprint` (checksum, inode, device).

### 3. Beobachtungsmodell
* **FileObservation**: Pflicht (`snapshot_id`, `rel_path`, `size_bytes`, `mtime`, `is_symlink`). Optional (`abs_path_hint`, `ext`, `mime_type`, `ctime`, `is_text`, `encoding`, `line_count`, `checksum`, `owner`, `group`, `permissions`). `rel_path` bleibt die kanonische Pfadachse innerhalb eines Roots.
* **DirectoryObservation**: Pflicht (`snapshot_id`, `rel_path`, `depth`). Optional (`kept_file_count`, `recursive_bytes`, `child_dirs`, `signal_count`).

### 4. Abgeleitete Projektionen
* **Workspaces**: Workspace-Erkennung als Annotation (`workspace_id`, `root_path`, `workspace_kind`, `signals`, `confidence`, `tags`).
* **Hotspots**: Messung von multi-dimensionaler Komplexität (`top_dirs`, `highest_file_density`, `deepest_paths`, `highest_signal_density`).
* **TopologyProjection**: Intermediate Repräsentation der Dateiraum-Topologie (`snapshot_id`, `root_path`, `nodes`).
* **ContentProjection**: (`text_files_count`, `binary_files_count`, `large_files`, `extensions`).

## 5. Snapshot-Mechanik

### 5.1 Snapshot-Erzeugung
Phasen: Root auflösen -> Rohinventar erzeugen -> Basisstats berechnen -> optionale Enrichment-Artefakte erzeugen -> Snapshot-Metadaten schreiben -> Snapshot registrieren.

Minimaler Write: `scan_result` -> `inventory.jsonl` -> `dirs.jsonl` -> `summary.md` -> `snapshot_meta.json` -> `snapshot_registry` append.

### 5.2 Snapshot-ID-Strategie
Format: `snap_<machine_id>__<root_id>__<UTC timestamp>__<short config hash>` (Beispiel: `snap_heim-pc__home__2026-03-10T053519Z__83b1`). Dies ist global unterscheidbar, Root-/Maschinenkontext ist sichtbar.

### 5.3 Snapshot-Registry
Speicherung in einer SQLite-Tabelle, während Artefakte als Dateien im Dateisystem verbleiben (Mischform).

## 6. Delta-Mechanik

### 6.1 Delta-Typen
* **Snapshot-to-Snapshot Delta**: Vergleich zweier Snapshots desselben Roots.
* **Cross-machine Delta**: Vergleich zweier Roots auf unterschiedlichen Maschinen.
* **Time-window Delta**: Vergleich erste vs letzte Beobachtung in Zeitraum.

### 6.2 Delta-Kernstruktur
Pflicht: sortierte Listen, deterministische Ausgabe, klare Referenz auf beide Snapshots. Felder: `delta_id`, `from_snapshot_id`, `to_snapshot_id`, `created_at`, `new_files`, `removed_files`, `changed_files`, `summary`.
Rename-Erkennung (renamed_files) ist zunächst nicht Pflichtkern.

## 7. Artefaktklassen
* **Klasse A – Kernartefakte** (Immer): `inventory.jsonl`, `dirs.jsonl`, `summary.md`, `snapshot_meta.json`.
* **Klasse B – Enrichment-Artefakte** (Optional): `content.json`, `media.json`, `mime_summary.json`, `hashes.jsonl`.
* **Klasse C – Derivation-Artefakte** (Abgeleitet): `topology.json`, `hotspots.json`, `workspaces.json`, `duplicates.json`, `history_views.json`.
* **Klasse D – Index-Artefakte** (Suche/Retrieval): `fts.sqlite`, `chunk_index.sqlite`, `semantic_index/...`.

## 8. Speicherstrategie & Verzeichnisstruktur

### 8.1 Speicherstrategie
Registry + Indizes in SQLite (für Snapshot/Root/Machine Registries und schnelle Suche). Rohartefakte als Dateien (für große Inventare, Versionierung).

### 8.2 Verzeichnisstruktur-Vorschlag
```text
atlas/
  machines/
    heim-pc/
      roots/
        home/
          snapshots/
            snap_.../
              summary.md
              inventory.jsonl
              dirs.jsonl
              content.json
              topology.json
              hotspots.json
              workspaces.json
              snapshot_meta.json
        repos/
          snapshots/...
    heimserver/
      roots/...
  registry/
    atlas_registry.sqlite
  indexes/
    fts.sqlite
    semantic_chunks.sqlite
```

## 9. Index-Strategie
Suchachsen:
* **Dateimetadaten-Suche** (Pfad, Ext, Größe, Root)
* **Inhalts-Suche** (Volltext, Chunks)
* **Historie-Suche** (wann gesehen/geändert).
Backend: Primär SQLite + FTS.

## 10. Contracts, die Atlas künftig braucht
* **Root Contract**: Zulässige Root-Typen, machine_id-Bindung.
* **Snapshot Contract**: Pflichtfelder eines Snapshots, Artefakt-Refs.
* **Inventory Contract**: Pflichtfelder pro Datei. `is_text` wird explizit als optional oder `guaranteed only in content-enabled scans` definiert.
* **Delta Contract**: deterministische Listen, Sortierung.
* **Mode Output Contract**: Welche Artefakte garantiert sind für inventory, topology, content, workspace.

## 11. API-Strategie & Multi-Machine-Universum
* **Kernoperationen**: `atlas scan`, `atlas snapshot`, `atlas derive`, `atlas diff`, `atlas history`, `atlas search`, `atlas machines`, `atlas roots`.
* **Multi-Machine**: Maschine als erste Bürger (heim-pc, heimserver, backup-nas).
* **Root-Klassen**: Lokales FS (/home), Teilroot (/repos), Externe Platte, Remote Root.
* **Cross-Machine Vergleiche**: Root-to-Root, Snapshot-to-Snapshot, Policy Diff.

---

# Teil 3/4: Ausbaupfade, Phasenmodell, Kernfeatures mit höchstem Hebel

## 1. Priorisierungslogik
1. Hebel (Alltagsnutzen)
2. Systemtiefe (Verbessert Kern)
3. Replizierbarkeit (Stabil, testbar)
4. Anschlussfähigkeit (Für Lenskit/HausKI)
5. Drift-Risiko (Fokus auf Kernrolle)

## 2. Die große Ausbau-Roadmap (Phasen A-F)
* **Phase A – Atlas als belastbarer Kernscanner**: Vollständige Inventur, Root/Machine Kontext, Snapshot Erzeugung, Registry.
* **Phase B – Zeitgedächtnis**: Snapshot-Registry, deterministische Deltas, Historie. (Fähigkeiten: `atlas snapshot`, `atlas diff`, `atlas history`).
* **Phase C – Incrementalität und Watch-Mode**: Inkrementelle Re-Scans über mtime/size Filter, Watch-Mode.
* **Phase D – Inhaltszugang und Suchschicht**: Pfad-, Namens-, Content-Suche. (Fähigkeit: `atlas search`).
* **Phase E – Systemanalyse und Cross-Machine Intelligence**: Cross-machine diff, Duplicates, Storage Hotspots, Orphans. (Fähigkeiten: `atlas analyze`).
* **Phase F – Wissenskarte und höhere Projektionen**: Knowledge Clusters, Maps.

## 3. Die 12 Kernfeatures in endgültiger Priorisierung
1. **Snapshot Registry (kritisch)**: Ohne Registry kein Zeitmodell.
2. **Incremental Scan (kritisch)**: Vergleiche gegen letzten Snapshot.
3. **File History (sehr hoch)**: Wann erstmals gesehen, zuletzt geändert.
4. **Content Search (sehr hoch)**: Volltextsuche, Previews.
5. **Cross-Machine Diff (sehr hoch)**: Heim-PC vs Heimserver, Backup-Lücken.
6. **Duplicate Detection (hoch)**: Dateigröße -> Hash -> Gruppenartefakt.
7. **Watch-Mode (hoch)**: Live erkennen nach Incrementalität.
8. **Storage Hotspots (hoch)**: Growth hotspots, largest dirs.
9. **Orphan Detection (mittel-hoch)**: Forgotten downloads, dead dirs.
10. **Knowledge Clusters (mittel)**: Such-/Inhaltsbasis nötig.
11. **Semantic File Tags (mittel)**: document, media, repo.
12. **System Knowledge Map (spät, aber wertvoll)**: Systemweite Visualisierung.

## 4. Duplicate Detection im Detail
Stufe 1 (Size prefilter) -> Stufe 2 (Hash confirmation) -> Stufe 3 (Gruppenartefakt `duplicate_set` über Maschinen/Roots hinweg erzeugen).

## 5. Watch-Mode und Chronik-Integration
Live-Erkennung von Events (file_created, file_modified). Export als Chronik-kompatible Artefakte für Agenten/HausKI.

## 6. Change Intelligence (Zweite Ordnung)
Nicht nur "neue Datei", sondern "wachsendes Verzeichnis", "plötzliche Datenflut", "vergessene Archive". (`atlas analyze changes --since 30d`).

## 7. Repo-/Workspace-Erkennung neu eingeordnet
Marker wie `.git`, `pyproject.toml`, `package.json` definieren keine Hauptwelt. Sie sind eine nützliche Marker-Leseart. Repo-/Workspace-Erkennung bleibt Annotation auf dem globalen Dateiatlas.

## 8. Was bewusst nicht priorisiert wird
* keine tiefe AST-/Codeanalyse als Atlas-Pflicht
* keine Git-Historien-Primärlogik
* keine LLM-Semantik im Kernlauf
* kein schweres graphisches UI vor stabilen Artefakten
* kein monolithischer „scan-and-solve-everything“-Befehl

---

# Teil 4/4: Verbindliche Architekturentscheidungen, Contracts, Verzeichnisstruktur, abhakbare Roadmap

## 1. Verbindliche Architekturentscheidungen (Setzungen)

### Entscheidung A — Atlas ist ein zustandsbehaftetes Gedächtnis
Jeder relevante Scan erzeugt einen persistenten Snapshot. Deltas und Historien bauen auf Snapshots auf. Pflichtobjekte: `machine`, `root`, `snapshot`.

### Entscheidung B — Atlas ist dateizentriert, Inhalte sind optionale Schicht
Pflichtkern: Pfad, Größe, Zeit, Typ, Root, Maschine.
Optional: `is_text`, encoding, line_count, preview, chunks, Volltextindex. Content darf nie den Discovery-Kern blockieren.

### Entscheidung C — Atlas ist eine Pipeline, kein Monolith
1. Discovery -> 2. Snapshot -> 3. Enrichment -> 4. Derivation -> 5. Indexing -> 6. Serving/Integration. Keine Gottfunktion (`atlas scan --everything`).

### Entscheidung D — Repo-/Workspace-Erkennung ist Annotation, nicht Leitontologie
Atlas modelliert primär Dateiwirklichkeit, nicht Projektpsychologie. Repo-Marker dürfen Atlas bereichern, aber nicht semantisch kapern.

### Entscheidung E — Registry in SQLite, schwere Artefakte als Dateien
SQLite für Machine Registry, Root Registry, Snapshot Registry, Delta Registry, Suchmetadaten/FTS.
Dateien für `inventory.jsonl`, `dirs.jsonl`, `content.json`, `topology.json`, `hotspots.json`, `workspaces.json`.

## 2. Contracts, die du wirklich anlegen solltest

* **Machine Contract**: Pflichtfelder (`machine_id`, `hostname`). `machine_id` muss stabil sein.
* **Root Contract**: Pflichtfelder (`root_id`, `machine_id`, `root_kind`, `root_value`). Kein Scan ohne expliziten Root-Kontext.
* **Snapshot Contract**: Pflichtfelder (`snapshot_id`, `machine_id`, `root_id`, `created_at`, `scan_config_hash`, `status`, mindestens ein Kernartefakt-Ref). Statuswerte (`running`, `complete`, `partial`, `failed`).
* **Inventory Contract**: Pflichtfelder (`snapshot_id`, `rel_path`, `size_bytes`, `mtime`, `is_symlink`). Harte Entscheidung: `is_text` wird nicht universell garantiert, sondern nur wenn Content-Enrichment aktiv ist.
* **Delta Contract**: Pflichtfelder (`from_snapshot_id`, `to_snapshot_id`, `created_at`, `new_files`, `removed_files`, `changed_files`). Listen sind deterministisch, sortiert, reproduzierbar.
* **Mode Output Contract**: Garantiert spezifische Pflichtartefakte für `inventory`, `topology`, `content`, `workspace`.

## 3. ADR-artige Setzungen (Architecture Decision Records)
- [ ] ADR-001 Atlas is filesystem-first, not repo-first
- [ ] ADR-002 Atlas is stateful and snapshot-driven
- [ ] ADR-003 Atlas uses pipeline stages, not monolithic scan flows
- [ ] ADR-004 Repo/workspace detection is annotation only
- [ ] ADR-005 Registry in SQLite, large artifacts as files
- [ ] ADR-006 Content enrichment is optional and mode-dependent

## 4. Abhakbare Roadmap

### Phase 0 — Konstitution und Contracts
Ziel: Atlas semantisch festziehen, bevor weiterer Ausbau Drift erzeugt.
- [ ] ADR-001 bis ADR-006 anlegen
- [ ] Machine Contract definieren
- [ ] Root Contract definieren
- [ ] Snapshot Contract definieren
- [ ] Inventory Contract definieren
- [ ] Delta Contract definieren
- [ ] Mode Output Contract definieren
- [ ] is_text-Garantie explizit dokumentieren
- [ ] Verzeichnisstruktur offiziell festlegen

**Stop-Kriterium**: Atlas hat eine explizite, maschinenlesbare und dokumentierte Grundverfassung.

### Phase 1 — Registry-Kern
Ziel: Machine-, Root- und Snapshot-Wirklichkeit persistent und abfragbar machen.
- [ ] atlas_registry.sqlite einführen
- [ ] Machine Registry implementieren
- [ ] Root Registry implementieren
- [ ] Snapshot Registry implementieren
- [ ] Snapshot-Status (running/complete/partial/failed) implementieren
- [ ] Snapshot-Artefakt-Refs konsistent speichern
- [ ] Snapshot-ID-Schema stabilisieren
- [ ] CLI: `atlas machines`
- [ ] CLI: `atlas roots`
- [ ] CLI: `atlas snapshots`

**Stop-Kriterium**: Jeder Scan taucht als Snapshot mit Root-/Machine-Kontext in der Registry auf.

### Phase 2 — Zeitgedächtnis
Ziel: Atlas wird historisch nutzbar.
- [ ] Snapshot-to-Snapshot Delta formal einführen
- [ ] Delta Registry ergänzen
- [ ] `from_snapshot_id` / `to_snapshot_id` standardisieren
- [ ] sortierte Delta-Listen garantieren
- [ ] CLI: `atlas diff <snapA> <snapB>`
- [ ] CLI: `atlas history <path>`
- [ ] Datei-Historienmodell definieren
- [ ] Root-Historienmodell definieren
- [ ] Zeitfenster-Vergleiche konzipieren
- [ ] Fehler-/Partial-Delta-Verhalten standardisieren

**Stop-Kriterium**: Atlas kann Zustand und Veränderung über Zeit explizit zeigen.

### Phase 3 — Incrementalität
Ziel: Große Roots effizient aktualisierbar machen.
- [ ] Re-Scan gegen letzten Snapshot vorbereiten
- [ ] mtime-/size-Heuristik definieren
- [ ] inode/device optional einbeziehen
- [ ] selektives Hashing-Modell festlegen
- [ ] unveränderte Teilbäume überspringen können
- [ ] `scan_config_hash` wirksam in Reuse-Logik einbeziehen
- [ ] Performance-Metriken erfassen
- [ ] CLI: `atlas scan --incremental`
- [ ] Regressionstests für inkrementelles Verhalten ergänzen

**Stop-Kriterium**: Ein Folgescan großer Roots ist deutlich günstiger als ein Vollscan.

### Phase 4 — Suchschicht
Ziel: Dateien und Inhalte systemweit abfragbar machen.
- [ ] SQLite-FTS evaluieren und festziehen
- [ ] Metadaten-Suchschema definieren
- [ ] Path-Search implementieren
- [ ] Name-Search implementieren
- [ ] Extension-/MIME-Search implementieren
- [ ] Größen-/Datumsfilter implementieren
- [ ] Content-Search implementieren
- [ ] Scope-Filter (machine, root, snapshot) implementieren
- [ ] CLI: `atlas search`
- [ ] Preview-/Snippet-Format definieren

**Stop-Kriterium**: Atlas kann Dateibestände und Inhalte über Registry + Index reproduzierbar durchsuchen.

### Phase 5 — Inhaltsanreicherung
Ziel: Dateien über Rohmetadaten hinaus erschließen, ohne den Kern zu überladen.
- [ ] MIME-Typ-Erkennung verbessern
- [ ] Encoding-Erkennung einführen
- [ ] line_count erfassen
- [ ] Parser für JSON/YAML/TOML/Markdown/CSV/HTML
- [ ] Medien-Minimalmetadaten (Bilddimensionen, Audio-/Video-Dauer)
- [ ] Preview-/Chunk-Artefakte definieren
- [ ] Content-Policy pro Root ermöglichen
- [ ] Binary-/Huge-file-Strategie klären
- [ ] Tests für modeabhängige Inhaltsfelder ergänzen

**Stop-Kriterium**: Content-Enrichment ist modular, root- und modeabhängig zuschaltbar.

### Phase 6 — Analyseartefakte
Ziel: Atlas wird diagnostisch.
- [ ] Hotspots erweitern um Growth-/Change-Achsen
- [ ] Duplicate Detection (size prefilter + hash confirm)
- [ ] duplicates.json definieren
- [ ] Orphan Detection definieren
- [ ] analyze disk standardisieren
- [ ] analyze duplicates implementieren
- [ ] analyze orphan implementieren
- [ ] Oldest-/Largest-Files-Artefakte vereinheitlichen
- [ ] Cross-root growth reports definieren

**Stop-Kriterium**: Atlas zeigt nicht nur Bestände, sondern konkrete Aufräum-, Speicher- und Vergleichsprobleme.

### Phase 7 — Multi-Machine-Atlas
Ziel: Maschinenübergreifende Dateiwirklichkeit sichtbar und vergleichbar machen.
- [ ] mehrere Machines sauber registrieren
- [ ] Root-Namenskonventionen zwischen Hosts vereinheitlichen
- [ ] Cross-machine snapshot diff definieren
- [ ] CLI: `atlas diff heim-pc:/home heimserver:/home`
- [ ] Backup-gap-Analyse definieren
- [ ] Remote-Collector-/SSH-Modell festlegen
- [ ] Konfliktfälle (gleiches root label, andere Pfade) definieren
- [ ] Maschinen-Health-/Last-Seen-Sicht ergänzen

**Stop-Kriterium**: Atlas kann Root- und Snapshot-Zustände über Maschinen hinweg vergleichen.

### Phase 8 — Watch-Mode und Chronik-Anbindung
Ziel: Atlas wird zu einem lebendigen Sensorsystem.
- [ ] Watch-Mode-Modell definieren
- [ ] inotify/fanotify-Strategie evaluieren
- [ ] Event-Schema für Dateiänderungen definieren
- [ ] Debounce-/Batching-Logik definieren
- [ ] Chronik-kompatiblen Exportpfad bauen
- [ ] CLI: `atlas watch /path`
- [ ] Snapshot-/Event-Verhältnis klären
- [ ] Watch-Failure-Recovery definieren

**Stop-Kriterium**: Atlas kann Dateiereignisse laufend beobachten und an Chronik weiterreichen.

### Phase 9 — Wissenskarte
Ziel: Die digitale Landschaft wird kartierbar.
- [ ] Knowledge-Cluster-Modell definieren
- [ ] systemweite Kategorien bestimmen
- [ ] `atlas map` Output-Format festlegen
- [ ] Root-/Machine-Karten definieren
- [ ] Cluster-Heuristiken bauen
- [ ] semantische Dateitags ergänzen
- [ ] UI-/Exportformate für Karten vorbereiten

**Stop-Kriterium**: Atlas kann Bestände nicht nur listen, sondern als maschinenweite Wissenslandschaft zeigen.

## 5. Meta-Reflexion: Sind wir kritisch genug?

Ja, aber mit zwei blinden Flecken, die explizit benannt werden müssen:

### Blinder Fleck 1
Wir haben noch keine exakte Aussage über die reale Dateimenge der Maschinen.
Größenordnungen und Scanfrequenzen fehlen; sie sind nötig, um Incrementalität, Hashing und Indexgröße präzise zu dimensionieren.

### Blinder Fleck 2
Wir haben noch keine endgültige Entscheidung über Content-Zugriffstiefe pro Root.
Das beeinflusst:
* Speicherbedarf
* Suchqualität
* Datenschutz-/Sicherheitsrestfragen
* Performance

## 6. Schlussverdichtung der gesamten Blaupause

Atlas soll werden: **der globale, historische Dateiatlas deiner Infrastruktur**

Mit diesem festen Kern:
* maschinenweit
* snapshot-getrieben
* dateizentriert
* pipelinebasiert
* suchfähig
* analysierbar
* repo-sensitiv, aber nicht repo-dominiert

Die entscheidende Formel lautet:
`Discovery -> Snapshot -> Enrichment -> Derivation -> Index -> Integration`

Und die wichtigste inhaltliche Invariante bleibt:
**Atlas modelliert zuerst Dateiwirklichkeit, nicht Entwicklerwirklichkeit.**
