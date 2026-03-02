import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional

def execute_query(
    index_path: Path,
    query_text: str,
    k: int = 10,
    filters: Optional[Dict[str, Optional[str]]] = None
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

        if query_text:
            engine_type = "fts5"
            query_mode = "fts"

            # FTS Query: Escape double quotes
            cleaned_q = query_text.replace('"', '""')

            scoring_expr = "bm25(chunks_fts)"

            base_sql = f"""
                SELECT
                    c.chunk_id, c.repo_id, c.path, c.start_line, c.end_line, c.start_byte, c.end_byte, c.content_sha256,
                    c.layer, c.artifact_type,
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
                    c.layer, c.artifact_type,
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

        base_sql += f" {order_clause} LIMIT ?"
        params.append(k)

        cursor = conn.execute(base_sql, params)
        rows = cursor.fetchall()

        results = []
        for r in rows:
            matched_terms = [query_text] if query_text else [query_mode]
            filter_pass = [k for k, v in filters.items() if v]

            rank_features = {}
            if query_text:
                rank_features["bm25"] = r["score"]
            else:
                rank_features["metadata"] = 0

            hit = {
                "chunk_id": r["chunk_id"],
                "repo_id": r["repo_id"],
                "path": r["path"],
                "range": f"{r['start_line']}-{r['end_line']}",
                "score": r["score"],
                "layer": r["layer"],
                "type": r["artifact_type"],
                "sha256": r["content_sha256"],
                "why": {
                    "matched_terms": matched_terms,
                    "filter_pass": filter_pass,
                    "rank_features": rank_features
                }
            }

            # NOTE: We do not currently emit a `range_ref` here because `r["path"]` is a repo-internal
            # path, whereas the `file_path` field in a `range_ref` must deterministically match the
            # artifact path listed in the manifest. Emitting it here would create semantically
            # invalid references. Once the indexing pipeline provides the precise bundle artifact
            # path for each chunk, this can be re-enabled.

            results.append(hit)

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
            raise RuntimeError(f"FTS syntax error in query: '{query_text}'. Try simpler terms or quoting.") from e
        else:
            raise RuntimeError(f"Database error executing query: {e}") from e
    finally:
        if conn:
            conn.close()
