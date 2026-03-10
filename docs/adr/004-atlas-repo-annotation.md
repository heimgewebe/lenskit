# ADR 004: Repo/workspace detection is annotation only

## Status
Accepted

## Context
When an application primarily sees the world as software projects, it tends to group and process files around repository boundaries. This obscures raw filesystem context and forces everything into an IDE-like perspective, which is against the mandate of Atlas.

## Decision
Repository and workspace detection (e.g. looking for `.git` directories, `pyproject.toml`) will be implemented as a purely optional annotation layer. It does not dictate the core ontology of Atlas.

## Consequences
- Core metrics, search, and history must be driven by paths, roots, and machines, not repo IDs.
- Workspace data will be a derived projection (e.g., `workspaces.json`), separate from the base inventory.