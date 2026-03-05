import argparse
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..retrieval.query_core import execute_query
from .stale_check import check_stale_index
from .policy_loader import load_and_validate_embedding_policy, EmbeddingPolicyError

def run_query(args: argparse.Namespace) -> int:
    index_path = Path(args.index)
    if not index_path.exists():
        print(f"Error: Index file not found: {index_path}", file=sys.stderr)
        return 1

    # Perform stale index check
    stale_policy = getattr(args, "stale_policy", "fail")
    is_stale = check_stale_index(index_path, stale_policy=stale_policy)
    if is_stale and stale_policy == "fail":
        return 1

    applied_filters = {
        "repo": args.repo,
        "path": args.path,
        "ext": args.ext,
        "layer": args.layer,
        "artifact_type": getattr(args, "artifact_type", None)
    }

    policy_instance = None
    if getattr(args, "embedding_policy", None):
        policy_path = Path(args.embedding_policy)
        try:
            policy_instance = load_and_validate_embedding_policy(policy_path)
        except EmbeddingPolicyError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    try:
        result = execute_query(
            index_path=index_path,
            query_text=args.q,
            k=args.k,
            filters=applied_filters,
            embedding_policy=policy_instance,
            explain=getattr(args, "explain", False),
            overmatch_guard=getattr(args, "overmatch_guard", False)
        )
    except RuntimeError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1

    if args.emit == "json":
        print(json.dumps(result, indent=2))
        return 0
    else:
        print(f"Found {result['count']} chunks for '{result['query']}'")
        print("-" * 60)
        for res in result["results"]:
            print(f"[{res['repo_id']}] {res['path']}:{res['range']}")
            print(f"    Type: {res['type']} | Layer: {res['layer']} | Score: {res['score']:.4f}")
        if "explain" in result:
            print("-" * 60)
            print("Explain Diagnostics:")
            print(json.dumps(result["explain"], indent=2))

    return 0
