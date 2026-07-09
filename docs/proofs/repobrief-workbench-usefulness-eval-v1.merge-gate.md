# Merge Gate — RepoBrief Workbench Usefulness Diagnostic v1

Do not merge this PR until the actual PR diff and current head have been reviewed.

## Required gates

- Fetch current PR metadata and head SHA.
- Fetch current PR diff.
- Review the diff against the intended docs/diagnostics-only scope.
- Confirm redundant marker files are gone.
- Validate the JSON report.
- Run structural whitespace check.
- Check CI if GitHub Actions runs for this PR.
- Reconcile whether task registry status should be updated in this PR or a follow-up.

## Intended commands

```bash
python3 -m json.tool docs/diagnostics/repobrief-workbench-usefulness-eval-20260709T030000Z.json >/dev/null
git diff --check
```

## Non-claims

This gate note is not a review approval and does not establish merge readiness.
