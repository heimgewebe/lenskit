# RBAW Production Sandbox v1

## Decision

The first production adapter for external patch evaluation uses a transient
`systemd --user` service on cgroup v2 and invokes the existing Bubblewrap
Sidecar unchanged.

The adapter is an execution boundary, not a second orchestrator. It accepts the
existing Sidecar request, snapshots the request and patch, starts one transient
unit with explicit aggregate limits, reads the existing
`repobrief.patch_evaluation` artifact, and emits a separate runner receipt that
binds policy, cgroup identity, accounting, artifact digest, and terminal result.

## Alternatives

### Transient systemd service — selected

Advantages:

- reuses the host's existing cgroup-v2 and service lifecycle machinery;
- keeps the current Bubblewrap filesystem, PID, and network boundary;
- adds no image registry or VM image supply chain;
- provides `MemoryMax`, `MemorySwapMax`, `TasksMax`, `CPUQuota`,
  `RuntimeMaxSec`, IO bandwidth controls, accounting, kill-on-unit-stop, and a
  stable Invocation ID;
- can fail closed when the user manager or required controller delegation is
  unavailable.

Costs and limits:

- requires a working user systemd manager and delegated `cpu`, `memory`, `pids`,
  and `io` controllers;
- filesystem quota is implemented by a per-unit bounded tmpfs rather than a
  project quota;
- the adapter is Linux-specific.

### Rootless container — deferred

A rootless container can express similar resource limits, but adds an image,
registry, runtime, and rootless-cgroup delegation contract. That would duplicate
parts of the current Bubblewrap and source-provenance boundary before a need for
an image-based environment has been demonstrated.

### MicroVM — deferred strongest tier

A MicroVM gives the strongest kernel boundary for hostile code. It also adds a
kernel/rootfs supply chain, boot lifecycle, artifact transport, networking, and
substantially higher operational cost. It remains the escalation path for code
that must not share the host kernel.

## Boundary composition

1. The runner validates paths and limits before mutation.
2. It snapshots the request and patch into an owner-only staging directory.
3. The source repository and snapshots are read-only to the transient service.
4. The output directory is the only persistent writable host path.
5. Sidecar workspace and scratch live in a size-bounded tmpfs.
6. The complete service process tree runs in one cgroup with aggregate memory,
   swap, CPU-rate, task-count, IO-rate, and wall-clock limits.
7. Existing Sidecar per-command RLIMITs remain defense in depth.
8. The runner reads systemd accounting and the Sidecar artifact after terminal
   completion, then atomically publishes a receipt outside the unit.
9. Cleanup requires the exact unit name, Invocation ID, and staging
   device/inode identity. Foreign resources are never adopted.

## Resource interpretation

- `workspace_max_bytes` is a hard tmpfs capacity for checkout, object pack,
  patch snapshot, home, and temporary files inside the service namespace.
- `memory_max_bytes` and `memory_swap_max_bytes` are aggregate cgroup limits.
- `cpu_quota_percent` is the aggregate CPU share. Together with
  `runtime_max_seconds` it yields a derived maximum CPU-time budget.
- `tasks_max` covers processes and threads in the complete unit.
- read/write bandwidth limits apply to every discovered block-backed input or
  persistent-output device. Together with the runtime limit they yield derived
  maximum block-IO byte budgets.
- tmpfs IO is bounded by `workspace_max_bytes`; persistent logs remain bounded
  by the existing Sidecar request contract.

## Failure semantics

Missing controller delegation, an unusable user manager, output collision,
ambiguous device resolution, namespace-policy rejection, timeout, OOM kill,
resource failure, missing or malformed Sidecar artifact, identity mismatch, or
unproven cleanup produces runner `status: error`.

A Sidecar `failed` artifact remains a patch-command failure and is not promoted
to infrastructure error merely because `systemd-run --wait` returns nonzero.

## Non-claims

The runner receipt is external runtime evidence. It does not establish patch
correctness, test sufficiency, security correctness, merge readiness, merge
authorization, or equivalence to a MicroVM boundary.
