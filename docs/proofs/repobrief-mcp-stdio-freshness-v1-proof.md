# RepoBrief MCP stdio and live freshness v1 proof

Status: review-ready implementation; final PR-head attestation remains PR metadata.
Bureau: `heimgewebe/bureau#468`
Pull request: `heimgewebe/lenskit#992`
Branch: `feat/repobrief-mcp-stdio-freshness-v1`

## Result

This slice adds the local protocol binding between MCP clients and the existing RepoBrief
code-level surfaces:

- newline-delimited JSON-RPC stdio lifecycle;
- `initialize`, `ping`, `tools/list`, `tools/call`, `resources/list`,
  `resources/templates/list`, and `resources/read`;
- bindings for existing `ask_context`, `grounding_verify`, and resource handlers;
- a checkout-independent absolute-path launcher;
- opt-in binding for the existing explicit `snapshot_create` write handler;
- a separate live-freshness result that compares one snapshot with one explicitly configured
  checkout.

## Freshness contract

A snapshot is `fresh` only when:

1. an operator explicitly configured `repo_root`;
2. snapshot Git provenance identifies that checkout;
3. snapshot cleanliness is explicitly `false`;
4. current Git provenance is present;
5. current cleanliness is explicitly `false`;
6. snapshot commit and current `HEAD` match.

A mismatch or dirty state is `stale`. Missing evidence is not promoted to fresh. A
manifest-recorded path is evidence, not filesystem permission. No result performs an implicit
rebuild or network operation.

## Security boundary

- MCP manifest arguments remain inside the configured bundle root.
- Citation-map overrides remain inside the selected bundle directory.
- Live Git inspection runs only against the operator-provided `--repo-root`.
- Git inspection is direct, read-only, time-bounded, network-free, and disables optional locks,
  fsmonitor, global/system Git configuration, and terminal prompts.
- `snapshot_create` is absent from `tools/list` unless explicitly enabled at server startup.
- Enabling `snapshot_create` requires `--repo-root`; source repository and output root are fixed
  to startup configuration and cannot be replaced by tool arguments.
- No TCP/HTTP listener, Git mutation, shell, patch, PR, secret, review, fix, or merge authority is
  introduced.

## Runtime and CI validation

The implementation head immediately before this proof-only update was:

```text
e311a94e1dc5cc3394738d4367d043e2427b287a
```

All repository checks completed successfully for that head:

- `test-suite` run `29228459238`: full pytest, browser tests, WebUI JavaScript tests, and
  deterministic release candidate;
- `lint` run `29228459209`: Ruff plus graph and complexity maintainability ratchets;
- `CodeQL` run `29228459194`;
- `contracts-validate` run `29228459761`;
- `task-index` run `29228459260`;
- `Doc-Freshness` run `29228459270`;
- `ai-context guard` run `29228459204`.

The test surface includes:

- an actual subprocess handshake through `scripts/repobrief-mcp-stdio.py` from outside the
  Lenskit checkout;
- tool and resource protocol calls;
- bundle, citation-map, repository, and output-root authority guards;
- a real temporary Git repository proving clean-to-dirty freshness transitions while preserving
  `HEAD` and the Git index bytes;
- fail-closed missing, ambiguous, malformed, dirty, and unavailable states.

The final PR head, complete diff SHA-256, and critical self-review are supplied after the final
proof-only CI run without another source-tree mutation.

## Does not establish

This proof does not establish network transport security, authentication, remote freshness,
repository truth, answer correctness, complete code understanding, runtime correctness, test
sufficiency, review completeness, regression absence, public distribution readiness, or merge
readiness by itself.
