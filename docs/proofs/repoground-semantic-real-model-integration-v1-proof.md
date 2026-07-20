# RepoGround Semantic Real-Model Integration v1 — Proof

Status: implemented and locally verified from RepoGround main commit `701c28983e873892155d4b5148274392aea7a951` on branch `test/semantic-real-model-integration-v1`.

## Problem

RepoGround's semantic-dimension tests previously used controlled mock models. Those tests prove the intended normalization and fallback contracts, but they do not establish the concrete output shapes returned by the locked `sentence-transformers` library or the compatibility of a saved and reloaded local model with RepoGround's validation and cosine-scoring path.

The optional semantic dependency installation proof deliberately downloaded no model. A real pre-trained model would add separate artifact identity, licensing, availability, network and semantic-quality questions that are not required to test the runtime shape contract.

## Implemented integration lane

`scripts/ci/run_semantic_real_model_integration.py` now builds a small real `SentenceTransformer` pipeline from the installed library using its `BoW` and `Normalize` modules. The fixture:

- has an explicit eight-token vocabulary and therefore eight output dimensions;
- contains no downloaded or pre-trained model weights;
- is saved twice and requires the same canonical tree SHA-256 for both outputs;
- is bound to tree SHA-256 `913b82d98b28add74e605bde8a807826ce1b995b783ddac158e7f0fdf5bcfc75`;
- is reloaded from a local path with `local_files_only=True`;
- emits actual NumPy query, single-document and document-batch embeddings;
- passes those embeddings through RepoGround's model cache, dimension validation and cosine scorer.

`scripts/ci/run_semantic_real_model_integration.sh` executes the runner in the same digest-pinned CPython 3.12 image as the semantic lock compiler. The model phase uses:

- Docker `--network none` plus an in-container requirement that `/sys/class/net` exposes only `lo`;
- a read-only root filesystem;
- a fixed unprivileged numeric identity, UID/GID `65532:65532`, instead of the host user;
- a temporary runtime copy produced only from regular files in `git archive HEAD`, normalized to file mode `0444` and directory mode `0555` before its read-only mount;
- a read-only dependency mount whose complete host path is rejected when any component is a symlink;
- host orchestration isolated with Python 3.10 `-I -S`, while the pinned CPython 3.12 container uses `-P -S`, `PYTHONSAFEPATH=1`, and explicit `PYTHONPATH=/semantic-target:/work` rather than runtime `sys.path` mutation;
- all Linux capabilities dropped;
- `no-new-privileges`;
- Hugging Face and Transformers offline flags;
- an additional Python socket guard.

The existing `semantic-lock` workflow now installs the 58-package SHA-256-locked dependency closure into a unique `mktemp` directory below `RUNNER_TEMP`. The EXIT trap is installed before the directory is created, so cancellation and early failure do not leave a fixed shared path. After installation, read/execute access is added without write access for the fixed container identity, the network-disabled integration wrapper runs, and the target is removed. The normal RepoGround Python suite remains independent of Torch and SentenceTransformers.

The workflow path filter also now watches the real renamed platform contract, `docs/release/repoground-semantic-platforms.v1.json`, instead of the obsolete pre-cutover filename.

The container image is not independently hard-coded in the integration wrapper. It is read from the digest-pinned `compiler.image` field in that platform contract. Updating the tag or digest therefore requires one explicit contract change, regenerated semantic locks, a new deterministic model-tree hash check, and renewed local and GitHub integration evidence. The `sentence-transformers==5.6.0` and `torch==2.13.0+cpu` roots are likewise compatibility pins for reproducibility; they are not an instruction to select versions dynamically at runtime.

## Real execution evidence

Hash-locked dependency installation:

```text
task_id: fba537b7c3af4cc4a49686a8
terminalization_sha256: 1a1de2c245afd7f37e85a88f0e3f98008291d6e7a9b7e129bd15f9ca05930a8e
lifecycle_receipt_sha256: 38099cef463b746f2c82ff3efea4d5200aba892c04299fad71b08fbb69c18041
result: success
```

Hardened fixed-identity, network-disabled integration wrapper with commit-staged runtime and cleanup verification:

```text
task_id: 7f0912b4312449798fa2a90f
terminalization_sha256: f8b554c0d1cab933171eaa4f55ff2b605aa751767dcfeb907212a0a33acb6e4d
lifecycle_receipt_sha256: e80a5d7c257f60f605f80c2dc8f5d340cf7698d9979296c09e5f6ceee1b07647
result: success
runtime_copy_cleanup: pass, no repoground-semantic-runtime.* path remained
```

Observed runtime and outputs:

```text
CPython: 3.12.3
sentence-transformers: 5.6.0
torch: 2.13.0+cpu
numpy: 2.5.1
CUDA available: false
observed network interfaces: [lo]
query output: numpy.ndarray, shape [8]
single-document output: numpy.ndarray, shape [1, 8]
document-batch output: numpy.ndarray, shape [2, 8]
model tree SHA-256 A: 913b82d98b28add74e605bde8a807826ce1b995b783ddac158e7f0fdf5bcfc75
model tree SHA-256 B: 913b82d98b28add74e605bde8a807826ce1b995b783ddac158e7f0fdf5bcfc75
RepoGround dimension validation: pass
actual query dimensions: 8
actual document dimensions: 8
cosine scores: [0.866025447845459, 0.0]
```

Dependency-free contract tests:

```text
python3 -m pytest \
  merger/repoground/tests/test_semantic_real_model.py \
  merger/repoground/tests/test_semantic_extension_lock.py -q

13 passed in 0.13s
```

Complete RepoGround Python suite:

```text
python3 -m pytest merger/repoground/tests -q

4371 passed, 2 skipped in 120.65s
```

Durable complete-suite task on the hardened final code, workflow and wrapper:

```text
task_id: 6c1ba8d1eedc4d17b50bf0a3
terminalization_sha256: 407d63374c6534cee565756f9d9bdd4e343843c764c4cdea97c6a00f1fb497c2
lifecycle_receipt_sha256: f0f69c8f449cca0b26f0dfca17349ea88d31aa788dfb1306aa65edcdc553e435
persisted_output_sha256: 9d6fef780e912ca623256bc0077cf33976904b5567d1422a7db5c4cf6171c636
```

Static and contract checks:

```text
changed-file Ruff: pass
Python syntax compilation: pass
workflow YAML parse: pass
wrapper bash syntax: pass
release contract: pass, findings=[]
maintainability ratchet: pass, new_count=0, resolved_count=2, findings=[]
git diff --check: pass
```

A repository-wide unconfigured `ruff check .` still reports 128 existing baseline findings in unrelated legacy and fixture files. No finding points to this slice; the changed-file Ruff check and the repository maintainability ratchet are the applicable fail-closed gates.

## Failure semantics

The integration fails closed when:

- the observed container network exposes any interface other than loopback;
- the dependency target is not normalized and absolute, contains a symlink in any path component, or is not a directory;
- the committed runtime archive contains a symlink, hard link or any other non-regular entry;
- the generated model tree contains a symlink or another non-regular entry;
- the explicit dependency and repository import roots are absent;
- installed SentenceTransformers or Torch versions differ from the locked roots;
- CUDA unexpectedly becomes the selected execution surface;
- either generated model tree differs from the other or from the committed hash;
- local model loading attempts a Python network operation;
- direct library output types or shapes change;
- RepoGround observes a dimension or score-count mismatch;
- scores are non-finite or no longer preserve the controlled fixture ordering.

## Boundaries

This proof establishes compatibility with a real, saved and reloaded SentenceTransformer pipeline built from the exact locked library versions. It does not establish compatibility with arbitrary pre-trained models, model availability, external model licensing, semantic quality, ranking quality on natural queries, GPU support, cross-platform installability, vulnerability absence or readiness to enable semantic reranking by default.
