import argparse
import sys
from typing import List, Optional
from . import cmd_index
from . import cmd_query
from . import cmd_eval

def main(args: Optional[List[str]] = None) -> int:
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="lenskit",
        description="lenskit: Repo Understanding & Retrieval System"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Index command
    index_parser = subparsers.add_parser("index", help="Build or verify retrieval index")
    index_parser.add_argument("--dump", required=True, help="Path to dump_index.json")
    index_parser.add_argument("--chunk-index", required=True, help="Path to chunk_index.jsonl")
    index_parser.add_argument("--out", help="Output path for SQLite index")
    index_parser.add_argument("--rebuild", action="store_true", help="Force rebuild of index")
    index_parser.add_argument("--verify", action="store_true", help="Verify existing index freshness")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query the retrieval index")
    query_parser.add_argument("--index", required=True, help="Path to SQLite index")
    query_parser.add_argument("--q", default="", help="Search query text")
    query_parser.add_argument("--k", type=int, default=10, help="Max results")
    query_parser.add_argument("--repo", help="Filter by repo_id")
    query_parser.add_argument("--path", help="Filter by path substring")
    query_parser.add_argument("--ext", help="Filter by file extension")
    query_parser.add_argument("--layer", help="Filter by layer")
    query_parser.add_argument("--artifact-type", help="Filter by artifact_type")
    query_parser.add_argument("--emit", choices=["text", "json"], default="text", help="Output format")

    # Eval command
    eval_parser = subparsers.add_parser("eval", help="Evaluate retrieval quality against Gold Queries")
    eval_parser.add_argument("--index", required=True, help="Path to SQLite index")
    eval_parser.add_argument("--queries", default="docs/retrieval/queries.md", help="Path to queries markdown file")
    eval_parser.add_argument("--k", type=int, default=10, help="Max results for recall calculation")
    eval_parser.add_argument("--emit", choices=["text", "json"], default="text", help="Output format")

    # Verify command (placeholder)
    verify_parser = subparsers.add_parser("verify", help="Verify artifacts or bundles")

    parsed_args = parser.parse_args(args)

    if parsed_args.command is None:
        parser.print_help()
        return 0

    if parsed_args.command == "index":
        return cmd_index.run_index(parsed_args)
    elif parsed_args.command == "query":
        return cmd_query.run_query(parsed_args)
    elif parsed_args.command == "eval":
        return cmd_eval.run_eval(parsed_args)
    elif parsed_args.command == "verify":
        print("Verify command placeholder. Use pr-schau-verify for now.")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
