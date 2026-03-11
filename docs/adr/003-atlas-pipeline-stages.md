# ADR 003: Atlas uses pipeline stages, not monolithic scan flows

## Status
Accepted

## Context
A monolithic scanner process that attempts to do everything at once (discovery, analysis, enrichment) becomes slow, fragile, and memory-intensive, specially over a very large filesystem.

## Decision
Atlas uses a pipeline architecture with discrete stages:
1.  **Discovery**: Base metadata and path collection.
2.  **Snapshot**: Persistent storage of the discovery phase.
3.  **Enrichment**: Optional deeper data gathering (content parsing, etc.).
4.  **Derivation**: Synthesizing higher-level views (hotspots, topology).
5.  **Indexing**: Search and metadata indices.

## Consequences
- Requires explicitly passing artifacts or context between stages.
- Allows for decoupled operations, incremental processing, and selective enrichment.