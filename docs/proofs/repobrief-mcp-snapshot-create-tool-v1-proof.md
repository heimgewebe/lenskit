# RepoBrief MCP snapshot_create tool v1 proof

Task: `RBV1-T011`  
Status: implementation proof for the code-level handler, not an MCP server proof.

## What changed

RepoBrief now has an explicit MCP-shaped `snapshot_create` handler at:

```text
merger.lenskit.core.repobrief_mcp_tools.snapshot_create
```

The existing CLI generator path remains available as:

```text
repobrief snapshot create
```

The CLI implementation now exposes `build_snapshot_create_result(...)` so the MCP-shaped handler can reuse the same deterministic generator without scraping printed JSON.

## Guards

The handler requires:

- explicit repository path;
- explicit snapshot profile;
- explicit controlled output root;
- optional relative output subdirectory that cannot escape the output root;
- timeout guard;
- maximum total repository content-size guard;
- per-file size guard forwarded to the existing snapshot generator.

The handler rejects an output directory that is the repository or is inside the repository.

## Boundary

The handler may write only Brief Bundle artifacts. It does not mutate:

- Git state;
- pull requests;
- patches;
- the source working tree.

Read-only RepoBrief helpers remain read-only and do not call the MCP-shaped write handler as fallback.

## Non-claims

This proof does not establish:

- MCP protocol server availability;
- transport/security correctness;
- runtime correctness;
- test sufficiency;
- review completeness;
- repository truth;
- PR mergeability;
- forensic readiness.
