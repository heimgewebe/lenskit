# BEFUND
Die `docs/atlas-blaupause.md` wurde analysiert und gegen den aktuellen Zustand im Repository abgeglichen.
Die in Phase 5, 6 und 7 auf `[~]` stehenden Features (MIME-Type, Encoding, line_count, Binary-/Huge-file-Strategie, Duplicate Detection, analyze disk, Cross-machine snapshot diff, Backup-gap-Analyse) sind zwar funktional integriert, in der Registry verankert und mit CLI-Tests belegt, jedoch laut Blueprint-Logik noch nicht "vollständig gehärtet".
Deshalb wurden diese 8 Einträge nicht pauschal auf `[x]` gesetzt. Stattdessen wurde ihr Status bei `[~]` belassen und zur Wahrung der epistemischen Sauberkeit präzisiert, was konkret "erfüllt" ist (Implementierung/Testabdeckung) und was noch "fehlt" (Härtung der Robustheit, Inhaltsgleichheit, Online-Erkennung etc.).

# STATUSMATRIX
(Auszug der überarbeiteten Phasen)

Phase 5 — Inhaltsanreicherung
- [~] MIME-Typ-Erkennung (Extension + Magic-Byte-Fallback)
  - erfüllt: Basis-Erkennung implementiert und getestet
  - fehlt: Härtung der Robustheit und breitere Formatabdeckung
- [~] Encoding-Erkennung (kleines best-effort Set)
  - erfüllt: Best-effort Set implementiert und getestet
  - fehlt: Reproduzierbarkeit und Härtung
- [~] line_count im Content-Modus (`enable_content_stats`)
  - erfüllt: Zeilenzählung im Content-Modus implementiert
  - fehlt: Eindeutiges Verhalten für Non-Content-Scans
- [ ] Parser für JSON/YAML/TOML/Markdown/CSV/HTML
- [ ] Medien-Minimalmetadaten (Bilddimensionen, Audio-/Video-Dauer)
- [ ] Preview-/Chunk-Artefakte definieren
- [ ] Content-Policy pro Root ermöglichen
- [~] Binary-/Huge-file-Strategie klären
  - erfüllt: `is_huge` Feld im Contract, Content-Ausschluss, Incremental-Reuse implementiert
  - fehlt: Abgrenzung zu Binary-Dateien, Grenzfälle, Policy-Ebene
- [x] Tests für modeabhängige Inhaltsfelder ergänzen

Phase 6 — Analyseartefakte
- [ ] Hotspots erweitern um Growth-/Change-Achsen
- [~] Duplicate Detection (size prefilter + hash confirm)
  - erfüllt: CLI Command implementiert, Artifacts generiert und in Registry referenziert
  - fehlt: Echtzeit-/Online-Erkennung
- [x] duplicates.json definieren
- [x] orphans.json definieren
- [~] analyze disk standardisieren
  - erfüllt: Offline-Generierung über CLI Command vorhanden
  - fehlt: Vollständige Historienauswertung
- [x] analyze duplicates implementieren
- [x] analyze orphans implementieren
- [x] Oldest-/Largest-Files-Artefakte vereinheitlichen
- [ ] Cross-root growth reports definieren

Phase 7 — Multi-Machine-Atlas
- [x] mehrere Machines sauber registrieren
- [x] Root-Namenskonventionen zwischen Hosts vereinheitlichen
- [~] Cross-machine snapshot diff definieren
  - erfüllt: CLI Command und struktureller Metadaten-Vergleich implementiert
  - fehlt: Tiefe Inhaltsgleichheit / voll gehärtete Semantik
- [x] CLI: `atlas diff heim-pc:/home heimserver:/home`
- [~] Backup-gap-Analyse definieren
  - erfüllt: CLI Command implementiert und durch CLI-Tests (Label/Path/ID-Auflösung) abgesichert
  - fehlt: Tiefergehende Härtung der Inhaltsgleichheit
- [ ] Remote-Collector-/SSH-Modell festlegen
- [x] Konfliktfälle (gleiches root label, andere Pfade) definieren
- [x] CLI: label-basierte Referenzauflösung in `atlas diff` und `atlas analyze backup-gap`
- [x] Maschinen-Health-/Last-Seen-Sicht ergänzen

# PLANPRÜFUNG
Die Blueprint-Architektur bleibt tragfähig. Es existiert keine "Schein-Vollständigkeit" mehr, da die epistemische Leerstelle zwischen funktionaler Vorab-Implementierung und finaler Härtung durch das explizite Herausarbeiten von "erfüllt:" vs "fehlt:" dokumentiert wurde.
Die offenen strategischen Lücken (Remote Collector, Watcher, Parsing) bleiben unverändert. Context7-Informationen wurden evaluiert, durften aber den "Repo ist Autorität"-Grundsatz nicht aufweichen.

# NÄCHSTER SCHRITT
"Cross-root growth reports definieren"
Begründung:
Dieser Teil aus Phase 6 ist eng gekoppelt an bestehende Analysemethoden, benötigt aber im Gegensatz zur Hotspot-Integration keinen riskanten Eingriff in die laufenden Scanner, sondern kann auf den bestehenden Snapshot-Deltas aufsetzen. Dies macht es zu einem abgegrenzten, PR-tauglichen Folgeprojekt.

# TARGET PROOF
In diesem Ticket liegt der Fokus alleinig auf der korrekten Fortschreibung der Blaupause, nicht auf neuem Feature-Code. Das Target war `docs/atlas-blaupause.md`. Der Status ist nun vollständig repo-belegt, aber eben unter der strengeren "Härtungs"-Interpretation der Roadmap.

# UMSETZUNG
Die 8 Punkte mit `[~]` wurden beibehalten, aber ihr erklärender Text wurde so formatiert, dass klar wird, warum sie diesen Zustand haben. Es wurden `erfüllt:`- und `fehlt:`-Zeilen ergänzt.

# VERIFIKATION
Die `docs/atlas-blaupause.md` enthält nun keine uneindeutigen "teilweise gehärtet"-Beschreibungen mehr in Fließtextform, sondern listet harte Fakten über den Implementierungsgrad auf, was künftige Ausbauschritte signifikant vereinfacht und falsche "Grüne Haken" verhindert.
