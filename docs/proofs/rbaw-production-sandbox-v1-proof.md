# RBAW Production Sandbox v1 — Implementation Proof

## Bound revision

Implementation base: RepoGround `24eee84dd845fcf5f3a4a82c9e42e64428e76d6d`.

## Implemented slice

`tools/patch_evaluation_systemd_runner.py` wraps the existing external Sidecar
without importing it into RepoGround core.

The runner:

- requires Linux, cgroup v2, a working systemd user manager, and the `cpu`,
  `memory`, `pids`, and `io` controllers;
- validates bounded numeric limits and requires one empty, current-user-owned mode-`0700` persistent output root;
- separately hashes the original request, snapshots the rewritten execution request and patch with read-only modes, and verifies both snapshots after execution;
- resolves every block-backed source/output device before mutation;
- launches one UUID-named transient user service with aggregate memory, swap,
  task, CPU, runtime, and IO-rate limits;
- gives the unit a bounded tmpfs for all Sidecar workspace and scratch data;
- exposes the source and snapshots read-only and only the dedicated output root writable;
- preserves the existing Bubblewrap network-deny and per-command RLIMIT layers;
- retains successful terminal units long enough to read Invocation ID, cgroup path, result, exit information, accounting, effective systemd properties, and the actual `memory.max`, `memory.swap.max`, `pids.max`, `cpu.max`, and `io.max` kernel files;
- distinguishes a valid Sidecar `failed` artifact from systemd resource failure;
- treats OOM, timeout, signal, resource, missing artifact, malformed artifact,
  or unproven cleanup as runner `error`;
- binds the pre-launch runner/Sidecar producer digest, verifies it after execution, and atomically publishes a strict receipt that hashes the Sidecar artifact and combined systemd/kernel policy readback;
- cleans only the exact unit Invocation ID and staging device/inode identity, and refuses receipt publication if the output-root identity changed.

## Regression coverage

`tests/test_patch_evaluation_systemd_runner.py` covers:

- aggregate CPU and multi-device IO ceiling derivation plus kernel cgroup enforcement readback;
- strict limit validation;
- bounded immutable request/patch snapshots and producer drift detection;
- exact systemd property generation and effective-policy readback;
- namespace policy and exclusive persistent-output-root enforcement;
- preservation of Sidecar command failure semantics;
- OOM and cleanup-proof error precedence;
- foreign staging identity refusal;
- atomic receipt no-overwrite behavior;
- block-device fail-closed behavior;
- request rewrite and patch digest binding;
- source-boundary path rejection;
- cgroup-v2 absence.

## Deliberate non-claim

CI unit tests exercise policy construction and failure semantics without claiming
a live delegated user cgroup. Bureau #979 remains open until a real host run binds
systemd version, delegated controllers, unit Invocation ID, cgroup path, enforced
limits, patch digest, accounting, terminal status, and cleanup readback.

A MicroVM remains the later strongest tier for code that must not share the host
kernel.
