# Graph Runtime Contract

**Status:** Verbindlich ab Phase 3
**Geltungsbereich:** Definiert die semantische Bedeutung des Architecture Graphs für die Query- und Eval-Runtime in Lenskit.

---

## 1. Zweck

Der Lenskit-Architekturgraph (`graph_index.json`) dient nicht nur der Visualisierung, sondern fließt als formales, berechenbares Signal in die Such- und Evaluierungspipeline ein. Dieses Dokument definiert die Semantik der Graphelemente und deren exakte Wirkung auf das Retrieval-Ranking.

---

## 2. Ontologie und Semantik

### 2.1 Node (Knoten)
* **Bedeutung:** Ein Knoten repräsentiert eine strukturelle Code-Einheit. Im Standardfall entspricht dies einer Datei (File-Node). Die Granularität kann später auf Module oder Klassen erweitert werden.
* **Identität (`node_id`):** Eindeutiger Identifier. Für Dateien wird üblicherweise `file:<path>` oder der reine `<path>` verwendet.
* **Erreichbarkeit:** Ein Knoten gilt als erreichbar, wenn ein Pfad von mindestens einem Entrypoint zu ihm existiert.

### 2.2 Edge (Kante)
* **Bedeutung:** Eine gerichtete Kante (`src` → `dst`) repräsentiert eine Abhängigkeit.
* **Beispiel:** `src` importiert oder ruft `dst` auf. Wenn `A` von `B` abhängt (z.B. `A` importiert `B`), zeigt die Kante von `A` nach `B`.
* **Traversierung:** Die Traversierung für die Distanzberechnung erfolgt entlang dieser gerichteten Kanten (von den Entrypoints in die Tiefe der Abhängigkeiten).

### 2.3 Entrypoint
* **Bedeutung:** Entrypoints sind definierte Einstiegspunkte in das System (z.B. `main.py`, API-Routen, CLI-Befehle).
* **Funktion:** Sie dienen als Ausgangspunkte (Wurzeln) für die Distanzberechnung. Entrypoints haben per Definition die Distanz `0`.

### 2.4 Distance (Distanz)
* **Bedeutung:** Die minimale Anzahl von Kanten (Hops) von einem beliebigen Entrypoint zu einem Knoten.
* **Gerichtetheit:** Die Distanz ist gerichtet. Ein Modul, das von einem Entrypoint importiert wird, hat Distanz 1. Ein Modul, das den Entrypoint importiert (was meist architektonisch vermieden wird), hat keine automatische Erreichbarkeit aus dieser Richtung.
* **Unreachable (Nicht erreichbar):** Knoten, zu denen kein Pfad von einem Entrypoint existiert, erhalten intern den Distanzwert `-1` (oder werden nicht im Distanz-Mapping geführt). Sie erhalten keinen Graph-Bonus.

---

## 3. Runtime-Wirkung (Scoring)

Das Graph-Signal wird als additiver Bonus in die Score-Komponenten integriert. Es darf lexikalische und semantische Signale unterstützen, aber nicht vollständig überstimmen (Tie-Breaker und Verstärker).

### 3.1 Score-Formel

```python
graph_proximity = f(distance)
entrypoint_boost = g(distance)

raw_graph_bonus = (w_graph * graph_proximity) + (w_entry * entrypoint_boost)

graph_bonus = min(raw_graph_bonus, cap)

final_score = (w_bm25 * bm25_norm) + graph_bonus + penalties
```

*Hinweis:* Der Graph-Bonus wird relativ zum lexical score gecappt (`cap`). Der Graph dient als Verstärker / Tie-Breaker, nicht als dominantes Alleinsignal.

### 3.2 Definition der Bonus-Werte

* **Distanz 0 (Entrypoint):**
  * `graph_proximity = 1.0`
  * `entrypoint_boost = 1.0`
* **Distanz > 0 (Reachable):**
  * `graph_proximity = 1.0 / (distance + 1.0)`
  * `entrypoint_boost = 0.0`
* **Distanz -1 / Unreachable:**
  * `graph_proximity = 0.0`
  * `entrypoint_boost = 0.0`

### 3.3 Caps und Begrenzungen
* Der Graph-Bonus ist durch die Gewichtungsfaktoren (`w_graph`, `w_entry`) strikt nach oben begrenzt.
* Ein lexikalischer "perfect match" ohne Graph-Verbindung wird typischerweise immer noch höher gerankt als ein schwacher lexikalischer Treffer mit perfekter Graph-Verbindung, abhängig von der exakten Parameterisierung der Gewichte.

---

## 4. Fehlerpfade und Diagnose

Fehlt das Artefakt `graph_index.json` oder ist es ungültig, bricht die Query-Runtime nicht hart ab. Stattdessen:
* Die Suche wird im "Baseline"-Modus (ohne Graph-Bonus) ausgeführt.

Das `explain`-Objekt der Query enthält Diagnoseinformationen zur Graph-Nutzung.

### 4.1 `graph_used`

Gibt an, ob ein geladener Graph tatsächlich in das Ranking eingeflossen ist:
* `true` → Ein Graph wurde im Scoring verwendet. Das kann sowohl bei `graph_status = "ok"` als auch bei `graph_status = "stale_or_mismatched"` gelten.
* `false` → Es wurde kein Graph im Scoring verwendet, z. B. bei `graph_status = "not_found"`, `"invalid_json"`, `"invalid_schema"` oder `"unreadable"`.

### 4.2 `graph_status`

Gibt detailliert Auskunft über den Zustand des geladenen Graphen. Folgende Werte sind definiert:

* `ok` → Graph erfolgreich geladen und validiert.
* `not_found` → Datei nicht gefunden.
* `invalid_json` → Datei konnte nicht als JSON geparst werden.
* `invalid_schema` → JSON entspricht nicht dem `architecture.graph_index` Contract.
* `stale_or_mismatched` → Graph verweist auf einen anderen Dump-Index (Hash-Mismatch).
* `unreadable` → IO-Fehler (z.B. fehlende Leserechte).
