import re
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from .query_core import execute_query

def parse_gold_queries(md_path: Path) -> List[Dict[str, Any]]:
    if not md_path.exists():
        raise FileNotFoundError(f"Queries file not found: {md_path}")

    content = md_path.read_text(encoding="utf-8")

    if md_path.suffix == ".json":
        try:
            data = json.loads(content)
            queries = []
            for item in data:
                queries.append({
                    "query": item.get("query", ""),
                    "expected_paths": item.get("expected_patterns", []),
                    "filters": item.get("filters", {}),
                    "accept_criteria": item.get("accept_criteria", {})
                })
            return queries
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON queries file: {e}")

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
                "filters": {},
                "accept_criteria": {}
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

def do_eval(
    index_path: Path,
    queries_path: Path,
    k: int,
    is_json_mode: bool = False,
    is_stale: bool = False,
    embedding_policy: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
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
                filters=filters,
                embedding_policy=embedding_policy,
                explain=True
            )

            is_relevant = False
            top_match = "-"
            hit_why = None
            found_paths = [r["path"] for r in res["results"]]

            for r in res["results"]:
                hit_path = r["path"]
                for exp in expected:
                    if exp in hit_path:
                        is_relevant = True
                        top_match = hit_path
                        hit_why = r.get("why")
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

            detail = {
                "query": q_text,
                "filters": filters,
                "expected": expected,
                "is_relevant": is_relevant,
                "hit_path": top_match if is_relevant else None,
                "found_count": res["count"],
                "top_results": found_paths
            }
            if hit_why is not None:
                detail["why"] = hit_why
            if "explain" in res:
                detail["explain"] = res["explain"]

            results_detail.append(detail)

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
                "error": str(e),
                "explain": {
                    "error": str(e),
                    "filters": filters,
                    "why_fail": "query execution failed"
                }
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
            "hits": hits_at_k,
            "stale_flag": is_stale
        },
        "details": results_detail
    }

    return out
