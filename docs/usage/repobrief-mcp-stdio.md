# RepoBrief MCP stdio

RepoBrief can run as a local Model Context Protocol server over standard input and output.
The server exposes existing RepoBrief bundles and handlers; it does not invent a second
snapshot or grounding implementation.

## Start

```bash
python3 -m merger.lenskit.cli.repobrief_mcp_stdio \
  --bundle-root /absolute/path/to/briefs \
  --repo-root /absolute/path/to/repository
```

`--bundle-root` may name either a directory containing `*.bundle.manifest.json` files or
one exact bundle manifest. `--repo-root` is optional, but without it live freshness is
reported as `not_comparable` and no Git probe runs.

The default server is read-only. The existing explicit bundle-writing tool is exposed only
when the operator deliberately adds:

```text
--enable-snapshot-create
```

## Generic MCP client configuration

Clients that accept an MCP stdio command can use this shape:

```json
{
  "mcpServers": {
    "repobrief": {
      "command": "python3",
      "args": [
        "-m",
        "merger.lenskit.cli.repobrief_mcp_stdio",
        "--bundle-root",
        "/absolute/path/to/briefs",
        "--repo-root",
        "/absolute/path/to/repository"
      ]
    }
  }
}
```

The client-specific file location or registration command varies. The command and arguments
above are the stable RepoBrief side of the contract.

## Exposed tools

Read-only by default:

- `ask_context`: builds the existing cited context pack from one registered bundle;
- `grounding_verify`: runs the existing declaration and evidence verifier;
- `live_freshness`: compares the snapshot commit and cleanliness with the configured checkout.

Optional explicit write tool:

- `snapshot_create`: available only with `--enable-snapshot-create`; it may write Brief Bundle
  artifacts under its existing output, timeout, and size guards.

## Exposed resources

The server lists and reads the existing resource surface:

- `repobrief://snapshot/{stem}/manifest`
- `repobrief://snapshot/{stem}/canonical`
- `repobrief://snapshot/{stem}/reading-pack`
- `repobrief://snapshot/{stem}/health`
- `repobrief://snapshot/{stem}/availability`
- `repobrief://snapshot/{stem}/artifact/{role}`

Resource results retain the existing health, availability, and snapshot-bound freshness
metadata. When `--repo-root` is configured, the result metadata also includes live freshness.

## Freshness meanings

- `fresh`: snapshot commit equals local `HEAD`, and both the snapshot and current tree are clean;
- `stale`: the commit differs, the current tree is dirty, or the snapshot was created dirty;
- `unknown`: required snapshot provenance or cleanliness evidence is missing;
- `not_comparable`: no checkout was configured, Git is unavailable, or current cleanliness
  cannot be established.

A read never invokes `snapshot_create`, `git fetch`, `git pull`, or another repair action.
Staleness is reported, not hidden.

## Security boundary

- tool-supplied manifests must remain inside the configured bundle root;
- an optional citation map must remain inside the selected bundle directory;
- the MCP client cannot select an arbitrary Git checkout: the probe is bound to `--repo-root`;
- the Git probe disables optional locks, fsmonitor, global Git configuration, system Git
  configuration, and terminal prompts;
- the server has no TCP or HTTP listener and writes only MCP JSON-RPC messages to stdout;
- Git push/pull/fetch, shell execution, patches, pull requests, secrets, reviews, fixes, and
  merges remain outside the server authority.

Successful access or a `fresh` verdict does not establish repository truth, answer correctness,
test sufficiency, review completeness, runtime correctness, or merge readiness.
