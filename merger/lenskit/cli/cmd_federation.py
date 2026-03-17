import argparse
import sys
import json
from pathlib import Path

def register_federation_commands(subparsers) -> None:
    """Registers federation subcommands and arguments."""
    federation_parser = subparsers.add_parser("federation", help="Manage federated cross-repo bundles")
    federation_subparsers = federation_parser.add_subparsers(dest="federation_command", required=True)

    # init
    init_parser = federation_subparsers.add_parser("init", help="Initialize a new federation index")
    init_parser.add_argument("--id", required=True, help="Unique federation ID (e.g., project name)")
    init_parser.add_argument("--out", type=str, default="federation_index.json", help="Path to write the new federation index")

    # add
    add_parser = federation_subparsers.add_parser("add", help="Add a bundle to the federation index")
    add_parser.add_argument("--index", required=True, help="Path to federation index")
    add_parser.add_argument("--repo", required=True, help="Unique repo ID for this bundle")
    add_parser.add_argument("--bundle", required=True, help="Path or URI to the bundle root")

    # inspect
    inspect_parser = federation_subparsers.add_parser("inspect", help="Inspect a federation index")
    inspect_parser.add_argument("--index", required=True, help="Path to federation index")

    # validate
    validate_parser = federation_subparsers.add_parser("validate", help="Validate a federation index")
    validate_parser.add_argument("--index", required=True, help="Path to federation index")

    # query
    query_parser = federation_subparsers.add_parser("query", help="Query across a federation index")
    query_parser.add_argument("--index", required=True, help="Path to federation index")
    query_parser.add_argument("-q", "--query", required=True, help="Query string")
    query_parser.add_argument("-k", type=int, default=10, help="Number of results to return")
    query_parser.add_argument("--repo", type=str, help="Filter by repository ID")
    query_parser.add_argument("--trace", action="store_true", help="Include diagnostic trace")


def handle_federation_command(args: argparse.Namespace) -> int:
    """Dispatches federation commands to their respective handlers."""
    from merger.lenskit.core.federation import init_federation
    from merger.lenskit.core.federation import add_bundle
    from merger.lenskit.core.federation import inspect_federation
    from merger.lenskit.core.federation import validate_federation

    if args.federation_command == "init":
        out_path = Path(args.out)
        try:
            init_federation(args.id, out_path)
            print(f"Successfully initialized federation index '{args.id}' at {out_path.as_posix()}")
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.federation_command == "add":
        index_path = Path(args.index)
        try:
            add_bundle(index_path, args.repo, args.bundle)
            print(f"Successfully added bundle '{args.repo}' to federation index at {index_path.as_posix()}")
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.federation_command == "inspect":
        index_path = Path(args.index)
        try:
            summary = inspect_federation(index_path)
            print(json.dumps(summary, indent=2))
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.federation_command == "validate":
        index_path = Path(args.index)
        try:
            is_valid = validate_federation(index_path)
            if is_valid:
                print(f"Federation index at {index_path.as_posix()} is valid.")
                return 0
            else:
                print(f"Federation index at {index_path.as_posix()} is invalid.", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.federation_command == "query":
        from merger.lenskit.retrieval.federation_query import execute_federated_query
        index_path = Path(args.index)
        filters = {}
        if args.repo:
            filters["repo"] = args.repo

        try:
            res = execute_federated_query(
                index_path,
                query_text=args.query,
                k=args.k,
                filters=filters,
                trace=args.trace
            )
            print(json.dumps(res, indent=2))
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    return 0
