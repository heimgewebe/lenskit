# Lenskit Code-Scanning Central Barrier v2 Proof

## Trigger

PR #952 removed the original path, exception-disclosure, and workflow-permission surface and passed all pull-request checks. After squash merge, the complete `main` Python analysis for commit `2f75253bc77c4329d1aa0f2b71466197bae350f6` nevertheless reported six path-injection results.

The six results were all concentrated in the older central allowlist implementation:

- request-controlled absolute path canonicalization inside `SecurityConfig.validate_path`;
- repeated `exists` / `is_dir` operations after that validator;
- one redundant Hub existence check after `validate_source_dir`.

This exposed a process gap: GitHub pull-request analysis did not provide the same effective full-result surface as the subsequent `main` analysis.

## Runtime correction

The central validator no longer canonicalizes a request-controlled full path directly.

1. It performs lexical absolute-path and allowlist-root matching without filesystem access.
2. It derives a relative path beneath the narrowest matching registered root.
3. Exact root requests return the already canonical registered `Path` object.
4. Descendants are delegated to `resolve_secure_path`, which validates individual path segments and performs a post-canonicalization root check.
5. A canonical failure under the narrowest matching root is terminal; the validator does not fall back to a broader overlapping root.
6. Existing-directory requirements are represented by `validate_directory` and are used by Hub and source-directory callers.
7. `_find_repos` no longer repeats an unreachable existence check after directory validation.

## Least-authority behavior

When a broad root and a nested Hub are both registered, a symlink escape from the Hub is rejected against the Hub capability. The validator does not reinterpret the same request under the broader root. Direct use of the broader root remains possible only through the separately authorized broader capability.

## Raw SARIF merge gate

The CodeQL workflow now saves the raw analyzer SARIF and runs `scripts/ci/assert_codeql_sarif_clean.py` after analysis.

The gate:

- fails closed if the SARIF directory or SARIF files are missing;
- fails closed on malformed SARIF;
- prints rule, path, and line for every result;
- fails the workflow when any raw result is present;
- succeeds only when all raw SARIF result arrays are empty.

The gate was tested against the actual six-result `main` SARIF from PR #952 and exited with status 1 while listing all six findings. This prevents the previous PR-green/main-red discrepancy from passing unnoticed.

## Local validation

- focused and adjacent suite: 329 passed;
- central security and raw-SARIF tests: included;
- repository Ruff ratchet: passed;
- Python byte compilation: passed;
- planning-registration ratchet: zero findings and zero control errors;
- `git diff --check`: passed.

## Required live proof

Local validation cannot prove CodeQL closure. The follow-up PR must satisfy both:

1. ordinary GitHub CodeQL analysis succeeds;
2. `Require clean raw CodeQL SARIF` succeeds on the unfiltered analyzer output.

After merge, the new `main` analysis must also contain zero results before historical alert identities are triaged.

## Non-claims

This proof does not establish absence of unrelated vulnerabilities, elimination of every filesystem race, correctness on every operating system, safety of arbitrary trusted local CLI authority, test sufficiency, deployment state, or merge readiness without the live gates above.
