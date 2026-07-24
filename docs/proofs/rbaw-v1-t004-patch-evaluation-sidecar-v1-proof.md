# RBAW-V1-T004 External Patch Evaluation Sidecar v1 proof

## Scope

This slice prototypes the mutable evaluation layer outside RepoBrief core. The
producer is `tools/patch_evaluation_sidecar.py`; the existing schema and
read-only consumer remain unchanged.

## Boundary checks

- Source checkout worktree, staged-index, and untracked content is fingerprinted
  before evaluation and compared after cleanup; unrelated refs and Git
  configuration are outside this fingerprint.
- Evaluation runs in a detached disposable Git worktree at an exact commit.
- The patch is copied once into a private snapshot; its digest and applied bytes
  are therefore identical. Patch application fails before any configured command
  may run.
- Commands are argv arrays executed with `shell=False` and a confined relative
  working directory.
- Environment variables are allowlisted except for inherited `PATH`; Git
  global/system configuration and hooks are suppressed. Filesystem, credential,
  and network isolation remain unknown.
- Per-command timeouts and a global declared-command budget are enforced; timed-out
  process groups are terminated. The command budget begins immediately before the
  command loop. Validation, Git setup, cleanup, and source fingerprinting are not
  covered by it; large Python-side file hashing is not separately time-bounded.
- Logs are bounded, stored outside the source repository, and carry truncation
  metadata.
- The artifact is written atomically and declares all nine mandatory non-claims.
- Cleanup is fail-closed: an unremoved worktree or source drift forces artifact
  status `error`.

## Verification commands

```text
python -m pytest -q tests/test_patch_evaluation_sidecar.py merger/repoground/tests/test_patch_evaluation.py
# 30 passed in 2.19s

python -m pytest -q
# 4679 passed, 2 skipped in 116.93s

python -m ruff check tools/patch_evaluation_sidecar.py tests/test_patch_evaluation_sidecar.py
# All checks passed!

python -m py_compile tools/patch_evaluation_sidecar.py tests/test_patch_evaluation_sidecar.py
# exit 0

git diff --check
# exit 0
```

The durable full-suite receipt is bound to argv SHA-256
`c3f2578d3a465d10ae97391fe2a54f1c10832286381277ce1355ccfb0bbac529`
and receipt SHA-256
`7301747b260194f73ed0bfb6e8565f0e1ab2192d6d333dab68ded8727d8da5b6`.

## Does not establish

This proof and a passing prototype run do not establish correctness, test
sufficiency, security correctness, runtime behavior outside evaluated commands,
merge authorization, merge readiness, regression absence, repository
understanding, or truth of producer claims. Filesystem, credential, network, and
container sandboxing are not implemented by this prototype; configured commands must be
trusted.

Invalid requests and read-only provenance-preflight failures can terminate
without an artifact; they do not create a worktree or run declared commands.
Operational failures after mutable evaluation begins emit `status: error` when
the artifact destination remains writable.
