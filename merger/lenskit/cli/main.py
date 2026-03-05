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
    query_parser.add_argument("--stale-policy", choices=["warn", "fail", "ignore"], default="fail", help="Policy for handling stale indices")
    query_parser.add_argument("--embedding-policy", help="Path to embedding-policy.v1 JSON policy instance (requests semantic pipeline; currently candidate overfetch only)")
    query_parser.add_argument("--explain", action="store_true", help="Include diagnostic explain block in query results")
    query_parser.add_argument("--overmatch-guard", action="store_true", help="Disable synonym OR-expansion in router")

    # Eval command
    eval_parser = subparsers.add_parser("eval", help="Evaluate retrieval quality against Gold Queries")
    eval_parser.add_argument("--index", required=True, help="Path to SQLite index")
    eval_parser.add_argument("--queries", default="docs/retrieval/queries.md", help="Path to queries markdown file")
    eval_parser.add_argument("--k", type=int, default=10, help="Max results for recall calculation")
    eval_parser.add_argument("--emit", choices=["text", "json"], default="text", help="Output format")
    eval_parser.add_argument("--stale-policy", choices=["warn", "fail", "ignore"], default="fail", help="Policy for handling stale indices")
    eval_parser.add_argument("--embedding-policy", help="Path to embedding-policy.v1 JSON policy instance (requests semantic pipeline; currently candidate overfetch only)")

    # Range command
    range_parser = subparsers.add_parser("range", help="Range operations")
    range_subparsers = range_parser.add_subparsers(dest="range_cmd", required=True, help="Range commands")
    range_get_parser = range_subparsers.add_parser("get", help="Get a deterministic byte range from an artifact")
    range_get_parser.add_argument("--manifest", required=True, help="Path to bundle manifest or dump index")
    range_get_parser.add_argument("--ref", required=True, help="Path to range_ref JSON file")
    range_get_parser.add_argument("--format", choices=["raw", "json"], default="json", help="Output format")

    # PR-Explain command
    pr_explain_parser = subparsers.add_parser("pr-explain", help="Explain PR context")
    pr_explain_parser.add_argument("--delta", required=True, help="Path to delta.json file")

    # Verify command (placeholder)
    verify_parser = subparsers.add_parser("verify", help="Verify artifacts or bundles")

    # Architecture command
    architecture_parser = subparsers.add_parser("architecture", help="Extract architecture views")
    architecture_parser.add_argument("--repo", default=".", help="Path to repository root")
    architecture_group = architecture_parser.add_mutually_exclusive_group(required=True)
    architecture_group.add_argument("--entrypoints", action="store_true", help="Extract entrypoints")
    architecture_group.add_argument("--import-graph", action="store_true", help="Extract Python import graph")

    # Atlas command
    atlas_parser = subparsers.add_parser("atlas", help="Atlas filesystem crawler")
    atlas_subparsers = atlas_parser.add_subparsers(dest="atlas_cmd", required=True, help="Atlas commands")
    atlas_scan_parser = atlas_subparsers.add_parser("scan", help="Scan a filesystem path")
    atlas_scan_parser.add_argument("path", help="The root path to scan")
    atlas_scan_parser.add_argument("--exclude", help="Comma-separated list of glob patterns to exclude")
    atlas_scan_parser.add_argument("--no-default-excludes", action="store_true", help="Do not use default system excludes")
    atlas_scan_parser.add_argument("--max-file-size", type=int, help="Maximum file size in MB to include in scan (default 50)")
    atlas_scan_parser.add_argument("--no-max-file-size", action="store_true", help="Remove file size limits for the scan")
    atlas_scan_parser.add_argument("--depth", type=int, default=6, help="Maximum depth to scan")
    atlas_scan_parser.add_argument("--limit", type=int, default=200000, help="Maximum number of entries to scan")

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
    elif parsed_args.command == "range":
        if parsed_args.range_cmd == "get":
            return cmd_range_get(parsed_args)
        else:
            parser.parse_args(["range", "--help"])
            return 0
    elif parsed_args.command == "pr-explain":
        from . import pr_explain
        return pr_explain.run_pr_explain(parsed_args)
    elif parsed_args.command == "verify":
        print("Verify command placeholder. Use pr-schau-verify for now.")
        return 1
    elif parsed_args.command == "architecture":
        from . import cmd_architecture
        return cmd_architecture.run_architecture_cmd(parsed_args)
    elif parsed_args.command == "atlas":
        if parsed_args.atlas_cmd == "scan":
            from . import cmd_atlas
            return cmd_atlas.run_atlas_scan(parsed_args)
        else:
            parser.parse_args(["atlas", "--help"])
            return 0

    return 0


def cmd_range_get(args: argparse.Namespace) -> int:
    import sys
    import json
    from pathlib import Path
    from merger.lenskit.core.range_resolver import resolve_range_ref

    manifest_path = Path(args.manifest)
    ref_path = Path(args.ref)

    try:
        if not ref_path.exists():
            raise FileNotFoundError(f"range_ref file not found: {ref_path}")

        with ref_path.open("r", encoding="utf-8") as f:
            ref = json.load(f)

        result = resolve_range_ref(manifest_path, ref)

        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(result["text"], end="")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
