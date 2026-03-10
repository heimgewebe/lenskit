# ADR 008: Official Atlas Directory Structure

## Status
Accepted

## Context
Atlas needs a predictable filesystem layout for its SQLite registries and raw file artifacts to enable cross-machine operations, backups, and predictable data management.

## Decision
The official directory structure for Atlas storage is as follows:

```text
atlas/
  machines/
    <machine_id>/
      roots/
        <root_id>/
          snapshots/
            <snapshot_id>/
              summary.md
              inventory.jsonl
              dirs.jsonl
              content.json
              topology.json
              hotspots.json
              workspaces.json
              snapshot_meta.json
  registry/
    atlas_registry.sqlite
  indexes/
    fts.sqlite
    semantic_chunks.sqlite
```

## Consequences
- The CLI and backend services must adhere to this structure when generating artifacts.
- It guarantees that a snapshot is completely self-contained within its specific path `atlas/machines/<machine_id>/roots/<root_id>/snapshots/<snapshot_id>/`.
- The single central registry SQLite file tracks metadata pointing into the `machines/` tree.