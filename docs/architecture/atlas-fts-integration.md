# Atlas FTS Integration Design

## 1. Ausgangslage und Abgrenzung zum Ist-Zustand
Der aktuelle Suchmechanismus in Atlas (`merger/lenskit/atlas/search.py`) nutzt als linearen Fallback das iterative, zeilenweise Scannen von JSONL-Inventaren und (für Inhalte) das direkte Lesen vom Live-Dateisystem (`is_text`-Heuristik).
Dieser Ansatz ist ein best-effort Übergangszustand, der für kleine Roots ausreicht, aber bei großen Datenmengen nicht skaliert.
Gemäß der Atlas-Blaupause (Phase 4) und ADR-005 ist SQLite FTS5 als Suchtechnologie vorgesehen und im Repo für Lenskit-Chunks (`chunks_fts`) bereits technologisch etabliert.
Dieses Dokument definiert das Architekturdesign für die spezifische Integration von FTS5 in den Atlas-Bounded-Context.

## 2. Index-Inhalt
Was genau wird in den FTS-Index überführt?
*   **Pfade und Metadaten:** `rel_path`, `name`, `ext`, und potenziell aufbereitete Zeitstempel/Größen zur gefilterten Volltextsuche.
*   **Dateiinhalte (Content-Search):** Die Indizierung von Dateiinhalten ist konzeptionell an den `content`-Scan-Modus gebunden. Die genaue Text-Extraktionsstrategie (insbesondere für große Dateien oder non-UTF8) bleibt als Implementierungsdetail offen, muss sich aber an der `TEXT_DETECTION_MAX_BYTES`-Grenze (aktuell in `search.py` genutzt) orientieren.
*   **Kombination:** Die FTS-Tabelle muss eine kombinierte Suche über Pfad, Name und Inhalt (`content_snippet`) zulassen, ohne die Metadaten-Filterung (z.B. Dateigröße) zu brechen.

## 3. Snapshot-Bindung
Wie ist der Index an die maschinenweite Atlas-Historie gekoppelt?
*   **Globaler Index mit Snapshot-Referenzen:** Der FTS-Index (geplant als `fts.sqlite`) ist eine globale Suchstruktur, keine isolierte pro-Snapshot-Datei.
*   **Identität:** Jeder FTS-Eintrag muss zwingend mit `machine_id`, `root_id` und `snapshot_id` verknüpft sein.
*   **Historische Suche vs. Latest:** Die FTS-Struktur muss unterscheiden können, ob ein Suchtreffer aus dem *aktuellsten* Snapshot eines Roots stammt, oder ob historisch über alte Snapshots gesucht wird.

## 4. Update-Strategie
Wann wird indexiert?
*   **Nachgelagerte Indizierung (Derivation-Phase):** Die Indizierung in SQLite-FTS darf nicht den initialen Discovery-Scan (`inventory.jsonl`) verlangsamen oder blockieren. Sie erfolgt als nachgelagerter Schritt (z. B. als Teil von `atlas derive` oder einem impliziten asynchronen Worker-Prozess nach einem erfolgreichen `complete`-Snapshot).
*   **Rebuild vs. Inkrementell:** Offen. Ideal ist ein inkrementelles Update basierend auf Deltas zwischen Snapshots. Ein vollständiger Rebuild aus `inventory.jsonl` muss jedoch als Fallback zur Fehlerbehebung garantiert sein.

## 5. Invalidierung
Wann wird der Index als veraltet betrachtet?
*   Wenn ein Snapshot aus der Registry gelöscht wird, müssen die zugehörigen Einträge im FTS-Index kaskadierend entfernt oder als ungültig markiert werden.
*   Bei inkrementellen Updates überschreibt der neue Snapshot (`to_snapshot_id`) die "Latest"-Markierung der alten Datensätze desselben `rel_path` im selben Root.
*   Das exakte Schema für "Tombstones" (als gelöscht markierte Dateien in neueren Snapshots) muss vor der Implementierung finalisiert werden.

## 6. Query-Modell
Wie interagiert die Suche mit dem System?
*   **Machine/Path/Content:** Die Query-API (`atlas search`) übersetzt Metadaten-Filter (`--min-size`, `--ext`) und Scope-Filter (`machine_id`, `root_id`) in reguläre SQL-`WHERE`-Klauseln, während `content_query` und `path_pattern` an den FTS-`MATCH`-Operator delegiert werden.
*   **Cross-Machine Queries:** Da `machine_id` Teil des Index-Schemas ist, sind systemweite Suchanfragen nativ möglich, sofern die entsprechenden Snapshots in der Registry verankert sind.
*   **Live-Fallback:** Die Inhaltssuche vom Live-Dateisystem (wie aktuell in `search.py` für Nicht-Content-Scans) sollte als hybrider Fallback erhalten bleiben, falls ein Root ohne Content-Enrichment gescannt wurde.

## 7. Offene architektonische Fragen (Epistemische Leerstellen)
*   **Tombstone-Design:** Wie genau repräsentieren wir Dateien in FTS, die in Snapshot N existierten, aber in N+1 gelöscht wurden?
*   **Inkrementelles Indexing:** Reicht das Delta-Artefakt als alleinige Quelle für FTS-Updates, oder brauchen wir einen Full-Inventory-Abgleich?
*   **Hybride Suche:** Wie orchestriert `search.py` elegant den Wechsel zwischen FTS (falls indiziert) und linearem Live-Read (falls nur Inventory vorhanden)?
