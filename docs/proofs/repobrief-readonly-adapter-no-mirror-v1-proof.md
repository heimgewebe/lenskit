# RepoBrief Read-only Adapter without Mirror Authority v1 — proof

Status: local runtime validation complete
Technical commit: `7801ecc0e13cad70e041556e7ac08c1c7a9daf29`
Technical tree: `f29839c28db176705629157ffd4c63e75b310c5f`

## Implemented boundary

The protocol-neutral adapter accepts only exact manifests beneath explicit
allowed roots. Content reads are path-contained, size-bounded and checked
against manifest byte length and SHA-256. Missing or altered evidence fails
closed. Adapter dispatch contains no Git, shell, network, snapshot creation or
write implementation.

## Real-bundle validation

A clean checkout at the technical commit produced a redacted `full-max` bundle:

```text
bundle manifest SHA-256  f71dabc733670e847570c6bda99e87f83be9f8f575c0eb42b7f6e5d30667e765
manifest artifacts       21
generated files          26
post-emit health          pass
surface validation       pass
agent export gate         pass
export safety             pass
```

The adapter listed exactly the one configured snapshot. Query and symbol reads
succeeded. Hash inventories of all bundle files before and after every read were
byte-identical. No SQLite WAL, SHM or journal file was created.

## Focused tests

The adapter/evaluation suite contains 16 passing tests. It covers root escape,
unknown registration, hidden unregistered manifests, integrity drift, read-only
SQLite use, absence of SQLite sidecars, forbidden action dispatch, CLI list/call,
goldset schema and bounded usefulness evaluation.

## Compatibility contract

`docs/contracts/repobrief-readonly-adapter-compatibility.v1.json` binds every
adapter action to its library method and CLI entry. It separately labels MCP
surfaces as shared, analogous or unbound. This prevents an undocumented claim
that a code-level adapter is already an MCP transport server.

## Non-claims

The proof does not establish MCP deployment, authentication, remote freshness,
repository understanding, answer correctness, test sufficiency, review
completeness, security completeness or merge readiness.
