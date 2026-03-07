# Lenskit Retrieval System

## Optional Semantic Reranking

The local semantic re-ranking feature (F1b) is technically optional. To activate it, you must install the `sentence-transformers` dependency.

### Installation

```bash
pip install -r requirements-semantic.txt
```

Or manually:
```bash
pip install sentence-transformers>=2.0
```

### Current F1b Limitations

- `provider` is currently limited to `local` only.
- `similarity_metric` is fixed to `cosine`.
- `sentence-transformers` is optional, falling back to basic matching if not installed.
- `dimensions` configurations are not yet actively validated.
