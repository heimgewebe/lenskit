import sqlite3
from pathlib import Path
import json
from typing import Dict, Any, Optional

from .router import route_query

WHY_ZERO_TOKENS = "tokens too restrictive"
WHY_ZERO_FILTERS = "filters too restrictive"
WHY_ZERO_NONE = "no results"

_MODEL_CACHE = {}

def _get_semantic_model(model_name: str):
    if model_name not in _MODEL_CACHE:
        from sentence_transformers import SentenceTransformer
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _MODEL_CACHE[model_name]

def execute_query(
    index_path: Path,
    query_text: str,
    k: int = 10,
    filters: Optional[Dict[str, Optional[str]]] = None,
    embedding_policy: Optional[Dict[str, Any]] = None,
    explain: bool = False,
    overmatch_guard: bool = False,
    graph_index_path: Optional[Path] = None,
    graph_weights: Optional[Dict[str, float]] = None,
    test_penalty: float = 0.75
) -> Dict[str, Any]:
    """
    Executes a query against the SQLite index.
    Returns a dictionary containing query metadata and results.
    """
    if not filters:
        filters = {}

    conn = None
    try:
        conn = sqlite3.connect(str(index_path))
        conn.row_factory = sqlite3.Row

        where_clauses = []
        params = []

        engine_type = "metadata"
        query_mode = "metadata"
        fts_query_str = None
        router_output = None
        routed_query_raw = query_text

        if query_text:
            engine_type = "fts5"
            query_mode = "fts"

            # Route query (synonym expansion, stop-verbs, intent)
            router_output = route_query(query_text, overmatch_guard=overmatch_guard)

            # Use routed fts_query if available, fallback to original query
            routed_query = router_output["fts_query"] if router_output["fts_query"] else query_text
            routed_query_raw = routed_query

            # FTS Query: Escape double quotes
            cleaned_q = routed_query.replace('"', '""')

            scoring_expr = "bm25(chunks_fts)"

            base_sql = f"""
                SELECT
                    c.chunk_id, c.repo_id, c.path, c.start_line, c.end_line, c.start_byte, c.end_byte, c.content_sha256,
                    c.layer, c.artifact_type, c.content_range_ref, chunks_fts.content,
                    {scoring_expr} as score
                FROM chunks_fts
                JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
                WHERE chunks_fts MATCH ?
            """

            params.append(cleaned_q)
            fts_query_str = cleaned_q
            where_clauses.append("1=1") # Placeholder for appending ANDs easily

            # BM25: lower is better
            order_clause = "ORDER BY score ASC, c.repo_id ASC, c.path ASC, c.start_line ASC"
        else:
            # Metadata only query
            base_sql = """
                SELECT
                    c.chunk_id, c.repo_id, c.path, c.start_line, c.end_line, c.start_byte, c.end_byte, c.content_sha256,
                    c.layer, c.artifact_type, c.content_range_ref, '' as content,
                    0 as score
                FROM chunks c
            """
            where_clauses.append("1=1")
            order_clause = "ORDER BY c.repo_id, c.path, c.start_line"

        # Add metadata filters
        if filters.get("repo"):
            where_clauses.append("c.repo_id = ?")
            params.append(filters["repo"])

        if filters.get("path"):
            where_clauses.append("c.path_norm LIKE ?")
            params.append(f"%{filters['path'].lower()}%")

        if filters.get("ext"):
            where_clauses.append("c.path_norm LIKE ?")
            ext = filters["ext"]
            if not ext.startswith("."):
                ext = f".{ext}"
            params.append(f"%{ext.lower()}")

        if filters.get("layer"):
            where_clauses.append("c.layer = ?")
            params.append(filters["layer"])

        if filters.get("artifact_type"):
            where_clauses.append("c.artifact_type = ?")
            params.append(filters["artifact_type"])

        # Combine clauses
        if query_text:
            # Skip the first placeholder "1=1" if we are appending to existing WHERE
            extras = [c for c in where_clauses if c != "1=1"]
            if extras:
                base_sql += " AND " + " AND ".join(extras)
        else:
            # For metadata query, we have `FROM chunks c`. We need to start WHERE clause.
            base_sql += " WHERE " + " AND ".join(where_clauses)

        # If semantic re-ranking or graph reranking is requested, fetch a larger candidate pool
        is_reranking = embedding_policy is not None or graph_index_path is not None
        fetch_k = max(k, 50) if is_reranking else k

        base_sql += f" {order_clause} LIMIT ?"
        params.append(fetch_k)

        cursor = conn.execute(base_sql, params)
        rows = cursor.fetchall()

        results = []
        semantic_enabled = embedding_policy is not None
        fallback = embedding_policy.get("fallback_behavior", "ignore") if semantic_enabled else "ignore"

        base_diagnostics = {}
        semantic_model = None
        if semantic_enabled:
            # Note on F1b implementation limits:
            # Currently only `provider=local` and `similarity_metric=cosine` are actively implemented.
            # Other parameters like `dimensions` are structurally present but not actively validated here yet.
            engine_type += "+semantic_requested"
            provider = embedding_policy.get("provider", "local")
            metric = embedding_policy.get("similarity_metric", "cosine")

            if provider != "local":
                if fallback == "fail":
                    raise RuntimeError(f"Semantic re-ranking provider '{provider}' is not yet implemented (fallback_behavior=fail).")
                else:
                    base_diagnostics["semantic"] = {
                        "enabled": False,
                        "error": f"Provider '{provider}' not implemented",
                        "fallback_behavior": fallback,
                        "candidate_k": fetch_k,
                        "provider": provider,
                        "model_name": embedding_policy.get("model_name")
                    }
            elif metric != "cosine":
                if fallback == "fail":
                    raise RuntimeError(f"Semantic re-ranking metric '{metric}' is not supported (fallback_behavior=fail).")
                else:
                    base_diagnostics["semantic"] = {
                        "enabled": False,
                        "error": f"Metric '{metric}' not supported",
                        "fallback_behavior": fallback,
                        "candidate_k": fetch_k,
                        "provider": provider,
                        "model_name": embedding_policy.get("model_name")
                    }
            else:
                try:
                    model_name = embedding_policy.get("model_name", "all-MiniLM-L6-v2")
                    semantic_model = _get_semantic_model(model_name)
                    base_diagnostics["semantic"] = {
                        "enabled": True,
                        "fallback_behavior": fallback,
                        "candidate_k": fetch_k,
                        "provider": provider,
                        "model_name": model_name
                    }
                except ImportError as e:
                    if fallback == "fail":
                        raise RuntimeError(f"Semantic re-ranking provider '{provider}' requires sentence-transformers (fallback_behavior=fail).") from e
                    else:
                        base_diagnostics["semantic"] = {
                            "enabled": False,
                            "error": "sentence-transformers not installed",
                            "fallback_behavior": fallback
                        }
                except Exception as e:
                    if fallback == "fail":
                        raise RuntimeError(f"Semantic re-ranking failed to load model (fallback_behavior=fail): {e}") from e
                    else:
                        base_diagnostics["semantic"] = {
                            "enabled": False,
                            "error": str(e),
                            "fallback_behavior": fallback
                        }

        graph_index = None
        if graph_index_path:
            if not graph_index_path.exists():
                raise RuntimeError(f"Explicitly provided graph index file does not exist: {graph_index_path}")
            try:
                with graph_index_path.open() as f:
                    graph_index = json.load(f)
            except Exception as e:
                raise RuntimeError(f"Invalid graph index JSON at {graph_index_path}: {e}") from e

        if not graph_weights:
            graph_weights = {"w_bm25": 0.65, "w_graph": 0.20, "w_entry": 0.15}

        ranker_meta = None
        if graph_index:
            ranker_meta = {
                "w_bm25": graph_weights.get("w_bm25", 0.65),
                "w_graph": graph_weights.get("w_graph", 0.20),
                "w_entry": graph_weights.get("w_entry", 0.15),
                "test_penalty_default": test_penalty
            }

        bm25_scores = [-r["score"] for r in rows if r["score"] is not None and query_text]
        max_bm25_score = max(bm25_scores) if bm25_scores else 1.0
        if max_bm25_score == 0: max_bm25_score = 1.0

        # candidate_texts is built eagerly to keep row/result alignment simple.
        # fetch_k is small, so overhead is negligible.
        candidate_texts = []
        for idx, r in enumerate(rows):
            candidate_texts.append(r["content"] or "")
            matched_terms = [query_text] if query_text else [query_mode]
            filter_pass = [key for key, v in filters.items() if v]

            rank_features = {}
            if query_text:
                rank_features["bm25"] = r["score"]
                bm25_raw = -r["score"] if r["score"] is not None else 0
                rank_features["bm25_norm"] = bm25_raw / max_bm25_score
            else:
                rank_features["metadata"] = 0
                rank_features["bm25_norm"] = 0.0

            final_score = rank_features["bm25_norm"]
            why_list = []

            if graph_index:
                path_str = r["path"]
                node_id = f"file:{path_str}"
                dist = graph_index.get("distances", {}).get(node_id, -1)

                graph_proximity = 0.0
                entrypoint_boost = 0.0
                if dist == 0:
                    graph_proximity = 1.0
                    entrypoint_boost = 1.0
                    why_list.append("entrypoint_boost")
                elif dist > 0:
                    graph_proximity = 1.0 / (dist + 1.0)

                is_test = r["layer"] == "test" or "test" in path_str.lower()
                current_penalty = test_penalty if is_test else 1.0

                rank_features["graph_proximity"] = graph_proximity
                rank_features["entrypoint_boost"] = entrypoint_boost

                if graph_proximity > 0:
                    why_list.append("near_entry")
                if not is_test:
                    why_list.append("not_test")

                w_b = graph_weights.get("w_bm25", 0.65)
                w_g = graph_weights.get("w_graph", 0.20)
                w_e = graph_weights.get("w_entry", 0.15)

                score_pre = (w_b * rank_features["bm25_norm"]) + (w_g * graph_proximity) + (w_e * entrypoint_boost)
                final_score = score_pre * current_penalty

            hit = {
                "chunk_id": r["chunk_id"],
                "repo_id": r["repo_id"],
                "path": r["path"],
                "range": f"{r['start_line']}-{r['end_line']}",
                "score": r["score"],
                "final_score": final_score,
                "layer": r["layer"],
                "type": r["artifact_type"],
                "sha256": r["content_sha256"],
                "why": {
                    "matched_terms": matched_terms,
                    "filter_pass": filter_pass,
                    "rank_features": rank_features,
                    "diagnostics": base_diagnostics
                }
            }
            if graph_index:
                hit["why_list"] = why_list

            ref_str = None
            try:
                ref_str = r["content_range_ref"]
            except IndexError:
                pass
            if ref_str:
                try:
                    hit["range_ref"] = json.loads(ref_str)
                except Exception:
                    pass

            results.append(hit)

        if semantic_model:
            # Re-rank results using semantic model
            try:
                # Use a lightweight dot product/cosine calculation if the model is mocked for tests,
                # or import standard util if it's the real sentence_transformers.
                query_emb = semantic_model.encode(query_text)
                if isinstance(query_emb, list):
                    try:
                        import numpy as np
                        query_emb = np.array(query_emb)
                    except ImportError:
                        pass
                if hasattr(query_emb, "shape") and len(query_emb.shape) == 2 and query_emb.shape[0] == 1:
                    query_emb = query_emb.flatten()

                if candidate_texts:
                    doc_embs = semantic_model.encode(candidate_texts)
                    if isinstance(doc_embs, list):
                        try:
                            import numpy as np
                            doc_embs = np.array(doc_embs)
                        except ImportError:
                            pass

                    try:
                        from sentence_transformers import util
                        cosine_scores = util.cos_sim(query_emb, doc_embs)[0]
                    except ImportError:
                        # Fallback for mocked models in tests
                        try:
                            import numpy as np
                            q = np.array(query_emb)
                            d = np.array(doc_embs)
                            q_norm = np.linalg.norm(q)
                            d_norm = np.linalg.norm(d, axis=1)
                            q_norm = q_norm if q_norm > 0 else 1.0
                            d_norm = np.where(d_norm > 0, d_norm, 1.0)
                            cosine_scores = np.dot(d, q) / (d_norm * q_norm)
                        except ImportError:
                            import math
                            def _dot(a, b): return sum(x * y for x, y in zip(a, b))
                            def _norm(a): return math.sqrt(sum(x * x for x in a))

                            q = query_emb
                            q_n = _norm(q) or 1.0
                            cosine_scores = []
                            for d in doc_embs:
                                d_n = _norm(d) or 1.0
                                cosine_scores.append(_dot(q, d) / (q_n * d_n))

                    for i, hit in enumerate(results):
                        old_score = hit.get("score", 0)
                        hit["score"] = float(cosine_scores[i])
                        hit["final_score"] = float(cosine_scores[i])
                        hit["why"]["rank_features"] = hit["why"].get("rank_features", {})
                        hit["why"]["rank_features"]["semantic_score"] = float(cosine_scores[i])
                        hit["why"]["rank_features"]["original_bm25"] = old_score
            except Exception as e:
                if fallback == "fail":
                    raise RuntimeError(f"Semantic re-ranking failed during encoding (fallback_behavior=fail): {e}") from e
                else:
                    base_diagnostics["semantic"]["error"] = f"Encoding failed: {e}"
                    base_diagnostics["semantic"]["enabled"] = False
                    semantic_model = None

        # Sort results deterministically to avoid random tie flips.
        results.sort(key=lambda x: (-x.get("final_score", 0), x["path"]))
        results = results[:k]

        out = {
            "query": query_text,
            "k": k,
            "engine": engine_type,
            "query_mode": query_mode,
            "applied_filters": filters,
            "count": len(results),
            "results": results
        }
        if fts_query_str is not None:
            out["fts_query"] = fts_query_str

        if explain:
            explain_block = {}
            explain_block["fts_query"] = fts_query_str if fts_query_str is not None else ""
            explain_block["filters"] = {k: v for k, v in (filters or {}).items() if v}
            if router_output:
                explain_block["router"] = router_output
            if ranker_meta:
                explain_block["ranker"] = ranker_meta
            if len(results) == 0:
                if fts_query_str is not None:
                    explain_block["why_zero"] = WHY_ZERO_TOKENS
                elif explain_block["filters"]:
                    explain_block["why_zero"] = WHY_ZERO_FILTERS
                else:
                    explain_block["why_zero"] = WHY_ZERO_NONE
            else:
                # extract top-k scoring from the hits
                # we just need a summary of scores
                explain_block["top_k_scoring"] = [{"chunk_id": r["chunk_id"], "score": r["score"]} for r in results[:k]]
            out["explain"] = explain_block

        return out

    except sqlite3.Error as e:
        msg = str(e).lower()
        if "no such module: fts5" in msg:
            raise RuntimeError("SQLite FTS5 extension missing in this environment.") from e
        elif "no such table: chunks_fts" in msg:
            raise RuntimeError("FTS table missing; likely old or corrupt index. Reindex required.") from e
        elif "no such function: bm25" in msg or "unable to use function bm25" in msg:
            raise RuntimeError("SQLite FTS5 auxiliary function 'bm25' missing.") from e
        elif "syntax error" in msg:
            raise RuntimeError(f"FTS syntax error. original='{query_text}', routed='{routed_query_raw}'") from e
        else:
            raise RuntimeError(f"Database error executing query: {e}") from e
    finally:
        if conn:
            conn.close()
