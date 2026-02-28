import re
import sys
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

def parse_gold_queries(md_path: Path) -> List[Dict[str, Any]]:
    if not md_path.exists():
        raise FileNotFoundError(f"Queries file not found: {md_path}")

    content = md_path.read_text(encoding="utf-8")
    queries = []
    current_query = None

    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue

        m_title = re.match(r"^\d+\.\s+\*\*\"(.+?)\"\*\*", line)
        if m_title:
            if current_query:
                queries.append(current_query)
            current_query = {
                "query": m_title.group(1),
                "expected_paths": [],
                "filters": {}
            }
            continue

        if not current_query:
            continue

        clean_line = re.sub(r"^[\s*+\-]+", "", line).strip()

        if re.match(r"^\*?Expected:?\*?", clean_line, re.IGNORECASE):
            expected_terms = re.findall(r"`([^`]+)`", line)
            current_query["expected_paths"].extend(expected_terms)

        if re.match(r"^\*?Filter:?\*?", clean_line, re.IGNORECASE):
            parts = clean_line.split(":", 1)
            if len(parts) > 1:
                rest = parts[1]
                matches = re.findall(r"(?:`|)?([\w.-]+)=([\w/.-]+)(?:`|)?", rest)
                for k, v in matches:
                    current_query["filters"][k] = v

    if current_query:
        queries.append(current_query)

    return queries

def execute_query(
    index_path: Path,
    query_text: str,
    k: int = 10,
    filters: Optional[Dict[str, Optional[str]]] = None
) -> Dict[str, Any]:
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

            cleaned_q = query_text.replace('"', '""')
            scoring_expr = "bm25(chunks_fts)"

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
            where_clauses.append("1=1")
            order_clause = "ORDER BY score ASC, c.repo_id ASC, c.path ASC, c.start_line ASC"
        else:
            base_sql = """
                SELECT
                    c.chunk_id, c.repo_id, c.path, c.start_line, c.end_line, c.content_sha256,
                    c.layer, c.artifact_type,
                    0 as score
                FROM chunks c
            """
            where_clauses.append("1=1")
            order_clause = "ORDER BY c.repo_id, c.path, c.start_line"

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

        if query_text:
            extras = [c for c in where_clauses if c != "1=1"]
            if extras:
                base_sql += " AND " + " AND ".join(extras)
        else:
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

def do_eval(index_path: Path, queries_path: Path, k: int, is_json_mode: bool = False) -> Optional[Dict[str, Any]]:
    try:
        gold_queries = parse_gold_queries(queries_path)
    except Exception as e:
        print(f"Error parsing queries file: {e}", file=sys.stderr)
        return None

    if not gold_queries:
        print("No queries found in input file.", file=sys.stderr)
        return None

    if not is_json_mode:
        print(f"Running Eval on {len(gold_queries)} queries against {index_path.name}...")
        print("-" * 60)
        print(f"{'Query':<40} | {'Found':<5} | {'Rel?':<4} | {'Top-1 Match':<30}")
        print("-" * 60)

    hits_at_k = 0
    total_queries = len(gold_queries)
    results_detail = []

    for q in gold_queries:
        q_text = q["query"]
        filters = q["filters"]
        expected = q["expected_paths"]

        try:
            res = execute_query(
                index_path=index_path,
                query_text=q_text,
                k=k,
                filters=filters
            )

            is_relevant = False
            top_match = "-"
            found_paths = [r["path"] for r in res["results"]]

            for hit_path in found_paths:
                for exp in expected:
                    if exp in hit_path:
                        is_relevant = True
                        top_match = hit_path
                        break
                if is_relevant:
                    break

            if is_relevant:
                hits_at_k += 1

            if not is_json_mode:
                rel_mark = "✅" if is_relevant else "❌"
                disp_q = (q_text[:37] + "..") if len(q_text) > 37 else q_text
                disp_match = (top_match[:27] + "..") if len(top_match) > 27 else top_match
                print(f"{disp_q:<40} | {res['count']:<5} | {rel_mark:<4} | {disp_match:<30}")

            results_detail.append({
                "query": q_text,
                "filters": filters,
                "expected": expected,
                "is_relevant": is_relevant,
                "hit_path": top_match if is_relevant else None,
                "found_count": res["count"],
                "top_results": found_paths
            })

        except Exception as e:
            if not is_json_mode:
                disp_q = (q_text[:37] + "..") if len(q_text) > 37 else q_text
                print(f"{disp_q:<40} | {'ERR':<5} | ❌   | error: {str(e)[:23]}", file=sys.stderr)

            results_detail.append({
                "query": q_text,
                "filters": filters,
                "expected": expected,
                "is_relevant": False,
                "hit_path": None,
                "found_count": 0,
                "top_results": [],
                "error": str(e)
            })

    recall_at_k = (hits_at_k / total_queries) * 100.0 if total_queries > 0 else 0.0

    if not is_json_mode:
        print("-" * 60)
        print(f"Recall@{k}: {recall_at_k:.1f}% ({hits_at_k}/{total_queries})")
        print("-" * 60)

    out = {
        "metrics": {
            f"recall@{k}": recall_at_k,
            "total_queries": total_queries,
            "hits": hits_at_k
        },
        "details": results_detail
    }
    return out
