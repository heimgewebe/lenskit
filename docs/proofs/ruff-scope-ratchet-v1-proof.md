# Ruff Scope Ratchet v1 Proof

## Status

- Task: `TASK-LINT-RUFF-SCOPE-001`
- Slice type: lint-scope ratchet, no broad cleanup
- Date: 2026-07-07

## Ausgangsbefund

`lint.yml` pinned Ruff at `ruff==0.15.13` and ran:

```bash
ruff check --select=F401,F811 --exclude='**/fixtures/**' .
```

`requirements-dev.txt` already pins the same Ruff version. The repository had no checked-in `ruff.toml`, so the CI scope lived only in the workflow command. A plain local `ruff check .` could therefore use a wider default rule set than CI.

## Entscheidung

This slice makes the current CI gate explicit in a checked-in `ruff.toml`:

- `target-version = "py312"`
- `exclude = ["**/fixtures/**"]`
- `lint.select = ["F401", "F811"]`

The GitHub Actions lint job and the local contributing instructions now both run:

```bash
ruff check .
```

That means local and CI lint use the same checked-in scope.

## Ratchet-Grenze

The first ratchet step preserves the existing gate exactly: unused imports (`F401`) and redefined-while-unused (`F811`) outside fixtures.

The known broader Ruff findings remain outside this PR. Any expansion to rules such as `E701`, `E402`, `E741`, `E731`, `F841`, `E711`, or `E712` needs a separate measured slice with its own proof and CI evidence.

## STOP / Nicht-Ziele

This proof does not establish:

- that default `ruff check` is clean under Ruff's wider default rule set,
- that `E701`, `E402`, `E741`, `E731`, `F841`, `E711`, or `E712` are fixed,
- that a formatting policy is introduced,
- that tests are sufficient,
- that runtime behavior is correct,
- that the repository is free of further lint debt.

## Validation

Observed validation on 2026-07-07:

```bash
python3 -m json.tool docs/tasks/index.json >/tmp/lenskit-task-index.json
python3 -m pip install -r requirements-dev.txt
python3 -m ruff check .
```

Result: `ruff check .` passed with the checked-in scope. Pip reported a pre-existing user-environment dependency warning during install, but installation completed and the Ruff gate passed. No pytest run is claimed for this slice.
