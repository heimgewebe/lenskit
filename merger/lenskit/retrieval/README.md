# Lenskit Retrieval System

## Optional Semantic Reranking

The local semantic re-ranking feature (F1b) is technically optional. To activate it, you must install the `sentence-transformers` dependency.

### Installation

**Run from the repository root.**
```bash
pip install -r merger/lenskit/requirements-semantic.txt
```

Or manually:
```bash
pip install "sentence-transformers>=2.0"
```

### Current F1b Limitations

- `provider` is currently limited to `local` only.
- `similarity_metric` is fixed to `cosine`.
- `sentence-transformers` is optional; without it, semantic reranking is unavailable and behavior follows the configured fallback policy.
- `dimensions` configurations are not yet actively validated.
