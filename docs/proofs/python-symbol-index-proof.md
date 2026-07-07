# Python Symbol Index Proof

Status: done
Task: `RBV1-T016`

## Result

This slice adds an optional deterministic Python AST symbol index v1.

The index reports:

- classes
- functions
- async functions
- methods through qualified names
- module names
- source paths
- start and end lines
- `file:<path>#L<start>-L<end>` range refs
- simple decorator names when statically visible
- skipped parse errors without aborting the whole index

## Boundary

The symbol index is read-only. It parses Python source with the standard library
`ast` module and does not import modules, execute source code, inspect runtime
objects, mutate Git, refresh snapshots, create patches, create pull requests or
run tests as a RepoBrief verdict.

The index is optional and diagnostic. It can help an agent locate likely code
surfaces, but it cannot prove call graph completeness, dependency completeness,
runtime behavior, import success, test sufficiency, review impact or merge
readiness.

## Validation

```text
pytest -q merger/lenskit/tests/test_python_symbol_index.py
# 2 passed
```

## Non-claims

This slice does not establish call graph completeness, dependency completeness,
runtime behavior, import success, test sufficiency, review completeness,
retrieval improvement, security correctness, regression absence or merge
readiness.
