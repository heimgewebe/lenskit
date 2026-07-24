# RBAW-V1-T004 Patch Evaluation Integrity Hardening v2 — Proof

## Scope

This slice hardens the external Patch Evaluation Sidecar without moving mutable
execution into RepoGround core. The previously reviewed implementation is retained
byte-for-byte as `tools/patch_evaluation_sidecar_legacy.py`; the canonical entry
point installs a narrow hardening overlay before exposing the legacy API.

## Implemented boundaries

- Command evidence is sealed to a fingerprint of `HEAD`, local Git configuration,
  refs, tracked worktree diff, staged-index diff and every path changed by the
  applied patch.
- The fingerprint is checked immediately before and after every declared command.
  A command that resets the patch, changes Git configuration, moves refs, changes
  the index or mutates a patched path becomes an infrastructure `error`; later
  commands are recorded as `skipped`.
- `failed + skipped` remains `failed`. Incomplete execution no longer erases an
  observed command failure.
- stdout and stderr are drained concurrently into bounded in-memory buffers while
  the command runs. Published logs remain bounded and are mode `0600`.
- Commands run through the same Bubblewrap policy exercised by the runtime probe.
  A private PID, IPC, UTS and network namespace is used; `GIT_NO_LAZY_FETCH=1`
  prevents implicit promisor-remote fetches.
- `prlimit` bounds address space, individual file size, process count, open file
  count and CPU time for the Bubblewrap process and descendants.
- Sandbox startup is marked inside the namespace. Failure before the payload starts
  is recorded as infrastructure `error`, not as a failed test.
- Patch snapshots enforce the byte limit during copying rather than trusting an
  earlier `stat()` result.
- Workspace, runtime and log directories are created with mode `0700`. Cleanup is
  permitted only when the current device/inode identity matches the path created by
  this evaluation.
- Log directories include the evaluation UUID, so a foreign legacy log directory
  cannot block a later run.
- Producer provenance binds the canonical wrapper, immutable legacy core and
  hardening overlay before mutable evaluation and verifies the same digest during
  cleanup.
- An `os.link`/directory-fsync ambiguity is resolved by reading back the published
  artifact and accepting it only when its complete JSON value matches.

## Regression coverage

The original 47-test sidecar/consumer suite is retained and imported. Four tests
whose contracts deliberately changed are replaced, and focused regressions cover:

- patch removal followed by a nominally successful command;
- Git config and ref mutation;
- failure-preserving fail-fast aggregation;
- bounded high-volume output;
- exact sandbox-start classification;
- network deny and lazy-fetch disablement;
- foreign cleanup identity refusal;
- unique log publication; and
- ambiguous artifact-publication readback.

## Remaining non-claims

This slice does not establish total workspace or decompressed-checkout quotas.
RLIMITs cap individual files and process resources, but a command can still create
many bounded files. A production untrusted-code tier therefore still requires a
cgroup-v2/systemd or MicroVM runner with aggregate disk, memory, CPU, PID and IO
budgets. It also does not prove arbitrary command output free of secrets.

A passing artifact remains external evaluation evidence only. It does not establish
correctness, test sufficiency, security correctness, merge readiness or merge
authorization.
