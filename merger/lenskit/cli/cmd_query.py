import argparse
import sys
import json
import sqlite3
import hashlib
from pathlib import Path
from typing import List, Dict, Any

def run_query(args: argparse.Namespace) -> int:
    index_path = Path(args.index)
    if not index_path.exists():
        print(f"Error: Index file not found: {index_path}", file=sys.stderr)
        return 1

    try:
        conn = sqlite3.connect(str(index_path))
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as e:
        print(f"Error connecting to index: {e}", file=sys.stderr)
        return 1

    query_text = args.q
    limit = args.k

    # FTS handling: If text query exists, we use MATCH on chunks_fts
    # We join chunks and chunks_fts on chunk_id (since rowid is implicit and potentially mismatched if we reload?)
    # Wait, in index_db we insert chunks first, then fts. Rowid sequence is NOT guaranteed to match unless explicit.
    # But we used separate tables.
    # In `index_db.py`, `chunks` table has `chunk_id` PRIMARY KEY.
    # `chunks_fts` has `chunk_id` UNINDEXED column.
    # So we join on `chunk_id`.

    where_clauses = []
    params = []

    if query_text:
        # FTS Query
        # Simple query cleaning: escape double quotes
        cleaned_q = query_text.replace('"', '""')

        # FTS5 syntax: {col1 col2} : "query"
        # We query against content and path_tokens
        fts_match_expr = f'{{content path_tokens}} : "{cleaned_q}"'

        base_sql = """
            SELECT
                c.chunk_id, c.repo_id, c.path, c.start_line, c.end_line, c.content_sha256,
                c.layer, c.artifact_type,
                chunks_fts.rank as score
            FROM chunks_fts
            JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
            WHERE chunks_fts MATCH ?
        """
        params.append(fts_match_expr)

        order_clause = "ORDER BY chunks_fts.rank"
    else:
        # Metadata only query
        base_sql = """
            SELECT
                c.chunk_id, c.repo_id, c.path, c.start_line, c.end_line, c.content_sha256,
                c.layer, c.artifact_type,
                0 as score
            FROM chunks c
        """
        where_clauses.append("1=1") # placeholder for WHERE
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

    if where_clauses:
        if query_text:
            base_sql += " AND " + " AND ".join(where_clauses)
        else:
            base_sql += " WHERE " + " AND ".join(where_clauses)

    base_sql += f" {order_clause} LIMIT ?"
    params.append(limit)

    try:
        cursor = conn.execute(base_sql, params)
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error executing query: {e}", file=sys.stderr)
        return 1

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
