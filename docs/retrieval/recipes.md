# Retrieval Recipes

> FTS5 + bm25 sind Voraussetzung für den FTS-Modus. Meta-only Queries (ohne Suchtext `--q`) funktionieren weiterhin ohne FTS.

## Manifest Policy
Um zirkuläre Hashes zu vermeiden, teilt Lenskit die Artefakte strikt in zwei Manifest-Schichten auf (basierend auf Suffix-Konventionen):
- `<base>.dump_index.json`: Kanonische Wahrheit (Markdown, JSON Sidecar, Chunk Index). Stabil und forensisch prüfbar.
- `<base>.derived_index.json`: Beschleunigungsschicht (SQLite Index, Retrieval Eval). Enthält `canonical_dump_sha256` als Rückreferenz auf das Hauptmanifest. `canonical_dump_sha256` dient als Bindeglied, um stale Indizes erkennen zu lassen (durch Vergleich gegen das aktuelle dump manifest).

## 1. Index Erstellen

Indexieren eines "<base>.dump_index.json" und "<base>.chunk_index.jsonl" Paares.

```bash
python -m merger.lenskit.cli index \
  --dump output/<base>.dump_index.json \
  --chunk-index output/<base>.chunk_index.jsonl \
  --out output/<base>.chunk_index.index.sqlite
```

## 2. Index Prüfen

Überprüfen, ob ein Index aktuell (fresh) ist.

```bash
python -m merger.lenskit.cli index --dump output/my_dump.json --chunk-index output/my_chunks.jsonl --verify
```

## 3. Einfache Suche

Suche nach einem Begriff in allen Dateien.

```bash
python -m merger.lenskit.cli query --index output/my_index.sqlite --q "authentication"
```

## 4. Suche mit Repo-Filter

Suche nach "user" nur im Repository "backend".

```bash
python -m merger.lenskit.cli query --index output/my_index.sqlite --q "user" --repo backend
```

## 5. Suche nach Dateityp

Suche nach "schema" nur in SQL-Dateien.

```bash
python -m merger.lenskit.cli query --index output/my_index.sqlite --q "schema" --ext sql
```

## 6. Suche im Core-Layer

Suche nach "logging" nur im "core" Layer (Architektur).

```bash
python -m merger.lenskit.cli query --index output/my_index.sqlite --q "logging" --layer core
```

## 7. Pfad-basierte Suche

Suche nach "config" in Dateien, deren Pfad "settings" enthält.

```bash
python -m merger.lenskit.cli query --index output/my_index.sqlite --q "config" --path settings
```

## 8. JSON-Output für Agenten

Strukturierte Ausgabe für maschinelle Verarbeitung.

```bash
python -m merger.lenskit.cli query --index output/my_index.sqlite --q "error" --emit json
```

## 9. Limitierte Ergebnisse

Nur die Top-3 Treffer anzeigen.

```bash
python -m merger.lenskit.cli query --index output/my_index.sqlite --q "main" --k 3
```

## 10. Rebuild erzwingen

Index neu bauen, auch wenn er aktuell scheint.

```bash
python -m merger.lenskit.cli index --dump output/my_dump.json --chunk-index output/my_chunks.jsonl --rebuild
```

## 11. Query Claim Boundaries

Jedes Query-Result-Objekt enthält ein maschinenlesbares `claim_boundaries`-Feld.

```json
{
  "claim_boundaries": {
    "proves": [
      "These hits were returned by this index under this query and these filters."
    ],
    "does_not_prove": [
      "Absence of a hit does not prove absence in the repository.",
      "Ranking does not prove semantic importance.",
      "Snapshot query does not prove live repository state.",
      "Best-effort explain output is diagnostic, not canonical truth."
    ],
    "evidence_basis": ["query", "fts_query", "applied_filters", "index", "result_ranges"],
    "requires_live_check": false
  }
}
```

**Was ein Query-Treffer belegt:** Dieser Index hat unter dieser Query und diesen Filtern diesen Treffer zurückgegeben.

**Was ein Query-Treffer nicht belegt:**
- Dass ein nicht gefundener Inhalt im Repository fehlt (Absence of evidence ≠ evidence of absence).
- Dass Platz 1 semantisch wichtiger ist als Platz 3.
- Dass der Snapshot dem Live-Repository-Zustand entspricht.
- Dass Explain-Ausgaben kanonische Wahrheit sind — sie sind diagnostisch und best-effort.

`evidence_basis` spiegelt den tatsächlichen Ausführungspfad: `fts_query` erscheint nur, wenn eine FTS-Query ausgeführt wurde; bei reinen Metadata-Queries fehlt es.

`requires_live_check: false` bedeutet, dass kein Live-Repository-Zugriff für die Trefferermittlung nötig war — nicht, dass die Ergebnisse mit dem aktuellen Repository-Zustand übereinstimmen.
