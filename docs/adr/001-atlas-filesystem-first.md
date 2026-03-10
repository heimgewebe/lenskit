# ADR 001: Atlas is filesystem-first, not repo-first

## Status
Accepted

## Context
The goal is to build a tool that observes the entire physical reality of a machine's filesystem, rather than solely focusing on source code repositories. Treating a repository as the center of the universe limits visibility and misses context (like backups, external drives, system files).

## Decision
Atlas must model the physical filesystem (Machines, Roots, Files, Directories) as its primary ontology. Repositories and workspaces are treated as annotations on top of this physical model, not the primary organizational structure.

## Consequences
- Atlas logic should not fail or degrade significantly when run outside a git repository.
- Core entities like `Machine` and `Root` must be explicitly modeled.
- Repository-specific processing happens as an optional enrichment layer.