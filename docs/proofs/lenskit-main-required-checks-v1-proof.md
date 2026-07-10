# Lenskit main required checks v1 proof

Status: implemented and structurally verified on 2026-07-10. Positive implementation-PR evidence is recorded before merge.

## Scope

A separate repository ruleset named `main-required-checks` protects only `refs/heads/main`.
It does not replace the existing `zweigschutz` ruleset, which continues to protect deletion and non-fast-forward updates.

The new ruleset has GitHub ruleset id `18784275`, has no bypass actors, and requires these checks from their observed GitHub Apps:

| Required context | Integration id | Evidence guarded |
|---|---:|---|
| `Lenskit CodeQL policy (python)` | `15368` | The repository CodeQL workflow, including suppression-inventory validation and the post-analysis raw-SARIF clean gate |
| `CodeQL` | `57789` | GitHub Advanced Security's pull-request CodeQL result |
| `pytest-full` | `15368` | The full Python test suite excluding explicitly non-blocking markers |
| `ruff` | `15368` | The pinned repository-wide Ruff ratchet |
| `webui-js-tests` | `15368` | The Web UI JavaScript test suite |

`strict_required_status_checks_policy` is enabled. A pull request whose branch is behind `main` must therefore be brought up to date and revalidated before merge. This trades extra CI reruns for evidence against the current base.

The custom workflow job has the unique context `Lenskit CodeQL policy (python)` so GitHub's separate default `Analyze (python)` check cannot ambiguously satisfy this policy.

The machine-readable desired state is `config/github-main-required-checks.v1.json`. The read-only, network-free validator is `scripts/ci/check_github_main_ruleset.py`.

Operator check:

```bash
gh api repos/heimgewebe/lenskit/rulesets/18784275 \
  | python3 scripts/ci/check_github_main_ruleset.py
```

A successful validator result establishes only structural agreement between the observed API response and the checked-in policy. It does not establish that GitHub will enforce the rule at merge time.

## Staged activation proof

The ruleset was first created with `enforcement=disabled`.
The validator failed with exactly one finding:

```text
enforcement mismatch: expected 'active', found 'disabled'
```

After the payload was checked, the same ruleset was updated to `enforcement=active`, read back from the GitHub API, and validated with `status=pass` and no findings.

## Negative enforcement proof

Disposable pull request [#955](https://github.com/heimgewebe/lenskit/pull/955) used head commit `9a777407c43a002a7a528cf98bdf69ef2ec322d7` and intentionally introduced one Ruff `F401` violation.

Observed on 2026-07-10:

- GitHub computed the branch as `mergeable=MERGEABLE`; there was no content conflict.
- Required check `ruff` completed with `FAILURE`.
- GitHub reported `mergeStateStatus=BLOCKED`.
- The pull request was closed without merge.
- The disposable remote branch and worktree were removed.

This demonstrates that a content-mergeable pull request is blocked when a configured required check fails. It does not prove that every possible bypass, permission path, GitHub outage, or future rule edit is covered.

## Positive implementation proof

To be completed on the implementation pull request after the checked-in policy, validator, tests, and this proof have passed all five required checks on the current `main` base.

## Rollback

If an incorrect context or GitHub incident deadlocks merges:

1. set ruleset `18784275` to `enforcement=disabled`;
2. diagnose the mismatched context or integration id;
3. update the checked-in desired state and tests through a reviewed pull request;
4. reactivate only after API read-back validation and a fresh negative/positive proof.

Deleting this separate ruleset is a last-resort rollback. It does not modify the existing deletion/non-fast-forward `zweigschutz` ruleset.

## Non-claims

This proof does not establish:

- test sufficiency;
- absence of security findings;
- CodeQL or Ruff correctness;
- runtime correctness;
- review completeness;
- permanent GitHub availability;
- merge readiness of any unrelated pull request.
