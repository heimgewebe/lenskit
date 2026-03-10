# ADR 005: Registry in SQLite, large artifacts as files

## Status
Accepted

## Context
Atlas will generate large amounts of JSONL and raw data across many snapshots, roots, and machines. Querying this raw data frequently is slow. Keeping all of it in an index database like SQLite risks bloat. Keeping everything only in files makes metadata lookups slow.

## Decision
Atlas uses a hybrid approach:
- **Registry and Indexes:** Metadata about Machines, Roots, Snapshots, and Deltas, as well as fast search indices (FTS, chunk indices), are stored in SQLite (`atlas_registry.sqlite`, `fts.sqlite`).
- **Raw Data:** The actual discovery, enrichment, and derivation artifacts (`inventory.jsonl`, `content.json`, `topology.json`, etc.) are written directly to disk as flat files.

## Consequences
- Requires coordination between SQLite records and flat files.
- Ensures fast registry lookups while maintaining a portable history of flat files.