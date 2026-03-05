import argparse
import sys
import json
import os
from pathlib import Path

from merger.lenskit.adapters.atlas import AtlasScanner, render_atlas_md

def run_atlas_scan(args: argparse.Namespace) -> int:
    try:
        raw_path = os.path.expanduser(args.path)
        norm_path = os.path.normpath(raw_path)

        if not os.path.isabs(norm_path) and not args.path.startswith(('/', '\\')):
            print("Error: Path must be absolute.", file=sys.stderr)
            return 1

        scan_root = Path(norm_path).resolve()

        exclude_globs = []
        if args.exclude:
            exclude_globs = [x.strip() for x in args.exclude.split(",") if x.strip()]

        if args.no_max_file_size:
            max_file_size = None
        else:
            max_file_size = 50 * 1024 * 1024 # default
            if args.max_file_size is not None:
                max_file_size = args.max_file_size * 1024 * 1024

        scanner = AtlasScanner(
            root=scan_root,
            max_depth=args.depth,
            max_entries=args.limit,
            exclude_globs=exclude_globs if exclude_globs else None,
            no_default_excludes=args.no_default_excludes,
            max_file_size=max_file_size
        )

        # Determine output directory
        # The prompt says "rlens atlas scan /" without specifying an output dir.
        # It's an exploration tool. We can print to stdout or write to a default dir.
        # "produce filesystem inventories while automatically skipping"
        # We can just write it to current directory or print the stats.
        out_json = Path(f"atlas_scan_{scan_root.name if scan_root.name else 'root'}.json")

        print(f"Scanning: {scan_root}")
        print("This may take a while depending on the filesystem...")

        result = scanner.scan()

        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        md_content = render_atlas_md(result)
        out_md = out_json.with_suffix(".md")
        with open(out_md, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"Done. Scan stats written to {out_json} and {out_md}")
        print(md_content)
        return 0
    except Exception as e:
        print(f"Error during scan: {e}", file=sys.stderr)
        return 1
