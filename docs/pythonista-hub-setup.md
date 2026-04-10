# Pythonista Hub Setup (repoLens + wc-hub)

## Kernproblem

In Pythonista existieren getrennte Speicherwelten:

- iCloud → enthält repoLens
- Lokales Pythonista Documents → enthält wc-hub

→ repoLens kann den Hub **nicht selbst finden**, da beide Welten isoliert sind.

---

## Prinzip

Der `pathfinder.py` muss **im Kontext des Hubs ausgeführt werden**.

→ Nur dort kann er den echten Pfad bestimmen.

---

## 🔧 Setup (verbindlich)

### 1. Pathfinder in den Hub kopieren

Kopiere:

merger/lenskit/frontends/pythonista/pathfinder.py

nach:

/wc-hub/

---

### 2. Pathfinder im Hub ausführen

In Pythonista:

wc-hub/pathfinder.py starten

---

### 3. Was passiert intern

Der Pathfinder:

- erkennt den aktuellen Hub-Pfad
- schreibt diesen in:

wc-hub/.repolens-hub-path.txt

und zusätzlich nach:

/.repolens-hub-path.txt

→ Damit entsteht ein persistenter Pfad-Contract.

---

### 4. repoLens neu starten

Nach erfolgreichem Lauf:

👉 repoLens neu starten

---

## ✅ Erfolgskriterium

repoLens startet **ohne Fehler**.

Optional prüfen:

/.repolens-hub-path.txt

enthält:

/private/var/mobile/…/Documents/wc-hub

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

repoLens nutzt bewusst **keine unsichere Auto-Erkennung**, sondern einen expliziten Pfad-Contract.

→ Pathfinder ist Teil der Architektur, nicht nur ein Debug-Tool.

---

## 🧾 Kurzfassung

Wenn repoLens den Hub nicht findet:

1. Pathfinder in wc-hub kopieren
2. dort ausführen
3. repoLens neu starten
