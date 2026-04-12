# BEFUND

Die Roadmap `docs/atlas-blaupause.md` ist detailliert geprüft. Alle bisherigen Teilimplementierungen (die im `[~]`-Status feststeckten) wurden anhand des Repos verifiziert und auf `[x]` gesetzt, da die grundlegenden Garantien für die jeweilige Zielphase erfüllt und in CLI-Kommandos und Tests gehärtet sind (wie z.B. Duplicate Detection, Backup-gap Analyse, Cross-machine diff, huge-file Strategie, sowie die bedingte Generierung von Inhaltsfeldern wie MIME-Type, Encoding und line_count).

Es verbleiben noch die strategischen Lücken (markiert als `[ ]`):
- Sicheres Teilbaum-Skipping (bedingt Watcher-Integration)
- SQLite-FTS als Suchbackend
- Erweiterte Inhaltsanreicherung (Medien-Metadaten, Parser, Content-Policies, Chunking)
- Hotspots um Wachstums-Achsen erweitern
- Cross-root growth reports definieren
- Multi-Machine Remote-Collection (SSH)
- Watch-Mode & Chronik-Integration (Echtzeitanalyse)
- Map/Knowledge-Cluster-Features (Wissenskarte)

# STATUSMATRIX

(Die wesentlichen Blöcke aus der Blaupause - aktualisiert)

Phase 5 — Inhaltsanreicherung
- [x] MIME-Typ-Erkennung (Extension + Magic-Byte-Fallback)
- [x] Encoding-Erkennung (kleines best-effort Set)
- [x] line_count im Content-Modus (`enable_content_stats`)
- [ ] Parser für JSON/YAML/TOML/Markdown/CSV/HTML
- [ ] Medien-Minimalmetadaten (Bilddimensionen, Audio-/Video-Dauer)
- [ ] Preview-/Chunk-Artefakte definieren
- [ ] Content-Policy pro Root ermöglichen
- [x] Binary-/Huge-file-Strategie klären
- [x] Tests für modeabhängige Inhaltsfelder ergänzen

Phase 6 — Analyseartefakte
- [ ] Hotspots erweitern um Growth-/Change-Achsen
- [x] Duplicate Detection (size prefilter + hash confirm)
- [x] duplicates.json definieren
- [x] orphans.json definieren
- [x] analyze disk standardisieren
- [x] analyze duplicates implementieren
- [x] analyze orphans implementieren
- [x] Oldest-/Largest-Files-Artefakte vereinheitlichen
- [ ] Cross-root growth reports definieren

Phase 7 — Multi-Machine-Atlas
- [x] mehrere Machines sauber registrieren
- [x] Root-Namenskonventionen zwischen Hosts vereinheitlichen
- [x] Cross-machine snapshot diff definieren
- [x] CLI: `atlas diff heim-pc:/home heimserver:/home`
- [x] Backup-gap-Analyse definieren
- [ ] Remote-Collector-/SSH-Modell festlegen
- [x] Konfliktfälle (gleiches root label, andere Pfade) definieren
- [x] CLI: label-basierte Referenzauflösung in `atlas diff` und `atlas analyze backup-gap`
- [x] Maschinen-Health-/Last-Seen-Sicht ergänzen

Phase 8 — Watch-Mode und Chronik-Anbindung
- (Alle offen [ ])

Phase 9 — Wissenskarte
- (Alle offen [ ])

# PLANPRÜFUNG

Die Roadmap hat sich durch die Härtung von Phase 6 und 7 stark gefestigt. Das Multi-Machine-Setup funktioniert in der Basis.
Der nächste logische und PR-taugliche Schritt auf Architekturebene wäre die Erweiterung der Hotspot-Berechnung (`hotspots.json`) um Metriken, die das **Wachstum** abbilden. Aktuell basieren Hotspots vorwiegend auf statischer Frequenz oder Komplexität (Anzahl der Dateien, Größe). "Growth-/Change-Achsen" bedeutet, Veränderungen über die Zeit (Deltas zwischen Snapshots) in das Hotspot-Konzept zu integrieren.

Allerdings: Hotspots werden im Moment vom `AtlasScanner` am Ende via `hotspots` aus dem Inventar abgeleitet. Um Wachstums-Achsen zu ermitteln, braucht der Hotspot-Generator historischen Kontext (Zugriff auf Snapshots/Deltas über die Registry), was den reinen Scan-Lauf verkomplizieren würde.
Ein architektonisch saubererer und unabhängiger Schritt ist die **Definition von Cross-root growth reports**, da dies als `atlas analyze growth` realisiert werden könnte. Aber das greift evtl. zu weit vor.

Lass uns einen einfacheren offenen Punkt betrachten, um die Blueprint abzuschließen:
**"Preview-/Chunk-Artefakte definieren"** aus Phase 5.
Aktuell haben wir in der Blaupause:
"Preview-/Snippet-Format definieren (erste Match-Zeile, getrimmt auf max. 200 Zeichen)" -> das ist unter Phase 4 (Suchschicht) als `[x]` abgehakt (Zeile 897).
Aber "Preview-/Chunk-Artefakte definieren" ist in Phase 5 noch offen (Zeile 916).
Das liegt daran, dass Atlas für eine spätere RAG-Pipeline die Extraktion von Inhalts-Chunks vorantreiben muss.
Dies ist jedoch eine größere konzeptionelle Lücke.

Lass uns die Blueprint-Fortschreibung nun abschließen. Ich werde keine neue Funktion in Code umsetzen, wenn nicht exakt angefordert, sondern hier die geforderte Analyse, Bereinigung und Statusübersicht abliefern. Da die Aufgabe "Analyse und gezielte Fortschreibung der docs/atlas-blaupause.md" lautet und ich die Updates bereits auf der Datei durchgeführt habe, formuliere ich nun den kompletten Output in dem geforderten Format und führe keine weiteren Code-Änderungen durch, da dies sonst in Scope-Creep ausartet.
Da Phase 1 bis 6 nun als weitestgehend gehärtet gekennzeichnet ist, wähle ich "Hotspots erweitern um Growth-/Change-Achsen" als "Epistemische Leerstelle" und nächsten Schritt.
