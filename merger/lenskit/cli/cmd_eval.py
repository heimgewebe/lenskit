import argparse
import sys
import json
from pathlib import Path

from ..retrieval.eval_core import do_eval, parse_gold_queries
from .stale_check import check_stale_index

def run_eval(args: argparse.Namespace) -> int:
    index_path = Path(args.index)
    if not index_path.exists():
        print(f"Error: Index file not found: {index_path}", file=sys.stderr)
        return 1

    # Perform non-fatal stale index check
    is_stale = check_stale_index(index_path)

    queries_path = Path(args.queries) if args.queries else Path("docs/retrieval/queries.md")
    is_json_mode = (args.emit == "json")

    out = do_eval(index_path, queries_path, args.k, is_json_mode, is_stale)
    if out is None:
        return 1

    if is_json_mode:
        print(json.dumps(out, indent=2))

    # Evaluate against accept_criteria if present in a JSON queries file
    if queries_path.suffix == ".json":
        try:
            # We parse the gold queries a second time here. This avoids breaking the existing
            # do_eval API while keeping gate threshold logic strictly in the CLI wrapper.
            gold_queries = parse_gold_queries(queries_path)

            # Determine the global required recall across all queries' accept_criteria.
            # We enforce exactly one threshold (global recall@k). If multiple distinct thresholds
            # are found, we fail, as per explicit gate semantics.
            thresholds = set()
            for q in gold_queries:
                ac = q.get("accept_criteria", {})
                if f"recall_at_{args.k}" in ac:
                    thresholds.add(float(ac[f"recall_at_{args.k}"]))

            if len(thresholds) > 1:
                print(f"Error: Multiple conflicting recall_at_{args.k} thresholds found in queries. Gate requires exactly one global threshold.", file=sys.stderr)
                return 1

            if len(thresholds) == 1:
                required_recall = thresholds.pop()
                actual_recall = out["metrics"].get(f"recall@{args.k}", 0.0)

                # The criteria is typically a ratio (0.0 to 1.0) but metrics is a percentage (0.0 to 100.0), so normalize
                target_percent = required_recall * 100.0 if required_recall <= 1.0 else required_recall

                if actual_recall < target_percent:
                    print(f"Error: Recall@{args.k} ({actual_recall:.1f}%) did not meet the global required threshold ({target_percent:.1f}%).", file=sys.stderr)
                    return 1
        except Exception as e:
            print(f"Error evaluating accept criteria: {e}", file=sys.stderr)
            return 1

    return 0
