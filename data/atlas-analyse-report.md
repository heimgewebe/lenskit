# BEFUND

Atlas ist im aktuellen Repo-Zustand bereits strukturell als System zur Erfassung der physischen Dateiwirklichkeit etabliert. Das Fundament der Architekturentscheidungen (ADR-001 bis ADR-007) wurde substanziell implementiert. SQLite dient als kanonische Registry für Machines, Roots, Snapshots und Deltas. Path-Auflösungen erfolgen deterministisch (`merger/lenskit/atlas/paths.py`). Der Scan-Lifecycle ist gehärtet (`merger/lenskit/atlas/lifecycle.py`).

Ein wesentliches epistemisches Problem bleibt jedoch bestehen: Die Inhaltserschließungsphase (Phase 5) hat eine "Epistemische Leerstelle" hinsichtlich großer Dateien. Im Code (`merger/lenskit/adapters/atlas.py`) werden Dateien, die `max_file_size` überschreiten, über ein hartes `continue` komplett aus dem Scanner-Durchlauf und damit aus dem generierten `inventory.jsonl` ausgeschlossen. Dies verletzt die Invariante 4 ("Snapshot vor Erklärung" / "Erst Realität speichern, dann interpretieren") sowie das Kernmandat ("Atlas soll die physische Realität deiner Maschinen explizit erfassen: Welche Dateien gibt es?"). Große Dateien (z.B. VM-Images, Datenbankdumps) verschwinden aus dem Dateisystem-Gedächtnis völlig, anstatt nur von der inhaltlichen Analyse ausgeschlossen zu werden.

# STATUSMATRIX

### Phase 0 — Konstitution und Contracts
- [x] ADR-001 bis ADR-007 anlegen
- [x] Machine Contract definieren
- [x] Root Contract definieren
- [x] Snapshot Contract definieren
- [x] Inventory Contract definieren
- [x] Delta Contract definieren
- [x] Mode Output Contract definieren
- [x] is_text-Garantie explizit dokumentieren
- [x] Verzeichnisstruktur offiziell festlegen

### Phase 1 — Registry-Kern
- [x] atlas_registry.sqlite einführen
- [x] Machine Registry implementieren
- [x] Root Registry implementieren
- [x] Snapshot Registry implementieren
- [x] Snapshot-Status (running/complete/failed) implementieren
- [x] Snapshot-Artefakt-Refs konsistent in Zielstruktur speichern
- [x] Snapshot-ID-Schema vorläufig stabilisiert
- [x] CLI: atlas machines
- [x] CLI: atlas roots
- [x] CLI: atlas snapshots

### Phase 2 — Zeitgedächtnis
- [x] Snapshot-to-Snapshot Delta formal einführen
- [x] Delta Registry ergänzen
- [x] from_snapshot_id / to_snapshot_id standardisieren
- [x] sortierte Delta-Listen garantieren
- [x] CLI: atlas diff <snapA> <snapB>
- [x] CLI: atlas history <machine_id> <root_id> <rel_path>
- [x] Datei-Historienmodell definieren
- [x] Root-Historienmodell definieren
- [x] Zeitfenster-Vergleiche konzipieren
- [x] Fehler-/Partial-Delta-Verhalten standardisieren

### Phase 3 — Incrementalität
- [x] Re-Scan gegen letzten Snapshot vorbereiten
- [x] mtime-/size-Heuristik definieren
- [x] inode/device optional erfassen
- [x] selektives Hashing-Modell festlegen
- [x] heuristische Teilbaum-Kandidaten erkennen
- [ ] sicheren Teilbaum-Skip ermöglichen
- [x] scan_config_hash wirksam in Reuse-Logik einbeziehen
- [x] Basis-Incremental-Metriken erfassen
- [x] CLI: atlas scan --incremental
- [x] Regressionstests für inkrementelles Verhalten ergänzen

### Phase 4 — Suchschicht
- [ ] SQLite-FTS evaluieren und festziehen
- [x] Metadaten-Suchschema definieren
- [x] Path-Search implementieren
- [x] Name-Search implementieren
- [x] Extension-/MIME-Search implementieren
- [x] Größen-/Datumsfilter implementieren
- [x] Content-Search implementieren
- [x] Scope-Filter implementieren
- [x] CLI: atlas search
- [x] Preview-/Snippet-Format definieren

### Phase 5 — Inhaltsanreicherung
- [~] MIME-Typ-Erkennung (Extension + Magic-Byte-Fallback)
- [~] Encoding-Erkennung (kleines best-effort Set)
- [~] line_count im Content-Modus
- [ ] Parser für JSON/YAML/TOML/Markdown/CSV/HTML
- [ ] Medien-Minimalmetadaten
- [ ] Preview-/Chunk-Artefakte definieren
- [ ] Content-Policy pro Root ermöglichen
- [~] Binary-/Huge-file-Strategie klären (Fehlerhaft: Große Dateien werden komplett ignoriert)
- [x] Tests für modeabhängige Inhaltsfelder ergänzen

### Phase 6 — Analyseartefakte
- [ ] Hotspots erweitern um Growth-/Change-Achsen
- [x] teilweise gehärtet: Duplicate Detection
- [x] teilweise gehärtet: duplicates.json definieren
- [x] teilweise gehärtet: orphans.json definieren
- [x] teilweise gehärtet: analyze disk standardisieren
- [x] analyze duplicates implementieren
- [x] analyze orphans implementieren
- [x] Oldest-/Largest-Files-Artefakte vereinheitlichen
- [ ] Cross-root growth reports definieren

### Phase 7 — Multi-Machine-Atlas
- [x] mehrere Machines sauber registrieren
- [x] Root-Namenskonventionen zwischen Hosts vereinheitlichen
- [ ] teilweise gehärtet: Cross-machine snapshot diff definieren
- [x] CLI: atlas diff heim-pc:/home heimserver:/home
- [x] teilweise gehärtet: Backup-gap-Analyse definieren
- [ ] Remote-Collector-/SSH-Modell festlegen
- [x] Konfliktfälle (gleiches root label, andere Pfade) definieren
- [x] CLI: label-basierte Referenzauflösung in atlas diff
- [x] Maschinen-Health-/Last-Seen-Sicht ergänzen

### Phase 8 — Watch-Mode und Chronik-Anbindung
- [ ] Watch-Mode-Modell definieren (Alle Unterpunkte offen)

### Phase 9 — Wissenskarte
- [ ] Knowledge-Cluster-Modell definieren (Alle Unterpunkte offen)

# PLANPRÜFUNG

Die Roadmap in der Blaupause ist weitgehend stabil und spiegelt den Ausbaupfad gut wider. Context7-Intentionen (Gedächtnis vor Scanner) sind architektonisch sauber implementiert (SQLite Registry).

Die höchste architektonische Dissonanz liegt aktuell in **Phase 5 (Inhaltsanreicherung)**. Eine der Kerninvarianten ("Atlas bleibt source-of-truth für physische Dateiwirklichkeit") wird durch den Umgang mit großen Dateien gebrochen. In `merger/lenskit/adapters/atlas.py` Zeile 399 wird `continue` aufgerufen, wenn `size > self.max_file_size`. Das bedeutet, eine 5GB ISO-Datei existiert im Atlas-Gedächtnis nicht, nur weil sie für Content-Analysen zu groß ist.

*Belegt:* `merger/lenskit/adapters/atlas.py` implementiert Filterung vor der Inventarisierung, nicht nur vor der Inhaltsanalyse.
*Plausibel (Context7):* Atlas soll das physische Gedächtnis sein. Ein vollständiges Inventar ist essenziell für Systemanalysen (z. B. "Largest files", Disk-Usage).

# NÄCHSTER SCHRITT

**Umsetzung der Binary-/Huge-file-Strategie durch Korrektur des Dateigrößenfilters.**

*Begründung:*
1. Klein und PR-tauglich (minimalinvasiver Code-Eingriff).
2. Reduziert epistemische Unsicherheit (garantiert, dass das Inventar 100% der physischen Realität widerspiegelt, ausgenommen explizite Pfad-Excludes).
3. Architektonisch zwingend: Stellt die Invariante "Snapshot vor Erklärung" wieder her. Große Dateien müssen ins `inventory.jsonl`, dürfen aber bei der kostspieligen Content-Analyse übersprungen werden.

# TARGET PROOF

**Exakte Stelle:** `merger/lenskit/adapters/atlas.py`
**Aktueller Zustand (Zeile 396-401):**
```python
stat = f_path.stat()
size = stat.st_size

if self.max_file_size is not None and size > self.max_file_size:
    continue
```
**Warum Änderung notwendig ist:** Dies führt dazu, dass Atlas große Dateien physisch ignoriert. Eine Datei > 50MB wird nicht in das Inventar aufgenommen, was Analysen wie Speicherauslastung oder Snapshot-Vergleiche von Archiven verfälscht.
**Erwartete Wirkung:** Die `continue`-Anweisung wird entfernt. Stattdessen wird die Größe verwendet, um sicherzustellen, dass keine schweren Inhaltsanalysen (`is_text`, `quick_hash`, `mime_type` etc.) durchgeführt werden, die Inventarisierung aber stattfindet.

# UMSETZUNG
(folgt im Code-Schritt)

# VERIFIKATION
(folgt nach der Umsetzung via Test und CLI-Aufruf)
