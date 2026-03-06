import argparse
import sys
import json
import uuid
from pathlib import Path
from ..architecture.entrypoints import generate_entrypoints_document
from ..architecture.import_graph import generate_import_graph_document

def run_architecture_cmd(args: argparse.Namespace) -> int:
    """
    Executes the architecture CLI command.
    """
    if args.entrypoints:
        repo_root = Path(args.repo).expanduser().resolve()

        if not repo_root.is_dir():
            print(f"Error: Path '{args.repo}' is not a directory.", file=sys.stderr)
            return 1

        # Generating placeholders for run_id and canonical_dump_index_sha256
        # In a real pipeline, these would come from the broader run context
        run_id = f"cmd_run_{uuid.uuid4().hex[:8]}"
        # Mock SHA256 since CLI standalone might not have a dump index context yet
        canonical_sha256 = "0" * 64

        doc = generate_entrypoints_document(repo_root, run_id, canonical_sha256)

        # Determine output formatting
        # For this roadmap step, --entrypoints generates JSON output
        print(json.dumps(doc, indent=2))
        return 0
    elif args.import_graph:
        repo_root = Path(args.repo).expanduser().resolve()

        if not repo_root.is_dir():
            print(f"Error: Path '{args.repo}' is not a directory.", file=sys.stderr)
            return 1

        run_id = f"cmd_run_{uuid.uuid4().hex[:8]}"
        canonical_sha256 = "0" * 64

        doc = generate_import_graph_document(repo_root, run_id, canonical_sha256)

        print(json.dumps(doc, indent=2))
        return 0
    elif getattr(args, "graph_index", False):
        if not getattr(args, "graph_in", None) or not getattr(args, "entrypoints_in", None):
            print("Error: --graph-index requires --graph-in and --entrypoints-in", file=sys.stderr)
            return 1

        from ..architecture.graph_index import compile_graph_index
        idx = compile_graph_index(Path(args.graph_in), Path(args.entrypoints_in))
        print(json.dumps(idx, indent=2))
        return 0
    else:
        print("Error: You must specify an architecture view to extract (e.g., --entrypoints, --import-graph).", file=sys.stderr)
        return 1
