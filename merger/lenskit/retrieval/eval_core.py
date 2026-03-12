import re
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .query_core import execute_query

WHY_FAIL_QUERY_EXECUTION = "query execution failed"
WHY_FAIL_MISSING_EXPLAIN = "missing explain from query execution"

RE_MD_QUERY_TITLE = re.compile(r"^\d+\.\s+\*\*\"(.+?)\"\*\*")
RE_CLEAN_MD_LINE = re.compile(r"^[\s*+\-]+")
RE_EXPECTED_LABEL = re.compile(r"^\*?Expected:?\*?", re.IGNORECASE)
RE_CODE_TICKS = re.compile(r"`([^`]+)`")
RE_CATEGORY_LABEL = re.compile(r"^\*?Category:?\*?\s*(.+)$", re.IGNORECASE)
RE_FILTER_LABEL = re.compile(r"^\*?Filter:?\*?", re.IGNORECASE)
RE_FILTER_KV = re.compile(r"(?:`|)?([\w.-]+)=([\w/.-]+)(?:`|)?")

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
                    "category": item.get("category"),
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

        m_title = RE_MD_QUERY_TITLE.match(line)
        if m_title:
            if current_query:
                queries.append(current_query)
            current_query = {
                "query": m_title.group(1),
                "category": None,
                "expected_paths": [],
                "filters": {},
                "accept_criteria": {}
            }
            continue

        if not current_query:
            continue

        clean_line = RE_CLEAN_MD_LINE.sub("", line).strip()

        if RE_EXPECTED_LABEL.match(clean_line):
            expected_terms = RE_CODE_TICKS.findall(line)
            current_query["expected_paths"].extend(expected_terms)

        m_category = RE_CATEGORY_LABEL.match(clean_line)
        if m_category:
            current_query["category"] = m_category.group(1).strip()
            continue

        if RE_FILTER_LABEL.match(clean_line):
            parts = clean_line.split(":", 1)
            if len(parts) > 1:
                rest = parts[1]
                matches = RE_FILTER_KV.findall(rest)
                for k, v in matches:
                    current_query["filters"][k] = v

    if current_query:
        queries.append(current_query)

    return queries

def evaluate_single_run(
    q_text: str,
    filters: Dict[str, str],
    expected: List[str],
    index_path: Path,
    k: int,
    embedding_policy: Optional[Dict[str, Any]],
    graph_index_path: Optional[Path],
    graph_weights: Optional[Dict[str, float]]
) -> Tuple[bool, str, Optional[Dict[str, Any]], List[str], int, float, Dict[str, Any]]:
    res = execute_query(
        index_path=index_path,
        query_text=q_text,
        k=k,
        filters=filters,
        embedding_policy=embedding_policy,
        explain=True,
        graph_index_path=graph_index_path,
        graph_weights=graph_weights
    )

    is_relevant = False
    top_match = "-"
    hit_why = None
    found_paths = [r["path"] for r in res["results"]]
    rr = 0.0

    for idx, r in enumerate(res["results"]):
        hit_path = r["path"]
        for exp in expected:
            if exp in hit_path:
                if not is_relevant:
                    is_relevant = True
                    top_match = hit_path
                    hit_why = r.get("why")
                    rr = 1.0 / (idx + 1)
                break
        if is_relevant:
            break

    return is_relevant, top_match, hit_why, found_paths, res["count"], rr, res


def do_eval(
    index_path: Path,
    queries_path: Path,
    k: int,
    is_json_mode: bool = False,
    is_stale: bool = False,
    embedding_policy: Optional[Dict[str, Any]] = None,
    graph_index_path: Optional[Path] = None,
    graph_weights: Optional[Dict[str, float]] = None
) -> Optional[Dict[str, Any]]:
    """
    Executes a benchmark evaluation of the retrieval system against gold queries.

    When `embedding_policy` is provided (Compare Mode):
    - The system runs each query twice: once as a pure lexical baseline, and once utilizing the semantic reranker.
    - If the semantic pipeline raises an exception (even if `fallback_behavior="fail"`),
      the exception is trapped and isolated.
    - The evaluation script will NOT abort. The lexical baseline data remains preserved,
      and the semantic error string is explicitly logged within the `semantic.error` block of the JSON output.
    """
    try:
        gold_queries = parse_gold_queries(queries_path)
    except Exception as e:
        print(f"Error parsing queries file: {e}", file=sys.stderr)
        return None

    if not gold_queries:
        print("No queries found in input file.", file=sys.stderr)
        return None

    compare_mode = (embedding_policy is not None) or (graph_index_path is not None)
    if embedding_policy is not None and graph_index_path is not None:
        compare_type = "sem_graph"
        compare_label = "Sem+Graph"
    elif embedding_policy is not None:
        compare_type = "semantic"
        compare_label = "Semantic"
    elif graph_index_path is not None:
        compare_type = "graph"
        compare_label = "Graph"
    else:
        compare_type = "none"
        compare_label = "None"

    if not is_json_mode:
        print(f"Running Eval on {len(gold_queries)} queries against {index_path.name}...")
        print("-" * 80 if compare_mode else "-" * 60)
        if compare_mode:
            print(f"{'Query':<35} | {'Base (RR / Match)':<25} | {compare_label + ' (RR / Match)':<25}")
        else:
            print(f"{'Query':<40} | {'Found':<5} | {'Rel?':<4} | {'Top-1 Match':<30}")
        print("-" * 80 if compare_mode else "-" * 60)

    base_hits_at_k = 0
    base_mrr_sum = 0.0
    sem_hits_at_k = 0
    sem_mrr_sum = 0.0
    zero_hit_count = 0
    total_queries = len(gold_queries)
    results_detail = []
    category_stats: Dict[str, Dict[str, Any]] = {}

    for q in gold_queries:
        q_text = q["query"]
        category = q.get("category")
        filters = q["filters"]
        expected = q["expected_paths"]

        cat_key = category if category else "uncategorized"
        if cat_key not in category_stats:
            category_stats[cat_key] = {"total_queries": 0, "base_hits": 0, "base_mrr_sum": 0.0, "sem_hits": 0, "sem_mrr_sum": 0.0}
        category_stats[cat_key]["total_queries"] += 1

        try:
            # Baseline run (no embedding policy)
            b_rel, b_match, b_why, b_paths, b_count, b_rr, b_res = evaluate_single_run(q_text, filters, expected, index_path, k, None, None, graph_weights)

            s_rel, s_match, s_why, s_paths, s_count, s_rr, s_res = False, "-", None, [], 0, 0.0, {}
            sem_error_str = None
            if compare_mode:
                try:
                    # Semantic run
                    s_rel, s_match, s_why, s_paths, s_count, s_rr, s_res = evaluate_single_run(
                        q_text, filters, expected, index_path, k, embedding_policy, graph_index_path, graph_weights
                    )
                except Exception as e:
                    # We catch a broad Exception here intentionally. This guarantees that absolutely any
                    # catastrophic failure in the semantic path (e.g. OOM, bad schema, model crash)
                    # is perfectly isolated, ensuring the valid Baseline metrics remain intact for evaluation.
                    sem_error_str = str(e)
                    s_res = {"explain": {"filters": filters, "why_fail": WHY_FAIL_QUERY_EXECUTION}}

            if b_count == 0 and (not compare_mode or s_count == 0):
                zero_hit_count += 1

            if b_rel:
                base_hits_at_k += 1
                category_stats[cat_key]["base_hits"] += 1
            base_mrr_sum += b_rr
            category_stats[cat_key]["base_mrr_sum"] += b_rr

            if compare_mode:
                if s_rel:
                    sem_hits_at_k += 1
                    category_stats[cat_key]["sem_hits"] += 1
                sem_mrr_sum += s_rr
                category_stats[cat_key]["sem_mrr_sum"] += s_rr

            if not is_json_mode:
                disp_q = (q_text[:32] + "..") if len(q_text) > 32 else q_text
                if compare_mode:
                    b_disp_match = (b_match[:15] + "..") if len(b_match) > 15 else b_match
                    s_disp_match = (s_match[:15] + "..") if len(s_match) > 15 else s_match
                    b_str = f"{b_rr:.2f} / {b_disp_match}" if b_rel else f"0.00 / ❌"
                    if sem_error_str:
                        s_str = f"ERR / ❌"
                    else:
                        s_str = f"{s_rr:.2f} / {s_disp_match}" if s_rel else f"0.00 / ❌"
                    print(f"{disp_q:<35} | {b_str:<25} | {s_str:<25}")
                else:
                    rel_mark = "✅" if b_rel else "❌"
                    disp_match = (b_match[:27] + "..") if len(b_match) > 27 else b_match
                    print(f"{disp_q:<40} | {b_count:<5} | {rel_mark:<4} | {disp_match:<30}")

            detail = {
                "query": q_text,
                "category": cat_key,
                "filters": filters,
                "expected": expected,
                "is_relevant": b_rel,
                "hit_path": b_match if b_rel else None,
                "found_count": b_count,
                "top_results": b_paths,
                "rr": b_rr,
                "explain": b_res.get("explain", {"filters": filters, "why_fail": WHY_FAIL_MISSING_EXPLAIN})
            }
            if b_why is not None:
                detail["why"] = b_why

            if compare_mode:
                detail["baseline"] = {
                    "is_relevant": b_rel,
                    "hit_path": b_match if b_rel else None,
                    "found_count": b_count,
                    "top_results": b_paths,
                    "rr": b_rr,
                    "explain": b_res.get("explain", {"filters": filters, "why_fail": WHY_FAIL_MISSING_EXPLAIN})
                }
                detail[compare_type] = {
                    "is_relevant": s_rel,
                    "hit_path": s_match if s_rel else None,
                    "found_count": s_count,
                    "top_results": s_paths,
                    "rr": s_rr,
                    "explain": s_res.get("explain", {"filters": filters, "why_fail": WHY_FAIL_MISSING_EXPLAIN})
                }
                if sem_error_str:
                    detail[compare_type]["error"] = sem_error_str
                detail["delta_rr"] = s_rr - b_rr
                # Overwrite backwards-compatible base fields with semantic ones if we're evaluating semantic overall
                detail["is_relevant"] = s_rel
                detail["hit_path"] = s_match if s_rel else None
                detail["found_count"] = s_count
                detail["top_results"] = s_paths
                detail["rr"] = s_rr
                detail["explain"] = s_res.get("explain", {"filters": filters, "why_fail": WHY_FAIL_MISSING_EXPLAIN})
                if s_why is not None:
                    detail["why"] = s_why
                if sem_error_str:
                    detail["error"] = f"Semantic Run Error: {sem_error_str}"

            results_detail.append(detail)

        except RuntimeError as e:
            if "Invalid graph index JSON" in str(e) or "Explicitly provided graph index file does not exist" in str(e):
                raise e
            if not is_json_mode:
                disp_q = (q_text[:32] + "..") if len(q_text) > 32 else q_text
                if compare_mode:
                    print(f"{disp_q:<35} | {'ERR':<25} | {'ERR':<25}", file=sys.stderr)
                else:
                    print(f"{disp_q:<40} | {'ERR':<5} | ❌   | error: {str(e)[:23]}", file=sys.stderr)

            results_detail.append({
                "query": q_text,
                "category": cat_key,
                "filters": filters,
                "expected": expected,
                "is_relevant": False,
                "hit_path": None,
                "found_count": 0,
                "top_results": [],
                "error": str(e),
                "why": {"why_fail": WHY_FAIL_QUERY_EXECUTION},
                "explain": {"filters": filters, "why_fail": WHY_FAIL_QUERY_EXECUTION}
            })

        except Exception as e:
            if not is_json_mode:
                disp_q = (q_text[:32] + "..") if len(q_text) > 32 else q_text
                if compare_mode:
                    print(f"{disp_q:<35} | {'ERR':<25} | {'ERR':<25}", file=sys.stderr)
                else:
                    print(f"{disp_q:<40} | {'ERR':<5} | ❌   | error: {str(e)[:23]}", file=sys.stderr)

            results_detail.append({
                "query": q_text,
                "category": cat_key,
                "filters": filters,
                "expected": expected,
                "is_relevant": False,
                "hit_path": None,
                "found_count": 0,
                "top_results": [],
                "error": str(e),
                "explain": {
                    "filters": filters,
                    "why_fail": WHY_FAIL_QUERY_EXECUTION
                }
            })

    base_recall_at_k = (base_hits_at_k / total_queries) * 100.0 if total_queries > 0 else 0.0
    base_mrr = base_mrr_sum / total_queries if total_queries > 0 else 0.0

    sem_recall_at_k = (sem_hits_at_k / total_queries) * 100.0 if total_queries > 0 else 0.0
    sem_mrr = sem_mrr_sum / total_queries if total_queries > 0 else 0.0

    zero_hit_ratio = zero_hit_count / total_queries if total_queries > 0 else 0.0

    for cat_data in category_stats.values():
        c_total = cat_data["total_queries"]
        cat_data[f"recall@{k}"] = (cat_data["base_hits"] / c_total) * 100.0 if c_total > 0 else 0.0
        cat_data["MRR"] = cat_data["base_mrr_sum"] / c_total if c_total > 0 else 0.0

        if compare_mode:
            cat_data[f"{compare_type}_recall@{k}"] = (cat_data["sem_hits"] / c_total) * 100.0 if c_total > 0 else 0.0
            cat_data[f"{compare_type}_MRR"] = cat_data["sem_mrr_sum"] / c_total if c_total > 0 else 0.0

    if not is_json_mode:
        print("-" * 80 if compare_mode else "-" * 60)
        if compare_mode:
            print(f"Base Recall@{k}: {base_recall_at_k:.1f}% ({base_hits_at_k}/{total_queries}) | Base MRR: {base_mrr:.3f}")
            print(f"{compare_label[:4]:<4} Recall@{k}: {sem_recall_at_k:.1f}% ({sem_hits_at_k}/{total_queries}) | {compare_label[:4]:<4} MRR: {sem_mrr:.3f}")
            print(f"Delta Recall@{k}: {(sem_recall_at_k - base_recall_at_k):+.1f}% | Delta MRR: {(sem_mrr - base_mrr):+.3f}")
            print(f"0-Hits Ratio: {zero_hit_ratio:.2f} ({zero_hit_count}/{total_queries})")
            for cat, stats in category_stats.items():
                print(f"  {cat} Base Recall@{k}: {stats[f'recall@{k}']:.1f}% | Base MRR: {stats['MRR']:.3f}")
                print(f"  {cat} {compare_label[:4]:<4} Recall@{k}: {stats.get(f'{compare_type}_recall@{k}', 0):.1f}% | {compare_label[:4]:<4} MRR: {stats.get(f'{compare_type}_MRR', 0):.3f}")
        else:
            print(f"Recall@{k}: {base_recall_at_k:.1f}% ({base_hits_at_k}/{total_queries}) | MRR: {base_mrr:.3f}")
            print(f"0-Hits Ratio: {zero_hit_ratio:.2f} ({zero_hit_count}/{total_queries})")
            for cat, stats in category_stats.items():
                print(f"  {cat} Recall@{k}: {stats[f'recall@{k}']:.1f}% | MRR: {stats['MRR']:.3f}")
        print("-" * 80 if compare_mode else "-" * 60)

    out = {
        "metrics": {
            f"recall@{k}": sem_recall_at_k if compare_mode else base_recall_at_k,
            f"baseline_recall@{k}": base_recall_at_k,
            "MRR": sem_mrr if compare_mode else base_mrr,
            "baseline_MRR": base_mrr,
            "total_queries": total_queries,
            "hits": sem_hits_at_k if compare_mode else base_hits_at_k,
            "baseline_hits": base_hits_at_k,
            "stale_flag": is_stale,
            "zero_hit_ratio": zero_hit_ratio,
            "categories": category_stats
        },
        "details": results_detail
    }

    if compare_mode:
        out["metrics"][f"{compare_type}_recall@{k}"] = sem_recall_at_k
        out["metrics"][f"{compare_type}_MRR"] = sem_mrr
        out["metrics"][f"{compare_type}_hits"] = sem_hits_at_k
        out["metrics"]["delta_recall"] = sem_recall_at_k - base_recall_at_k
        out["metrics"]["delta_mrr"] = sem_mrr - base_mrr

        # Backwards compatibility specifically for semantic eval callers.
        # These additional semantic_* metrics in non-semantic compare modes serve purely for backward compatibility.
        if compare_type != "semantic":
            out["metrics"][f"semantic_recall@{k}"] = sem_recall_at_k
            out["metrics"]["semantic_MRR"] = sem_mrr

    return out
