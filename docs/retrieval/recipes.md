# Retrieval Recipes

## 1. Index Erstellen

Indexieren eines "dump_index.json" und "chunk_index.jsonl" Paares.

```bash
lenskit index --dump output/my_dump.json --chunk-index output/my_chunks.jsonl --out output/my_index.sqlite
```

## 2. Index Prüfen

Überprüfen, ob ein Index aktuell (fresh) ist.

```bash
lenskit index --dump output/my_dump.json --chunk-index output/my_chunks.jsonl --verify
```

## 3. Einfache Suche

Suche nach einem Begriff in allen Dateien.

```bash
lenskit query --index output/my_index.sqlite --q "authentication"
```

## 4. Suche mit Repo-Filter

Suche nach "user" nur im Repository "backend".

```bash
lenskit query --index output/my_index.sqlite --q "user" --repo backend
```

## 5. Suche nach Dateityp

Suche nach "schema" nur in SQL-Dateien.

```bash
lenskit query --index output/my_index.sqlite --q "schema" --ext sql
```

## 6. Suche im Core-Layer

Suche nach "logging" nur im "core" Layer (Architektur).

```bash
lenskit query --index output/my_index.sqlite --q "logging" --layer core
```

## 7. Pfad-basierte Suche

Suche nach "config" in Dateien, deren Pfad "settings" enthält.

```bash
lenskit query --index output/my_index.sqlite --q "config" --path settings
```

## 8. JSON-Output für Agenten

Strukturierte Ausgabe für maschinelle Verarbeitung.

```bash
lenskit query --index output/my_index.sqlite --q "error" --emit json
```

## 9. Limitierte Ergebnisse

Nur die Top-3 Treffer anzeigen.

```bash
lenskit query --index output/my_index.sqlite --q "main" --k 3
```

## 10. Rebuild erzwingen

Index neu bauen, auch wenn er aktuell scheint.

```bash
lenskit index --dump output/my_dump.json --chunk-index output/my_chunks.jsonl --rebuild
```
