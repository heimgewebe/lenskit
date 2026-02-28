import argparse
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..retrieval.query_core import execute_query

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
