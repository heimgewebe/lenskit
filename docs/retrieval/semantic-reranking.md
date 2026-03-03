# Semantic Re-Ranking Pipeline

This document outlines the architectural concept for implementing semantic re-ranking in Lenskit, satisfying Phase F of the Retrieval Project Roadmap.

## Context

Following the "Scope Management Principle" of Lenskit, we define complex algorithmic behavior through documentation and explicit schema contracts *before* modifying core logic. The foundational FTS (Full-Text Search) layer is fast, explainable, and handles filtering effectively. Semantic search is introduced strictly as a **re-ranker** applied to the top candidates retrieved by the lexical engine.

## The Pipeline

The retrieval pipeline consists of two stages:

1. **Candidate Generation (Top-K Lexical):**
   The existing `fts5` index executes the query with any applied metadata filters. Instead of retrieving just `K` results, it over-fetches a candidate pool (e.g., K = 50).
2. **Semantic Re-Ranking (Top-N Semantic):**
   The semantic engine processes the queries and candidate pool. Vectors for candidate chunks are retrieved (or calculated dynamically) and compared against the query vector. The top N items (e.g., N = 10) are returned.

## `embedding_policy.v1` Contract

The parameters for this re-ranking step are defined by the `embedding-policy.v1.schema.json` contract. This defines:
- **`model_name`**: Identifies the text embedding model used.
- **`dimensions`**: Specifies the expected vector size.
- **`provider`**: Delineates `api` vs `local` model execution.
- **`similarity_metric`**: Distance metric to compute similarity (e.g., `cosine`).
- **`fallback_behavior`**: Crucially, if the semantic service fails (e.g., API timeout), the policy determines whether to `fail` the request or `ignore` the error and yield the raw BM25 candidates.

## Evaluation Strategy

We employ a strict **improvement delta vs non-semantic** strategy.

Semantic re-ranking must prove its worth against the established baseline:
- `lenskit eval` will generate metrics (like `recall@10`) using the lexical-only approach.
- The same gold queries (`queries.v1.json`) are evaluated using the semantic re-ranker.
- The measurable difference between the two strategies constitutes the "improvement delta".

## Stop Criterion

The Phase F1 goal is considered successfully met when the semantic pipeline demonstrates a **measurable improvement** in standard metrics (e.g. `recall@k`) **without introducing new failure classes**. This ensures stability while augmenting the "Retrieval OS" with deeper intent matching capabilities.
