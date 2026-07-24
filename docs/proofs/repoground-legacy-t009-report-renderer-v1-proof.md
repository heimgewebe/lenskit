# REPOGROUND-LEGACY-RECONCILIATION-V1-T009 proof

## Scope

This proof binds the bounded T009 slice: decompose `iter_report_blocks` along
stable report sections while preserving canonical bytes, generator order,
lazy content reads, redaction, anchors, and size-bound behaviour.

It does **not** close umbrella task T004 and does not claim that every remaining
function in `merge.py` is small.

## Revision binding

- canonical task activation: Bureau PR #976, merge
  `9c59f667607d1b96b50dcf598896e04ff1d3c5b5`
- RepoGround base: `a87fcfbb579aad23016273ee59438025b536cd97`
- implementation head before this proof commit:
  `a1f57ff14e56289b47c8751f9fa185463d8e6dfd`
- implementation tree: `452a56409a680b70f665e7a488bdb7d1022ea630`

## Structural result

- `iter_report_blocks`: 1,042 lines before; 50 lines after
- its C901 complexity was 148 before and is below the configured C901 threshold
  after the split (it no longer appears in the C901 finding set)
- aggregate C901 findings: 198 -> 197
- aggregate excess mass: 2,533 -> 2395
- global maximum: 148 -> 138; the remaining maximum belongs
  to a different legacy function
- new C901 findings: 0

The renderer is divided into preparation, header/meta, plan, optional analysis,
structure, index, manifest, and streamed content responsibilities. A private
`_ReportRenderState` carries explicit inputs between those sections.

## Byte and streaming parity

Three deterministic golden scenarios were captured before the refactor with a
frozen UTC clock:

| Scenario | Blocks | Joined SHA-256 |
| --- | ---: | --- |
| full extras | 15 | `dbaa56af7075785ef27bd603893ca563a915eb65f1ae8de54ef994d16dc8b68a` |
| plan filtered | 2 | `38b98b0fa33960f5dcbfd85d08cd2e595465c13fdf9a8a887bf034c2e6bd066f` |
| machine lean + redaction | 9 | `9ed1251c56eaf55f8490a1b1d0055d52c7a06e298c956a2955689f3b7b29f8a3` |

The tests compare both the complete UTF-8 payload and every individual yielded
block by byte length and SHA-256. They also prove that the first header and plan
blocks are yielded before any file content is read, and that the fixture secret
is absent from the redacted report.

## Performance

The canonical fixed-fixture benchmark was measured before on clean base and
after on the clean implementation branch. The dirty-worktree measurement was
explicitly rejected because runtime provenance captured the large uncommitted
diff and inflated archive memory.

| Case | Median time change | Peak traced memory change |
| --- | ---: | ---: |
| archive | -0.41% | -0.25% |
| dual | -1.06% | +2.79% |

A renderer-only block profile additionally observed 89 identical block shapes
and a peak reduction from roughly 220 KiB to 204 KiB. The full archive and dual
changes are therefore non-material for this slice.

## Validation receipts

- focused report and merge regression suite: 111 passed; lifecycle receipt
  `b88bb7d4de7a01efe083122b18fcac96c32f7b7337909ce717286a5aa7fd5f2d`
- first complete repository suite: 4,753 passed, 2 skipped; lifecycle receipt
  `d3c865086625a5ea14db39a74afac96a50ef0a1c5c0c115b15bb2f6e57c56293`
- clean post-commit performance run: lifecycle receipt
  `ff912d74d3385dd9795e738b04b3cb2bbe13c16c4ba27ba33a7a69d9f2d7c206`
- repeated alternating benchmark: lifecycle receipt
  `d5112e800f3716fdd89e7bde2586490bd4c58092978f616105f0350972588d86`
- Ruff: pass
- parity guard: pass
- graph maintainability gate: pass
- `git diff --check`: pass

A final complete repository suite is run after this proof is committed and is
bound in the pull-request delivery evidence.

## Does not establish

- completion of umbrella task T004
- correctness of unrelated legacy functions below the C901 threshold
- absence of all future performance regressions
- permission to change foreign worktrees, branches, leases, or processes
