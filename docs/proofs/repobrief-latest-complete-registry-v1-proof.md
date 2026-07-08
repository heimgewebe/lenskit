# RepoBrief latest-complete registry v1 proof

Task: `RPU-V1-T003`

Status: implementation proof for the latest-complete RepoBrief bundle registry and read-only freshness status path.

## Implemented surface

This slice adds a small machine-readable registry with kind:

```text
repobrief.latest_complete_registry
```

The registry records:

- bundle stem;
- bundle manifest path;
- bundle manifest SHA-256;
- bundle run id;
- bundle generation timestamp;
- recorded source commit from `snapshot_provenance`;
- health summary from available health sidecars;
- freshness status vocabulary and explicit unknown state.

## Read-only status path

The read-only status command is:

```bash
python -m merger.lenskit.cli.main repobrief latest-complete status --registry <registry.json> [--repo <repo>]
```

Without `--repo`, source freshness is `unknown` with reason `live_repo_not_provided`.

With `--repo`, the status path compares the registry's recorded source commit with the explicit local repo `HEAD`:

- matching commit: `fresh`;
- different commit: `stale` with reason `head_drift`;
- unavailable repo or missing commit: `unknown`.

A stale result is not a failure by itself. It is a visible observation that consumers can use before relying on a bundle.

## Explicit write paths

The registry is written only by explicit write operations:

```bash
python -m merger.lenskit.cli.main repobrief latest-complete write --bundle-manifest <manifest> --out <registry.json>
```

or during explicit snapshot creation when the caller passes:

```bash
--latest-complete-registry <registry.json>
```

Read paths do not update the registry.

## Boundary

The read-only status path does not:

- create snapshots;
- refresh bundles;
- mutate Git;
- alter the source working tree;
- write registry files;
- write bundle artifacts;
- create pull requests;
- run tests or reviews.

## Validation scope

Tests cover:

- registry field emission;
- JSON-schema validation for emitted registries;
- health signal projection;
- fresh/stale/unknown freshness states;
- stale not being a failure by itself;
- read status not writing files or mutating the registry;
- CLI write and CLI status commands;
- optional explicit registry write during `snapshot create`.

## Non-claims

This proof does not establish:

- content truth;
- bundle completeness;
- runtime correctness;
- test sufficiency beyond the checked scope;
- review completeness;
- merge readiness;
- repo understanding;
- claim truth;
- freshness against a remote branch;
- agent quality improvement.
