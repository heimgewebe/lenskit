import argparse
import sys
import json
from pathlib import Path

from ..retrieval.eval_core import do_eval
from .stale_check import check_stale_index

def run_eval(args: argparse.Namespace) -> int:
    index_path = Path(args.index)
    if not index_path.exists():
        print(f"Error: Index file not found: {index_path}", file=sys.stderr)
        return 1

    # Perform non-fatal stale index check
    check_stale_index(index_path)

    queries_path = Path(args.queries) if args.queries else Path("docs/retrieval/queries.md")
    is_json_mode = (args.emit == "json")

    out = do_eval(index_path, queries_path, args.k, is_json_mode)
    if out is None:
        return 1

    if is_json_mode:
        print(json.dumps(out, indent=2))

    return 0
