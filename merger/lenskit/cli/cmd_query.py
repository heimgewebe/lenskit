import argparse
import sys
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

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

            # Robust BM25 detection
            try:
                # Test BM25 existence with minimal overhead, forcing parse/bind
                conn.execute("SELECT bm25(chunks_fts) FROM chunks_fts WHERE 0")
                scoring_expr = "bm25(chunks_fts)"
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if "no such module: fts5" in msg or "no such table: chunks_fts" in msg:
                    raise RuntimeError("SQLite FTS5 extension or table missing in this environment.") from e
                elif "no such function: bm25" in msg:
                    scoring_expr = "CAST(0.0 AS REAL)"
                else:
                    raise

            base_sql = f"""
                SELECT
                    c.chunk_id, c.repo_id, c.path, c.start_line, c.end_line, c.content_sha256,
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
                    c.chunk_id, c.repo_id, c.path, c.start_line, c.end_line, c.content_sha256,
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
            results.append({
                "chunk_id": r["chunk_id"],
                "repo_id": r["repo_id"],
                "path": r["path"],
                "range": f"{r['start_line']}-{r['end_line']}",
                "score": r["score"],
                "layer": r["layer"],
                "type": r["artifact_type"],
                "sha256": r["content_sha256"]
            })

        out = {
            "query": query_text,
            "count": len(results),
            "engine": engine_type,
            "query_mode": query_mode,
            "applied_filters": filters,
            "results": results
        }
        if fts_query_str is not None:
            out["fts_query"] = fts_query_str

        return out

    except sqlite3.Error as e:
        msg = str(e)
        if "no such module: fts5" in msg:
            raise RuntimeError("SQLite FTS5 extension missing in this environment.") from e
        elif "no such function: bm25" in msg:
            raise RuntimeError("SQLite FTS5 auxiliary function 'bm25' missing.") from e
        elif "syntax error" in msg:
            raise RuntimeError(f"FTS syntax error in query: '{query_text}'. Try simpler terms or quoting.") from e
        else:
            raise RuntimeError(f"Database error executing query: {e}") from e
    finally:
        if conn:
            conn.close()


def run_query(args: argparse.Namespace) -> int:
    index_path = Path(args.index)
    if not index_path.exists():
        print(f"Error: Index file not found: {index_path}", file=sys.stderr)
        return 1

    applied_filters = {
        "repo": args.repo,
        "path": args.path,
        "ext": args.ext,
        "layer": args.layer,
        "artifact_type": getattr(args, "artifact_type", None)
    }

    try:
        result = execute_query(
            index_path=index_path,
            query_text=args.q,
            k=args.k,
            filters=applied_filters
        )
    except RuntimeError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1

    if args.emit == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"Found {result['count']} chunks for '{result['query']}'")
        print("-" * 60)
        for res in result["results"]:
            print(f"[{res['repo_id']}] {res['path']}:{res['range']}")
            print(f"    Type: {res['type']} | Layer: {res['layer']} | Score: {res['score']:.4f}")

    return 0
