# Graph Local Resolution and Path Layers Proof

## Status

Implements the first measured G4 producer slice after `TASK-GRAPH-QUALITY-GOLDSET-001` established a reproducible baseline.

## Change

`generate_import_graph_document()` now builds a deterministic index from repository-relative Python module names to source paths. Absolute and relative imports produce local `file:` edges when one and only one path matches. `<module>.py` and `<package>/__init__.py` are supported. If both claim the same module name, the import remains an external `module:` edge; the producer does not guess.

For `from module import name`, the base module is retained when it resolves locally. The imported name is treated as a child module only when that child has its own unique local path. This prevents ordinary imported symbols from becoming invented module nodes.

File-node layers are inferred from explicit path segments. Test paths take precedence, followed by `cli`, `core`, and infrastructure segments (`infra`, `scripts`, `tools`). Unmatched paths remain `unknown`.

## Measured result

Against `docs/retrieval/graph_quality_goldset.v1.json`:

- local resolution recall: `1/4` to `4/4`;
- external preservation accuracy: remains `2/2`;
- layer assignment accuracy: `1/6` to `6/6`;
- unknown share among fixture file nodes: `1.0` to `1/6`.

The committed case-level result is `docs/diagnostics/graph-quality-baseline.v1.json`. The existing architecture-import golden snapshot also proves plain `import c`, local package imports, relative imports, star-import base preservation, and external standard-library imports.

## Negative semantics

- ambiguous local module names remain external;
- unavailable modules remain external;
- star imports are not expanded into symbols;
- path layers are heuristic labels, not architectural truth;
- no graph ranking default or retrieval weight changes;
- `coverage.unknown_layer_share` keeps its existing graph-wide semantics and is not redefined as file-only.

## Verification

Regression coverage includes schema validation, the architecture graph golden snapshot, ambiguous module collision handling, layer-precedence handling, goldset reproducibility, external-module preservation, Graph Model, Graph Bundle Sources, and Graph Quality Goldset CI gates.

## Non-claims

This work does not establish Python runtime import order, runtime causality, namespace-package completeness, `src/`-layout completeness, graph completeness, architectural importance, retrieval benefit, change impact, or test sufficiency.
