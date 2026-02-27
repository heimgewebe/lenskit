import argparse
import sys
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any

def run_query(args: argparse.Namespace) -> int:
    index_path = Path(args.index)
    if not index_path.exists():
        print(f"Error: Index file not found: {index_path}", file=sys.stderr)
        return 1

    conn = None
    try:
        conn = sqlite3.connect(str(index_path))
        conn.row_factory = sqlite3.Row

        query_text = args.q
        limit = args.k

        where_clauses = []
        params = []

        if query_text:
            # FTS Query
            # Simple query cleaning: escape double quotes
            cleaned_q = query_text.replace('"', '""')

            # Use bm25 for scoring (standard FTS5 function)
            base_sql = """
                SELECT
                    c.chunk_id, c.repo_id, c.path, c.start_line, c.end_line, c.content_sha256,
                    c.layer, c.artifact_type,
                    bm25(chunks_fts) as score
                FROM chunks_fts
                JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
                WHERE chunks_fts MATCH ?
            """
            # Pass query directly. Simple syntax is robust across versions.
            params.append(cleaned_q)
            where_clauses.append("1=1") # Placeholder for appending ANDs easily

            # BM25: lower is better
            order_clause = "ORDER BY score ASC"
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
        if args.repo:
            where_clauses.append("c.repo_id = ?")
            params.append(args.repo)

        if args.path:
            where_clauses.append("c.path_norm LIKE ?")
            params.append(f"%{args.path.lower()}%")

        if args.ext:
            where_clauses.append("c.path_norm LIKE ?")
            ext = args.ext if args.ext.startswith(".") else f".{args.ext}"
            params.append(f"%{ext.lower()}")

        if args.layer:
            where_clauses.append("c.layer = ?")
            params.append(args.layer)

        # Combine clauses
        # If FTS query is active, base_sql already has WHERE chunks_fts MATCH ?
        # We append additional AND clauses.
        if query_text:
            # Skip the first placeholder "1=1" if we are appending to existing WHERE
            # Actually, `WHERE chunks_fts MATCH ?` is already there.
            # We need to append `AND ...`
            # Let's filter out the placeholder "1=1" if it's the only thing
            extras = [c for c in where_clauses if c != "1=1"]
            if extras:
                base_sql += " AND " + " AND ".join(extras)
        else:
            # For metadata query, we have `FROM chunks c`. We need to start WHERE clause.
            # `where_clauses` contains "1=1" plus others.
            base_sql += " WHERE " + " AND ".join(where_clauses)

        base_sql += f" {order_clause} LIMIT ?"
        params.append(limit)

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

        if args.emit == "json":
            out = {
                "query": query_text,
                "count": len(results),
                "results": results
            }
            print(json.dumps(out, indent=2))
        else:
            print(f"Found {len(results)} chunks for '{query_text}'")
            print("-" * 60)
            for res in results:
                print(f"[{res['repo_id']}] {res['path']}:{res['range']}")
                print(f"    Type: {res['type']} | Layer: {res['layer']} | Score: {res['score']:.4f}")

        return 0

    except sqlite3.Error as e:
        print(f"Error executing query: {e}", file=sys.stderr)
        return 1
    finally:
        if conn:
            conn.close()
