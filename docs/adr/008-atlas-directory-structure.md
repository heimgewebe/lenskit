# ADR 008: Official Atlas Directory Structure

## Status
Accepted

## Context
Atlas needs a predictable filesystem layout for its SQLite registries and raw file artifacts to enable cross-machine operations, backups, and predictable data management.

## Decision
The official **canonical target structure** for Atlas storage is as follows.

*(Note: While the Registry is already correctly initialized at this location, flat file artifacts are currently still emitted to the working directory. A full migration of artifacts to this target snapshot path is pending in a future phase).*

```text
atlas/
  machines/
    <machine_id>/
      roots/
        <root_id>/
          snapshots/
            <snapshot_id>/
              <scan_id>.summary.md
              <scan_id>.inventory.jsonl
              <scan_id>.dirs.jsonl
              <scan_id>.content.json
              <scan_id>.topology.json
              <scan_id>.hotspots.json
              <scan_id>.workspaces.json
              <scan_id>.snapshot_meta.json
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