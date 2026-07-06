# RepoBrief Agent Workbench Boundary

This document defines the RepoBrief / Agent Workbench boundary before an Agent Workbench implementation exists.

It is a boundary contract, not runtime evidence. It does not implement a Workbench, define the final patch-evaluation schema, prove test sufficiency, or authorize merges.

## Purpose

RepoBrief is the deterministic evidence core for repository snapshots, canonical brief content, citations, ranges, artifact discovery, health, freshness, and read-only access.

Patch creation, patch application, command execution, sandboxing, test loops, and mutable worktree handling belong outside RepoBrief in an external Agent Workbench.

The purpose of this split is to keep evidence access separate from mutation authority. RepoBrief should make it easier to inspect and cite repository evidence. It should not become the actor that changes the repository and then declares the result acceptable.

## Terms

- **RepoBrief Snapshot**: A generated repository brief at a specific generation time. It may be stale relative to the live working tree, GitHub, or a pull request.
- **Canonical Brief Source**: The canonical Markdown content inside a RepoBrief bundle. It is the content authority for the generated snapshot.
- **Brief Sidecar**: A navigation, diagnostic, evidence-index, or cache artifact associated with a snapshot. A sidecar helps locate or interpret evidence; it is not a replacement for canonical content.
- **Agent Workbench**: An external mutable evaluation environment that may create or use isolated worktrees, apply patches, run commands, and collect patch-evaluation evidence.
- **Patch Evaluation**: A bounded evaluation run over a patch, worktree, branch, or proposed change. It records what was attempted and observed.
- **Worktree**: A mutable checkout or workspace. Worktrees are outside the RepoBrief read-only evidence layer.
- **Patch Evaluation Artifact**: A future external artifact emitted by the Agent Workbench. RepoBrief may later read and link such artifacts, but must not produce or interpret them as approval.

## Boundary decision

RepoBrief must not grow an internal write axis for patch, shell, test, Git, or pull-request operations.

The accepted architecture is:

- RepoBrief remains a read-mostly evidence and snapshot layer.
- The Agent Workbench is a separate mutable evaluation layer.
- CI remains an independent verification surface.
- GitHub PRs remain the review and decision surface.
- Bureau remains the task registry and status surface.
- Codex or other review agents remain review organs, not authority sources.
- Humans remain the decision authority for merges, risky boundary changes, and strategic direction.

This intentionally rejects the tempting shortcut: turning RepoBrief into an agent that can read evidence, patch code, run tests, and present a green result as if that were release authority.

## RepoBrief responsibilities

RepoBrief may:

- explicitly create repository snapshots when a create operation is requested,
- read existing Brief Bundles,
- locate artifacts by role,
- resolve required reading for task profiles,
- report health, freshness, and availability,
- resolve ranges and citation surfaces,
- query existing indexes,
- preserve authority and canonicality metadata,
- expose read-only access helpers,
- later expose read-first MCP resources and a small set of explicit tools,
- later read or link external Workbench artifacts when they are explicitly present and identified as external evidence.

When RepoBrief reads external Workbench artifacts, it may report their presence, provenance fields, availability, and declared status. It must not convert those observations into a release verdict.

## Explicit non-responsibilities

RepoBrief must not:

- trigger implicit refresh during read operations,
- mutate Git state as a side effect of reading,
- create branches or pull requests,
- write, apply, or repair patches,
- manage mutable worktrees,
- run shells, tests, linters, or sandboxes,
- read secrets,
- execute or orchestrate deployment actions,
- generate review verdicts,
- treat tests as release approval,
- claim runtime correctness,
- claim test sufficiency,
- claim review completeness,
- claim merge readiness,
- claim security correctness,
- introduce LLM inference, embeddings, or semantic reranking into the deterministic core.

## Agent Workbench responsibilities

An external Agent Workbench may:

- receive an explicit task, patch, branch, commit, or pull-request reference,
- consume RepoBrief snapshots and citations as read-only context,
- create isolated mutable worktrees or sandboxes,
- apply proposed patches,
- run configured tests, linters, static checks, or smoke commands,
- capture command lines, exit codes, logs, changed files, and environment metadata,
- emit patch-evaluation artifacts,
- link observations back to RepoBrief citations or source ranges,
- stop with a precise report when the workspace, command policy, secrets policy, or provenance is insufficient.

The Agent Workbench should be useful precisely because it is outside the RepoBrief core. It can be allowed to mutate an isolated workspace without weakening RepoBrief's evidence boundary.

## Artifact flow

A typical future flow is:

1. RepoBrief creates or reads a snapshot of a repository state.
2. An agent or human selects cited evidence from the snapshot.
3. The Agent Workbench receives an explicit patch-evaluation request.
4. The Workbench creates an isolated mutable workspace.
5. The Workbench applies a patch or checks out the requested branch.
6. The Workbench runs configured evaluation commands.
7. The Workbench emits patch-evaluation artifacts with provenance, commands, results, logs, and non-claims.
8. RepoBrief may later read or link those artifacts as external evidence.

There is no reverse authority upgrade. A Workbench artifact must not make an old RepoBrief snapshot fresh, canonical, complete, or correct. It can only add external observations about a separate evaluation run.

## Patch Evaluation Artifact preview

The detailed Patch Evaluation Artifact contract is deferred to a later task. This document only sketches likely fields so the boundary is understandable.

A future artifact may include:

- artifact id and schema version,
- producer identity and version,
- input repository, branch, commit, pull request, or patch id,
- referenced RepoBrief snapshot or bundle manifest,
- cited ranges or source references used as context,
- isolated workspace identifier,
- applied patch metadata,
- command policy,
- command lines and exit codes,
- captured logs or output references,
- changed-file summary,
- environment and tool versions,
- timeout and truncation status,
- declared non-claims.

This preview is not a schema. RBAW-V1-T002 owns the actual contract.

## MCP boundary

RepoBrief MCP remains a read-first boundary.

RepoBrief MCP resources and read-only tools must not trigger Workbench actions. They must not run shells, apply patches, create PRs, inspect secrets, or silently refresh snapshots.

A future `snapshot_create` tool is an explicit RepoBrief write exception for Brief Bundle generation only. It is not a permission to add patch, shell, test, or Workbench authority to RepoBrief MCP.

If Workbench control is ever exposed through MCP, it should be a separate Workbench surface with its own authority model, not a hidden extension of RepoBrief resources.

## Security and secret boundary

RepoBrief should not require secrets to read existing bundles or expose snapshot evidence.

The Agent Workbench may need access to credentials, private dependencies, or privileged environments in some deployments. Those capabilities must be explicit, scoped, logged, redacted where necessary, and kept outside RepoBrief's deterministic read path.

Evaluation logs and artifacts must preserve enough provenance to be auditable without leaking secrets. Missing redaction or unknown secret exposure should degrade or fail the evaluation artifact, not be smoothed into success.

## Non-claims

A successful RepoBrief read, Workbench run, CI job, review comment, or PR status does not by itself establish:

- `truth`
- `correctness`
- `completeness`
- `runtime_correctness`
- `test_sufficiency`
- `review_completeness`
- `merge_readiness`
- `security_correctness`
- `regression_absence`
- `repo_understood`
- `claims_true`
- `forensic_ready`

Evidence can support a decision. It is not the decision.

## Common false assumptions

### “If RepoBrief can run tests, the patch is good.”

False. RepoBrief must not run tests. Even when an external Workbench or CI runs tests, those results are evidence, not approval.

### “External Workbench means weaker integration.”

False. Externality is the safety property. The Workbench can integrate through explicit artifacts and citations without contaminating the read-only evidence core.

### “Source Citation Projection already makes a Workbench.”

False. Source Citation Projection improves evidence projection across artifact and source coordinates. It does not apply patches, create worktrees, run tests, or mutate Git.

### “MCP can later just get shell access.”

False. RepoBrief MCP is read-first. Shell access would cross into Workbench authority and must not be smuggled through a read-only resource interface.

## Risks and benefits

External Workbench benefits:

- preserves the evidence/mutation boundary,
- allows structured patch evaluation,
- reduces the risk that generated evidence becomes a self-authorizing verdict,
- improves auditability through explicit artifacts,
- lets CI and GitHub remain independent control surfaces.

External Workbench risks:

- more interfaces,
- more artifact types,
- more provenance fields to validate,
- slower initial implementation,
- possible confusion if Workbench artifacts are displayed beside RepoBrief artifacts without clear authority labels.

Internal RepoBrief write-axis benefits:

- apparently simpler local agent loop,
- fewer moving pieces at first.

Internal RepoBrief write-axis risks:

- breaks the authority boundary,
- forces RepoBrief to own shell, secrets, rollback, Git, worktree, and runtime semantics,
- makes tests easier to misread as merge approval,
- turns a citation system into a mutable agent controller.

The risk asymmetry is the decision: the external Workbench path is slower, but it preserves the system's spine. The internal write-axis path is faster in the same way a trapdoor is an efficient staircase.

## Future work

- RBAW-V1-T002: define the Patch Evaluation Artifact contract.
- RBAW-V1-T003: define read-only RepoBrief consumption of external patch-evaluation artifacts.
- RBAW-V1-T004: prototype an external Agent Workbench harness.
- RBAW-V1-T005: triage Lenskit agent optimization axes without adding mutation authority to RepoBrief.
