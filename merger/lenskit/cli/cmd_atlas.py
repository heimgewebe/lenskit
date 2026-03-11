import argparse
import sys
import json
import os
import socket
import datetime
import hashlib
from pathlib import Path

from merger.lenskit.adapters.atlas import AtlasScanner, render_atlas_md
from merger.lenskit.atlas.planner import plan_atlas_outputs, write_mode_outputs
from merger.lenskit.atlas.registry import AtlasRegistry

def run_atlas_machines(args: argparse.Namespace) -> int:
    registry_path = Path("atlas/registry/atlas_registry.sqlite").resolve()
    with AtlasRegistry(registry_path) as registry:
        machines = registry.list_machines()
    print(json.dumps(machines, indent=2))
    return 0

def run_atlas_roots(args: argparse.Namespace) -> int:
    registry_path = Path("atlas/registry/atlas_registry.sqlite").resolve()
    with AtlasRegistry(registry_path) as registry:
        roots = registry.list_roots()
    print(json.dumps(roots, indent=2))
    return 0

def run_atlas_snapshots(args: argparse.Namespace) -> int:
    registry_path = Path("atlas/registry/atlas_registry.sqlite").resolve()
    with AtlasRegistry(registry_path) as registry:
        snapshots = registry.list_snapshots()
    print(json.dumps(snapshots, indent=2))
    return 0

def run_atlas_scan(args: argparse.Namespace) -> int:
    try:
        raw_path = os.path.expanduser(args.path)
        norm_path = os.path.normpath(raw_path)

        if not os.path.isabs(norm_path) and not args.path.startswith(('/', '\\')):
            print("Error: Path must be absolute.", file=sys.stderr)
            return 1

        # Avoid .resolve() to maintain semantic parity with backend app.py
        # (which drops resolve() to dodge CodeQL path injection sinks on user input)
        scan_root = Path(norm_path)

        exclude_globs = []
        if args.exclude:
            exclude_globs = [x.strip() for x in args.exclude.split(",") if x.strip()]

        if args.no_max_file_size:
            max_file_size = None
        else:
            max_file_size = 50 * 1024 * 1024 # default
            if args.max_file_size is not None:
                max_file_size = args.max_file_size * 1024 * 1024

        # Setup Registry
        registry_path = Path("atlas/registry/atlas_registry.sqlite").resolve()
        registry = AtlasRegistry(registry_path)

        # Register Machine
        hostname = socket.gethostname()
        machine_id = os.environ.get("ATLAS_MACHINE_ID", hostname)
        registry.register_machine(machine_id, hostname)

        # Register Root
        # Ensure we always use absolute path as canonical value
        root_value = str(scan_root)
        root_hash = hashlib.md5(root_value.encode("utf-8"), usedforsecurity=False).hexdigest()[:8] # nosec B303
        root_id = f"{machine_id}__{scan_root.name if scan_root.name else 'root'}_{root_hash}"
        registry.register_root(root_id, machine_id, "abs_path", root_value, label=scan_root.name)

        # Configure Snapshot Identity
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        scanner = AtlasScanner(
            root=scan_root,
            max_depth=args.depth,
            max_entries=args.limit,
            exclude_globs=exclude_globs if exclude_globs else None,
            no_default_excludes=args.no_default_excludes,
            max_file_size=max_file_size,
            snapshot_id=None, # Will inject directly later once hash is computed
            enable_content_stats=(args.mode == "content")
        )

        # Determine effective scan config hash based on Scanner state
        eff_excludes = scanner.exclude_globs
        eff_ex_str = ",".join(sorted(eff_excludes))
        config_str = f"mode={args.mode}|depth={args.depth}|limit={args.limit}|ex={eff_ex_str}|maxfs={max_file_size}"
        short_hash = hashlib.md5(config_str.encode("utf-8"), usedforsecurity=False).hexdigest()[:8] # nosec B303

        snapshot_id = f"snap_{machine_id}__{root_id}__{timestamp}__{short_hash}"
        scanner.snapshot_id = snapshot_id

        registry.create_snapshot(snapshot_id, machine_id, root_id, short_hash, "running")

        try:
            # Set up correct directory structure based on Atlas Blaupause
            snapshot_dir = Path("atlas") / "machines" / machine_id / "roots" / root_id / "snapshots" / snapshot_id
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            planned_outputs = plan_atlas_outputs(args.mode, scan_id=None)

            # Map the planned outputs to the full paths, but let planner just return file names
            planned_paths = {k: snapshot_dir / v for k, v in planned_outputs.items()}

            # For the registry, we'll store the relative path from the CWD
            # so the SQLite index references the files correctly.
            registry_artifacts = {k: str(v) for k, v in planned_paths.items()}

            print(f"Scanning: {scan_root} (Mode: {args.mode})")
            print("This may take a while depending on the filesystem...")

            inventory_path = planned_paths.get("inventory")
            dirs_path = planned_paths.get("dirs")

            result = scanner.scan(inventory_file=inventory_path, dirs_inventory_file=dirs_path)

            # Write core stats JSON (always)
            out_json = snapshot_dir / "snapshot_meta.json"
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)

            registry_artifacts["snapshot_meta"] = str(out_json)

            # Render summary MD
            md_content = render_atlas_md(result)
            out_md = planned_paths["summary"]
            with open(out_md, "w", encoding="utf-8") as f:
                f.write(md_content)

            # Additional structural outputs
            write_mode_outputs(planned_outputs, result, snapshot_dir)

            # Write artifacts before updating the registry status to complete (Memory constraint)
            registry.update_snapshot_artifacts(snapshot_id, registry_artifacts)
            registry.update_snapshot_status(snapshot_id, "complete")

            print(f"Done. Outputs generated for mode '{args.mode}':")
            for k, v in registry_artifacts.items():
                print(f" - {k}: {v}")

            print(f"\nSummary preview:\n{md_content}")
            return 0
        except Exception:
            registry.update_snapshot_status(snapshot_id, "failed")
            raise

    except Exception as e:
        print(f"Error during scan: {e}", file=sys.stderr)
        return 1
    finally:
        if 'registry' in locals() and registry:
            registry.close()
