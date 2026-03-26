# Atlas FTS Integration Design

Dieses Dokument definiert das Integrationsdesign für SQLite FTS5 in den Atlas-Bounded-Context. Um falsche Finalität zu vermeiden, trennt es explizit zwischen dem belegten Ist-Zustand, dem architektonisch präferierten Zielbild und den noch offenen Implementierungsentscheidungen.

## 1. Ausgangslage und Abgrenzung (Belegter Ist-Zustand)
- **Technologische Basis:** Gemäß der Atlas-Blaupause (Phase 4) und ADR-005 ist SQLite FTS5 als Suchtechnologie vorgesehen und im Repo für Lenskit-Chunks (`chunks_fts`) bereits technologisch etabliert.
- **Aktueller Atlas-Suchmechanismus:** Der aktuelle Suchmechanismus in Atlas (`merger/lenskit/atlas/search.py`) nutzt iteratives, zeilenweises Scannen von JSONL-Inventaren und (für Inhalte) das direkte Lesen vom Live-Dateisystem (`is_text`-Heuristik).
- **Einordnung:** Dieser aktuelle lineare Ansatz ist ein belegter Best-Effort-Übergangszustand, der für kleine Roots ausreicht, aber bei großen Datenmengen als Suchschicht nicht skaliert. Eine explizite FTS-Integration in die Atlas-Artefakte fehlt derzeit.

## 2. Präferiertes Integrationsmodell

Die folgenden Punkte beschreiben die architektonisch präferierte Richtung für die FTS-Integration, basierend auf den bestehenden Invarianten der Blaupause (Zustandsbehaftung, Pipeline-Architektur).

### 2.1 Index-Inhalt
Was sollte in den FTS-Index überführt werden?
*   **Pfade und Metadaten:** `rel_path`, `name`, `ext` und potenziell aufbereitete Zeitstempel/Größen zur gefilterten Volltextsuche.
*   **Dateiinhalte (Content-Search):** Die Indizierung von Dateiinhalten sollte konzeptionell an den `content`-Scan-Modus gebunden sein. Die Text-Extraktion (insbesondere für große Dateien oder non-UTF8) sollte sich an der `TEXT_DETECTION_MAX_BYTES`-Grenze orientieren.
*   **Kombination:** Die FTS-Struktur sollte eine kombinierte Suche über Pfad, Name und Inhalte (z. B. via `content_snippet`-Feld) zulassen, ohne Metadaten-Filterung (z.B. Dateigröße) zu brechen.

### 2.2 Snapshot-Bindung
Wie sollte der Index an die maschinenweite Atlas-Historie gekoppelt sein?
*   **Identität:** Jeder FTS-Eintrag sollte zwingend über `machine_id`, `root_id` und `snapshot_id` eindeutig referenzierbar sein.
*   **Globaler Index (Präferenz):** Ein globaler Index innerhalb der Atlas-Registry (`fts.sqlite`) mit expliziten Snapshot-Referenzen ist aktuell naheliegend, um maschinen- und root-übergreifende Abfragen effizient zu gestalten. (Eine per-Snapshot-Lösung wäre nur bei massiven Isolationsanforderungen geboten).
*   **Historische Suche:** Die Struktur sollte zwischen Suchtreffern aus dem *aktuellsten* Snapshot und historischen Suchanfragen differenzieren können.

### 2.3 Update-Strategie
Wann und wie sollte indexiert werden?
*   **Nachgelagerte Indizierung (Präferenz):** Um den initialen Discovery-Scan (`inventory.jsonl`) nicht zu blockieren, sollte die FTS-Indizierung als nachgelagerter Schritt (z. B. via `atlas derive` oder einen Worker nach einem `complete`-Snapshot) erfolgen. (Eine Inline-Indizierung direkt beim Content-Scan wäre alternativ zu prüfen).
*   **Inkrementelle Updates:** Ein inkrementelles Update basierend auf Delta-Artefakten ist präferiert. Ein vollständiger Rebuild aus `inventory.jsonl` sollte als Fehlerbehebungs-Fallback existieren.

### 2.4 Invalidierung
Wann wird der Index als veraltet betrachtet?
*   **Kaskadierende Löschung:** Wenn ein Snapshot aus der Registry entfernt wird, sollten die zugehörigen FTS-Einträge entfernt oder ungültig markiert werden.
*   **Überschreibung bei Inkrementen:** Bei inkrementellen Updates überschreibt der neue Snapshot logisch die "Latest"-Gültigkeit der alten Datensätze für denselben `rel_path` im selben Root.

### 2.5 Query-Modell
Wie sollte die Suche (`atlas search`) interagieren?
*   **SQL-Translation:** Metadaten-Filter (`--min-size`, `--ext`) und Scope-Filter (`machine_id`, `root_id`) sollten in reguläre `WHERE`-Klauseln übersetzt werden, während `content_query` und `path_pattern` an FTS-Operatoren (`MATCH`) delegiert werden.
*   **Cross-Machine Queries:** Sofern die Snapshots in der Registry verankert sind, sind systemweite Abfragen über die `machine_id` als Index-Dimension nativ möglich.
*   **Hybrider Fallback (Präferenz):** Falls ein Root ohne Content-Enrichment gescannt wurde (oder der Index unvollständig ist), sollte als Fallback auf das direkte Lesen vom Live-Dateisystem (wie in der aktuellen `search.py`) zurückgegriffen werden.

## 3. Offene Architekturentscheidungen (Vor Implementierung zwingend zu entscheiden)

Bevor Code für die FTS-Integration geschrieben wird, müssen die folgenden vier epistemischen Leerstellen hart entschieden und im Repo dokumentiert werden:

1.  **Index-Schnitt (Global vs. Per-Snapshot):**
    Wird `fts.sqlite` ein globaler Atlas-Index (Referenzierung via IDs) oder generieren wir isolierte FTS-Dateien pro Snapshot/Root?
2.  **Write-Path (Inline vs. Derive):**
    Wird die FTS-Indizierung synchron direkt während des `content`-Scans mitgeschrieben, oder asynchron/nachgelagert via `atlas derive` als Pipeline-Schritt generiert?
3.  **Deletion- und Tombstone-Modell:**
    Wie repräsentiert das FTS-Schema Dateien, die in Snapshot N existierten, in N+1 aber gelöscht wurden? Werden sie hart gelöscht, weich markiert (Tombstones) oder ausschließlich über die Join-Logik mit der Snapshot-Registry gefiltert?
4.  **Default-Query-Semantik (Latest-Only vs. Historisch):**
    Sucht `atlas search` standardmäßig nur in den *aktuellsten* Snapshots aller Roots (was eine performante `is_latest`-Markierung erfordert), oder durchsucht es historisch alle verknüpften Snapshots, sofern nicht explizit gefiltert?
