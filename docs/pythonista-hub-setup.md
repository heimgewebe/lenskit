# Pythonista Hub Setup (repoLens + wc-hub)

## Kernproblem

In Pythonista existieren getrennte Speicherwelten:

- iCloud → enthält repoLens
- Lokales Pythonista Documents → enthält wc-hub

Konkrete Pfade (Beispiel):

- iCloud:
  /private/var/mobile/Library/Mobile Documents/iCloud~com~omz-software~Pythonista3/Documents/...

- Lokal:
  /private/var/mobile/Containers/Data/Application/.../Documents/...

→ repoLens kann den Hub teils automatisch erkennen (z. B. über Argument, Environment oder gespeicherten Pfad),
  aber über die getrennten iCloud-/lokalen Documents-Welten hinweg ist diese Erkennung nicht verlässlich.

---

## iOS-Fähigkeiten und Grenzen (keine Subprozesse)

Pythonista/iOS unterstützt **keine Subprozesse**. repoLens kann dort daher keine
Git-Subprozesse starten.

- **Lokale Scans funktionieren** (kein Git nötig) – Merge/Reports laufen normal.
- **Git-basierte Funktionen sind auf iOS nicht verfügbar** – das Verhalten
  unterscheidet sich je nach Oberfläche:

  | Oberfläche | Verhalten |
  | :--- | :--- |
  | **UI (Run Merge)** | Ein aktivierter Pre-pull-Schalter wird **effektiv deaktiviert** (kein Crash, Hinweis im Log, lokaler Scan läuft weiter). |
  | **Headless – explizite Flags** | `--pre-pull`, `--source-mode local-ff`, `--source-mode remote-snapshot` werden **früh abgelehnt** (Exit 2, klare Fehlermeldung, kein Stacktrace). |
  | **Headless – impliziter Default** | Ein einfaches `repolens.py --headless` (keine Source-Flags) würde intern zu `local_ff` auflösen; stattdessen wird **implizit auf `local_current` degradiert** (Hinweis im stdout, kein Crash). |

- Für alle git-basierten Funktionen **Desktop bzw. den rLens-Service verwenden**.

> Praxis: Auf dem iPad „Run Merge” ohne Pre-pull ausführen. Ein versehentlich
> aktivierter Pre-pull-Schalter stoppt den Merge nicht – er wird effektiv
> deaktiviert, der lokale Scan läuft weiter.

---

## Prinzip

Der `pathfinder.py` muss **im Kontext des Hubs ausgeführt werden**.
Der Ausführungsort bestimmt die Sicht auf das Dateisystem.

→ Nur dort kann er den echten Pfad bestimmen.

---

## 🔧 Setup (verbindlich)

### 1. Pathfinder in den Hub kopieren

Kopiere:

merger/lenskit/frontends/pythonista/pathfinder.py

nach:

`<lokales Pythonista Documents>/wc-hub/`

---

### 2. Pathfinder im Hub ausführen

In Pythonista:

`<lokales Pythonista Documents>/wc-hub/pathfinder.py` starten (bzw. `repolens-hub-pathfinder.py`)

---

### 3. Was passiert intern

Der Pathfinder:

- erkennt den aktuellen Hub-Pfad
- schreibt diesen in:

`<lokales Pythonista Documents>/wc-hub/.repolens-hub-path.txt`

und zusätzlich nach:

`<repoLens iCloud-Verzeichnis>/.repolens-hub-path.txt`

→ Damit entsteht ein persistenter Pfad-Contract.

---

### 4. repoLens neu starten

Nach erfolgreichem Lauf:

👉 repoLens neu starten

---

## ✅ Erfolgskriterium

repoLens startet **ohne Fehler**.

Zusätzlich prüfen:

1. Öffne:
   `<repoLens iCloud-Verzeichnis>/.repolens-hub-path.txt`

2. Inhalt muss exakt sein:
   /private/var/mobile/.../Documents/wc-hub

Wenn diese Datei fehlt oder leer ist → Pathfinder erneut ausführen.

---

## 🧯 Wenn es nicht funktioniert

1. Prüfen:
   Existiert `<repoLens iCloud-Verzeichnis>/.repolens-hub-path.txt`?

2. Wenn nein:
   → Pathfinder erneut im wc-hub ausführen

3. Wenn ja:
   → repoLens komplett neu starten

4. Wenn weiterhin Fehler:
   → falscher Script-Kontext (Pathfinder im falschen Ort ausgeführt)

---

## ❗ Wichtige Regel

> Pathfinder funktioniert nur korrekt, wenn er im Zielverzeichnis (wc-hub) ausgeführt wird.

Ein Lauf aus iCloud heraus liefert falsche oder unvollständige Ergebnisse.

---

## 🔁 Wann erneut ausführen?

- nach Verschieben des wc-hub
- nach iOS-/App-Neuinstallation
- wenn repoLens meldet:
  `Hub-Verzeichnis nicht gefunden`

---

## 🧠 Designentscheidung

repoLens bevorzugt bewusst einen expliziten gespeicherten Pfad-Contract
statt sich primär auf Auto-Erkennung zu verlassen.
Begrenzte Fallbacks existieren, können aber in getrennten Speicherwelten fehlschlagen.

→ Pathfinder ist Teil der Architektur, nicht nur ein Debug-Tool.

---

## 🧾 Kurzfassung

Wenn repoLens den Hub nicht findet:

1. Pathfinder in wc-hub kopieren
2. dort ausführen
3. repoLens neu starten
