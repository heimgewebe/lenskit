# BEFUND
Die `docs/atlas-blaupause.md` wurde analysiert und gegen den aktuellen Zustand im Repository abgeglichen.
Die Features in den fortgeschrittenen Phasen (z.B. MIME-Type, Encoding, Duplicate Detection, analyze disk, Cross-machine diff) sind zwar funktional implementiert und durch Tests belegt (nachgewiesen durch E2E-CLI-Tests und Unit-Tests), aber laut strenger Blueprint-Logik noch nicht als vollständig `[x]` gehärtet zu betrachten.
Um das "Overloading" des `[~]`-Status zu beheben – welches fälschlicherweise reine Implementierungs-Lücken mit Härtungs-Lücken gleichsetzte –, wurde die Statussemantik im Dokument (Abschnitt 0) formell neu definiert und präzisiert. `[~]` wird für fortgeschrittene Features ab Phase 5 nun systematisch durch die drei Dimensionen `implementation`, `tests` und `hardening` unterfüttert. Ältere Phasen bleiben unberührt, um Scope-Creep zu vermeiden.

# STATUSMATRIX
(Auszug der überarbeiteten Phasen mit neuer dimensionaler Statusstruktur)

Phase 5 — Inhaltsanreicherung
- [~] MIME-Typ-Erkennung (Extension + Magic-Byte-Fallback)
  - implementation: done
  - tests: present
  - hardening: partial (best-effort Heuristik, Formatabdeckung ausbaufähig)
- [~] Encoding-Erkennung (kleines best-effort Set)
  - implementation: done
  - tests: present
  - hardening: partial (Reproduzierbarkeit und Robustheit offen)
- [~] line_count im Content-Modus (`enable_content_stats`)
  - implementation: done
  - tests: present
  - hardening: partial (Verhalten für Non-Content-Scans methodisch unklar)
- [ ] Parser für JSON/YAML/TOML/Markdown/CSV/HTML
- [ ] Medien-Minimalmetadaten (Bilddimensionen, Audio-/Video-Dauer)
- [ ] Preview-/Chunk-Artefakte definieren
- [ ] Content-Policy pro Root ermöglichen
- [~] Binary-/Huge-file-Strategie klären
  - implementation: done (Erfassung und Content-Bypass)
  - tests: present
  - hardening: partial (Abgrenzung zu reinen Binaries und Policy-Ebene fehlen)

Phase 6 — Analyseartefakte
- [ ] Hotspots erweitern um Growth-/Change-Achsen
- [~] Duplicate Detection (size prefilter + hash confirm)
  - implementation: done (Offline CLI)
  - tests: present
  - hardening: partial (Echtzeit-/Online-Erkennung fehlt)
- [~] analyze disk standardisieren
  - implementation: done (CLI Output und Disk-Artifact)
  - tests: present
  - hardening: partial (Vollständige Historienauswertung fehlt)

Phase 7 — Multi-Machine-Atlas
- [~] Cross-machine snapshot diff definieren
  - implementation: done (struktureller Metadaten-Abgleich)
  - tests: present
  - hardening: partial (tiefe Inhaltsgleichheit nicht bewiesen)
- [~] Backup-gap-Analyse definieren
  - implementation: done (CLI Command)
  - tests: present
  - hardening: partial (wie beim Diff fehlt inhaltliche Tiefe)

# PLANPRÜFUNG
Der Paradigmenwechsel vom formlosen Begleittext ("teilweise implementiert") hin zu orthogonalen Dimensionen (Implementation, Tests, Hardening) schafft epistemische Klarheit, ohne die Features verfrüht als `[x]` freizugeben.
Wir unterscheiden nun explizit objektiv belegbare Fakten (die Funktionen sind funktional implementiert und durch vorhandene Unit- und CLI-Tests abgesichert) von architektonischen Restrisiken (Hardening ist nur "partial", weil Edge-Cases oder volle Inhaltsgleichheits-Nachweise fehlen). Diese Metareflexion entspricht dem geforderten Niveau der Blaupause als strenges Steuerinstrument.

# NÄCHSTER SCHRITT
"Cross-root growth reports definieren" (Phase 6)
Begründung:
Dieser Teil aus Phase 6 ist eng gekoppelt an bestehende Analysemethoden. Da die Offline-CLI-Struktur durch Backup-gap und Diff nun etabliert (implementation: done) und stabilisiert (tests: present) ist, ist der Growth-Report ein isolierter, sicherer nächster Schritt, ohne den Kernscanner zu gefährden.

# TARGET PROOF
In diesem Schritt lag der Fokus strikt auf der Aktualisierung der `docs/atlas-blaupause.md`.
Es wurde keine Feature-Logik im Code berührt. Das Dokument mischte zuvor Implementierungsgrad und Härtungsgrad im Symbol `[~]`. Der Zustand nachher führt die Dimensionen explizit ein und löst diese semantische Überladung für kritische Phasen systematisch auf.

# UMSETZUNG
- Hinzufügen des Kapitels `0. STATUS-SEMANTIK & DIMENSIONEN` zur formalen Festschreibung der Dimensionen (mit dem Hinweis, dass ältere Phasen nicht rückwirkend transformiert werden müssen).
- Umschreiben der 8 fraglichen Einträge von Fließtext ("erfüllt/fehlt") in strukturierte Listen:
  `- implementation: ...`
  `- tests: ...`
  `- hardening: ...`

# VERIFIKATION
Durch das strukturierte Format wird die Interpretation der Blaupause systematischer fassbar und reduziert Ambiguität deutlich. Künftige Contributors können nun klar ablesen, dass das Feature zwar funktional existiert und Tests durchlaufen, aber es noch an der letzten "Hardening"-Rigorosität (z.B. Reproduzierbarkeit oder echter Online-Robustheit) mangelt, was Reviews und künftige Ausbauschritte vereinfacht.
