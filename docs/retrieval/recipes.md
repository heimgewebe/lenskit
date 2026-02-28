# Retrieval Recipes

> FTS5 + bm25 sind Voraussetzung für den FTS-Modus. Meta-only Queries (ohne Suchtext `--q`) funktionieren weiterhin ohne FTS.

## Manifest Policy
Um zirkuläre Hashes zu vermeiden, teilt Lenskit die Artefakte strikt in zwei Manifest-Schichten auf (basierend auf Suffix-Konventionen):
- `<base>.dump_index.json`: Kanonische Wahrheit (Markdown, JSON Sidecar, Chunk Index). Stabil und forensisch prüfbar.
- `<base>.derived_index.json`: Beschleunigungsschicht (SQLite Index, Retrieval Eval). Enthält `canonical_dump_sha256` als Rückreferenz auf das Hauptmanifest. `canonical_dump_sha256` dient als Bindeglied, um stale Indizes erkennen zu lassen (durch Vergleich gegen das aktuelle dump manifest).

## 1. Index Erstellen

Indexieren eines "<base>.dump_index.json" und "<base>.chunk_index.jsonl" Paares.

```bash
python -m merger.lenskit.cli index --dump output/my_dump.json --chunk-index output/my_chunks.jsonl --out output/my_index.sqlite
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
