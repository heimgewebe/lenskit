# Graph Resolution and Layer Goldset v1.1 Baseline

## Status

G4b expands the diagnostic goldset after G4a saturated the original fixture. This slice changes the measurement contract and fixture repository only. It does not change the static Python graph producer, graph ranking, Relation Cards, or default graph use.

## Measurement surface

The versioned goldset is `docs/retrieval/graph_quality_goldset.v1.json`. Version 1.1 adds falsifiable coverage for:

- a package import resolved through `<package>/__init__.py`;
- a conventional `src/` layout whose configured import root is not represented by the producer;
- a namespace-package-style path without `__init__.py` and without configured import-root metadata;
- two possible search-root targets that must not be selected arbitrarily;
- syntactically invalid Python that is seen but not emitted as a file node;
- overlapping layer segments that make precedence observable.

The evaluator is `merger/lenskit/architecture/graph_quality_eval.py`. It emits deterministic case-level results, aggregate metrics, and parse coverage. The committed machine-readable result is `docs/diagnostics/graph-quality-baseline.v1.json`.

## G4a and expanded G4b surface

| Metric | G4a surface | G4b v1.1 surface |
| --- | ---: | ---: |
| Local resolution recall | 4 / 4 = 1.0 | 5 / 7 = 0.714286 |
| External preservation accuracy | 2 / 2 = 1.0 | 3 / 3 = 1.0 |
| Layer assignment accuracy | 6 / 6 = 1.0 | 8 / 8 = 1.0 |
| Unknown layer share among file nodes | 1 / 6 = 0.166667 | 10 / 17 = 0.588235 |
| Declared parse failures handled | not measured | 1 / 1 = 1.0 |

The lower local-resolution recall is not a producer regression. The denominator changed: G4b adds two intentionally unresolved layouts. The package `__init__.py` case resolves, while `src/` and namespace import-root cases expose the missing search-root model.

The higher unknown-layer share is likewise a changed fixture population, not evidence that existing layer assignments degraded. Most new packaging files deliberately lack `cli`, `core`, `test`, `infra`, `scripts`, or `tools` path segments.

## Case-level findings

### Resolved

- repository-relative absolute imports remain resolved;
- relative imports remain resolved;
- `import package_case.pkg` resolves to `package_case/pkg/__init__.py`;
- test paths override a nested `core` segment;
- `core` overrides a containing `tools` segment under the documented precedence.

### Open gaps

- `from acme.service import run` does not resolve to `src_layout/src/acme/service.py` because no import-root configuration declares `src_layout/src` as a Python search root;
- `from acme.alpha import run` does not resolve to `namespace_case/acme/alpha.py` because repository-relative module names are not the same as configured namespace roots.

### Preserved uncertainty

`import mod` has two fixture candidates under different possible search roots. The graph retains `module:mod` and produces no local edge to either candidate. This is the intended result until import-root provenance can make the choice deterministic.

### Parse failure

The invalid fixture is counted in `files_seen`, excluded from `files_parsed`, and has no file node. The baseline records `18` files seen, `17` parsed, and one parse failure. The current producer logs the parse problem; this goldset does not claim a persisted per-file diagnostic artifact.

## Decision boundary for the next producer slice

A later G4c should not infer `src/` or namespace roots from directory names alone. A safe implementation needs an explicit, deterministic source-root surface, for example configuration or packaging metadata with documented precedence and ambiguity handling. Until that contract exists, unresolved cases are preferable to invented local edges.

The goldset metric `unknown_file_share` counts file nodes only. The architecture-graph field `coverage.unknown_layer_share` retains its broader graph-wide meaning and may also count external nodes.

## Non-claims

This baseline does not establish runtime import behavior, effective `sys.path`, installed-package state, runtime causality, graph completeness, layer ontology completeness, retrieval benefit, change impact, test sufficiency, or readiness to enable graph ranking by default.
