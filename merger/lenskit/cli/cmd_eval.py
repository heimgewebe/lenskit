import argparse
import sys
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from . import cmd_query

def parse_gold_queries(md_path: Path) -> List[Dict[str, Any]]:
    """
    Parses the Gold Queries markdown file.
    Extracts query text, expected paths (from expected block), and filters.
    """
    if not md_path.exists():
        raise FileNotFoundError(f"Queries file not found: {md_path}")

    content = md_path.read_text(encoding="utf-8")
    queries = []

    # Regex to find query blocks:
    # 1. **"query text"**
    # 2. *Intent:* ...
    # 3. *Expected:* ... (extracts `backticked` terms as path substrings)
    # 4. *Filter:* ... (optional, key=value)

    # We iterate line by line for robustness
    current_query = None

    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 1. Match Query Title: 1. **"query text"**
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

        # Check for keywords. We remove markdown bullets (*, -) and formatting (*) from start
        # Normalized check: remove non-alphanumeric prefix
        clean_line = re.sub(r"^[\s*+\-]+", "", line).strip()
        # Should now be "Expected: ..." or "Intent: ..." or "Filter: ..."

        # 3. Match Expected: *Expected:* `file.py`, `dir/`
        if re.match(r"^\*?Expected:?\*?", clean_line, re.IGNORECASE):
            # Extract all backticked terms
            expected_terms = re.findall(r"`([^`]+)`", line)
            current_query["expected_paths"].extend(expected_terms)

        # 4. Match Filter: *Filter:* `layer=core`
        if re.match(r"^\*?Filter:?\*?", clean_line, re.IGNORECASE):
            # Extract key=value pairs, often in backticks or plain text
            # Strategy: look for k=v patterns
            # Find the colon
            parts = clean_line.split(":", 1)
            if len(parts) > 1:
                rest = parts[1]
                # Find all `key=value` or key=value
                # Regex logic:
                # (?:`|)? : optional backtick start
                # ([\w.-]+) : key (alphanumeric + dot + dash)
                # = : literal equal
                # ([\w/.-]+) : value (alphanumeric + slash + dot + dash)
                # (?:`|)? : optional backtick end
                matches = re.findall(r"(?:`|)?([\w.-]+)=([\w/.-]+)(?:`|)?", rest)
                for k, v in matches:
                    current_query["filters"][k] = v

    if current_query:
        queries.append(current_query)

    return queries

def run_eval(args: argparse.Namespace) -> int:
    index_path = Path(args.index)
    if not index_path.exists():
        print(f"Error: Index file not found: {index_path}", file=sys.stderr)
        return 1

    queries_path = Path(args.queries) if args.queries else Path("docs/retrieval/queries.md")

    try:
        gold_queries = parse_gold_queries(queries_path)
    except Exception as e:
        print(f"Error parsing queries file: {e}", file=sys.stderr)
        return 1

    if not gold_queries:
        print("No queries found in input file.", file=sys.stderr)
        return 1

    is_json_mode = (args.emit == "json")

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

        # Execute Query
        try:
            res = cmd_query.execute_query(
                index_path=index_path,
                query_text=q_text,
                k=args.k, # Use CLI k (default 10) for Recall@K
                filters=filters
            )

            # Check Relevance
            # Definition: At least one result in Top-K contains one of the expected substrings in its path.
            is_relevant = False
            top_match = "-"

            found_paths = [r["path"] for r in res["results"]]

            for hit_path in found_paths:
                # Check against all expected terms
                for exp in expected:
                    # remove trailing slash for directory matching if needed,
                    # but simple substring usually works enough for "dir/" in "path/to/dir/file.py"
                    if exp in hit_path:
                        is_relevant = True
                        top_match = hit_path
                        break
                if is_relevant:
                    break

            if is_relevant:
                hits_at_k += 1

            if not is_json_mode:
                # Console Output Row
                rel_mark = "✅" if is_relevant else "❌"
                # Truncate query for display
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
            # Explicitly handle failure: counts as irrelevant + error
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
            # Continue to next query, failure is recorded

    # Metrics
    recall_at_k = (hits_at_k / total_queries) * 100.0 if total_queries > 0 else 0.0

    if not is_json_mode:
        print("-" * 60)
        print(f"Recall@{args.k}: {recall_at_k:.1f}% ({hits_at_k}/{total_queries})")
        print("-" * 60)

    if is_json_mode:
        out = {
            "metrics": {
                f"recall@{args.k}": recall_at_k,
                "total_queries": total_queries,
                "hits": hits_at_k
            },
            "details": results_detail
        }
        print(json.dumps(out, indent=2))

    return 0
