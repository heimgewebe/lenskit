import argparse
import sys
import json
import os
import socket
import datetime
import hashlib
from pathlib import Path
from typing import Dict, List, Any

from merger.lenskit.adapters.atlas import AtlasScanner, render_atlas_md
from merger.lenskit.atlas.planner import plan_atlas_outputs, write_mode_outputs
from merger.lenskit.atlas.registry import AtlasRegistry
from merger.lenskit.atlas.paths import resolve_atlas_base_dir, resolve_snapshot_dir, resolve_artifact_ref

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

def run_atlas_diff(args: argparse.Namespace) -> int:
    from merger.lenskit.atlas.diff import compute_snapshot_delta
    registry_path = Path("atlas/registry/atlas_registry.sqlite").resolve()
    try:
        with AtlasRegistry(registry_path) as registry:
            delta = compute_snapshot_delta(registry, args.from_snapshot, args.to_snapshot)
        print(f"Delta: {delta['delta_id']} ({delta['from_snapshot_id']} -> {delta['to_snapshot_id']})")
        print(f"Summary: {json.dumps(delta['summary'], indent=2)}")
        print(f"\nNew files: {len(delta['new_files'])}")
        for f in delta['new_files'][:10]:
            print(f"  + {f}")
        if len(delta['new_files']) > 10:
            print(f"  ... and {len(delta['new_files']) - 10} more")

        print(f"\nRemoved files: {len(delta['removed_files'])}")
        for f in delta['removed_files'][:10]:
            print(f"  - {f}")
        if len(delta['removed_files']) > 10:
            print(f"  ... and {len(delta['removed_files']) - 10} more")

        print(f"\nChanged files: {len(delta['changed_files'])}")
        for f in delta['changed_files'][:10]:
            print(f"  ~ {f}")
        if len(delta['changed_files']) > 10:
            print(f"  ... and {len(delta['changed_files']) - 10} more")

        return 0
    except Exception as e:
        print(f"Error computing diff: {e}", file=sys.stderr)
        return 1

def run_atlas_search(args: argparse.Namespace) -> int:
    from merger.lenskit.atlas.search import AtlasSearch
    registry_path = Path("atlas/registry/atlas_registry.sqlite").resolve()
    try:
        searcher = AtlasSearch(registry_path)

        results = searcher.search(
            query=args.query,
            machine_id=args.machine_id,
            root_id=args.root_id,
            snapshot_id=args.snapshot_id,
            path_pattern=args.path,
            name_pattern=args.name,
            ext=args.ext,
            min_size=args.min_size,
            max_size=args.max_size,
            date_after=args.date_after,
            date_before=args.date_before,
            content_query=getattr(args, 'content_query', None)
        )

        # Print results
        for r in results:
            print(f"[{r.get('machine_id')}][{r.get('root_id')}] {r.get('rel_path')} ({r.get('size_bytes')} bytes) - {r.get('mtime')}")
            if 'content_snippet' in r:
                print(f"  Snippet: {r['content_snippet']}")

        print(f"\nTotal results: {len(results)}")

        return 0
    except Exception as e:
        print(f"Error executing search: {e}", file=sys.stderr)
        return 1

def run_atlas_analyze(args: argparse.Namespace) -> int:
    if args.analyze_command == "duplicates":
        return _run_analyze_duplicates(args.snapshot_id)
    return 1

def _run_analyze_duplicates(snapshot_id: str) -> int:
    from merger.lenskit.atlas.registry import AtlasRegistry
    from merger.lenskit.atlas.paths import resolve_atlas_base_dir, resolve_artifact_ref

    registry_path = Path("atlas/registry/atlas_registry.sqlite").resolve()
    with AtlasRegistry(registry_path) as registry:
        snapshot = registry.get_snapshot(snapshot_id)
        if not snapshot:
            print(f"Error: Snapshot '{snapshot_id}' not found.", file=sys.stderr)
            return 1

        if snapshot['status'] != 'complete':
            print(f"Error: Snapshot '{snapshot_id}' is not complete.", file=sys.stderr)
            return 1

        root = registry.get_root(snapshot['root_id'])
        if not root:
            print(f"Error: Root '{snapshot['root_id']}' not found.", file=sys.stderr)
            return 1

    if not snapshot.get('inventory_ref'):
        print(f"Error: Snapshot '{snapshot_id}' has no inventory_ref.", file=sys.stderr)
        return 1

    base_dir = resolve_atlas_base_dir(registry_path)
    inventory_path = resolve_artifact_ref(base_dir, snapshot['inventory_ref'])

    if not inventory_path or not inventory_path.exists():
        print(f"Error: Inventory file not found at {inventory_path}", file=sys.stderr)
        return 1

    # Phase 1: Group by size using minimal entries
    size_groups: Dict[int, List[Dict[str, Any]]] = {}
    with inventory_path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get('is_symlink') or entry.get('size_bytes', 0) == 0:
                continue

            size = entry['size_bytes']
            if size not in size_groups:
                size_groups[size] = []

            # Store only what is needed
            min_entry = {
                "rel_path": entry.get('rel_path'),
                "size_bytes": size,
                "quick_hash": entry.get('quick_hash'),
                "checksum": entry.get('checksum')
            }
            size_groups[size].append(min_entry)

    # Phase 2: Compute full hash for potential duplicates
    root_path = Path(root['root_value'])
    duplicates_list = []

    for size, entries in size_groups.items():
        if len(entries) < 2:
            continue

        hash_groups: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            # Determine grouping hash and its verification status
            grouping_key = None
            is_verified = False

            # 1. Use existing checksum if present
            if entry.get('checksum'):
                grouping_key = entry['checksum']
                is_verified = True
            # 2. Otherwise use existing quick_hash (heuristic)
            elif entry.get('quick_hash'):
                grouping_key = f"quick:{entry['quick_hash']}"
                is_verified = False
            # 3. Otherwise compute live SHA256 (confirmed)
            else:
                f_path = root_path / entry['rel_path']
                if f_path.is_file():
                    try:
                        sha256 = hashlib.sha256()
                        with f_path.open('rb') as hf:
                            for chunk in iter(lambda: hf.read(8192), b""):
                                sha256.update(chunk)
                        grouping_key = f"sha256:{sha256.hexdigest()}"
                        is_verified = True
                    except OSError:
                        pass

            if grouping_key:
                if grouping_key not in hash_groups:
                    hash_groups[grouping_key] = {"verified": is_verified, "members": []}
                # Demote verification status if a group mixes confirmed and heuristic hashes
                # (Though with our prefixing, a "quick:" will never match a "sha256:")
                if not is_verified:
                    hash_groups[grouping_key]["verified"] = False
                hash_groups[grouping_key]["members"].append(entry)

        # Phase 3: Collect duplicates
        for h, grp_data in hash_groups.items():
            grp = grp_data["members"]
            is_verified = grp_data["verified"]
            if len(grp) > 1:
                dup_id = f"dup_{hashlib.sha256(h.encode('utf-8')).hexdigest()[:12]}"

                dup_entry = {
                    "duplicate_id": dup_id,
                    "checksum_verified": is_verified,
                    "size_bytes": size,
                    "members": [
                        {
                            "machine_id": snapshot['machine_id'],
                            "root_id": snapshot['root_id'],
                            "rel_path": e['rel_path']
                        } for e in grp
                    ]
                }

                if is_verified:
                    dup_entry["checksum"] = h
                else:
                    dup_entry["quick_hash"] = h.replace("quick:", "", 1) if h.startswith("quick:") else h

                duplicates_list.append(dup_entry)

    duplicates_list.sort(key=lambda x: x['size_bytes'], reverse=True)

    report = {
        "snapshot_id": snapshot_id,
        "analyzed_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "duplicate_groups_count": len(duplicates_list),
        "total_wasted_bytes": sum(g['size_bytes'] * (len(g['members']) - 1) for g in duplicates_list),
        "duplicates": duplicates_list
    }

    # Output to stdout. Future improvement: write to duplicates_ref in DB
    print(json.dumps(report, indent=2))
    return 0

def run_atlas_history(args: argparse.Namespace) -> int:
    registry_path = Path("atlas/registry/atlas_registry.sqlite").resolve()
    atlas_base = resolve_atlas_base_dir(registry_path)
    try:
        with AtlasRegistry(registry_path) as registry:
            snapshots = registry.list_snapshots()

        snapshots = [s for s in snapshots if s["status"] == "complete" and s["machine_id"] == args.machine_id and s["root_id"] == args.root_id]

        if not snapshots:
            print(f"No complete snapshots found for machine '{args.machine_id}' and root '{args.root_id}'", file=sys.stderr)
            return 1

        print(f"History for '{args.rel_path}' on machine '{args.machine_id}', root '{args.root_id}':")
        # Reverse to get chronological order (oldest first) since list_snapshots returns DESC
        snapshots.reverse()

        last_seen = None
        for snap in snapshots:
            inv_ref = snap.get("inventory_ref")
            if not inv_ref:
                print(f"Warning: Snapshot '{snap['snapshot_id']}' has no inventory_ref. Skipping.", file=sys.stderr)
                continue
            inv_path = resolve_artifact_ref(atlas_base, inv_ref)
            if not inv_path.exists():
                print(f"Warning: Inventory file '{inv_path}' for snapshot '{snap['snapshot_id']}' not found. Skipping.", file=sys.stderr)
                continue

            file_data = None
            with open(inv_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    item = json.loads(line)
                    if item.get("rel_path") == args.rel_path:
                        file_data = item
                        break

            if file_data:
                current_state = f"size={file_data.get('size_bytes')}, mtime={file_data.get('mtime')}, symlink={file_data.get('is_symlink')}"
                if last_seen is None:
                    print(f"[{snap['created_at']}] {snap['snapshot_id']}: CREATED ({current_state})")
                elif last_seen != current_state:
                    print(f"[{snap['created_at']}] {snap['snapshot_id']}: MODIFIED ({current_state})")
                else:
                    print(f"[{snap['created_at']}] {snap['snapshot_id']}: UNCHANGED")
                last_seen = current_state
            else:
                if last_seen is not None:
                    print(f"[{snap['created_at']}] {snap['snapshot_id']}: DELETED")
                last_seen = None

        return 0
    except Exception as e:
        print(f"Error computing history: {e}", file=sys.stderr)
        return 1


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
        atlas_base = resolve_atlas_base_dir(registry_path)
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

        # Determine effective scan config hash BEFORE instantiating Scanner
        # so we can pass it down for proper cache invalidation.
        temp_scanner = AtlasScanner(root=scan_root, exclude_globs=exclude_globs if exclude_globs else None, no_default_excludes=args.no_default_excludes, max_file_size=max_file_size)
        eff_excludes = temp_scanner.exclude_globs
        eff_ex_str = ",".join(sorted(eff_excludes))
        config_str = f"mode={args.mode}|depth={args.depth}|limit={args.limit}|ex={eff_ex_str}|maxfs={max_file_size}"
        short_hash = hashlib.md5(config_str.encode("utf-8"), usedforsecurity=False).hexdigest()[:8] # nosec B303

        incremental_inventory = None
        incremental_dirs_inventory = None
        previous_scan_config_hash = None
        if args.incremental:
            snapshots = registry.list_snapshots()
            # Find the latest complete snapshot for this root
            latest_snap = next((s for s in snapshots if s["status"] == "complete" and s["machine_id"] == machine_id and s["root_id"] == root_id), None)
            if latest_snap:
                previous_scan_config_hash = latest_snap.get("scan_config_hash")
                if latest_snap.get("inventory_ref"):
                    inv_path = resolve_artifact_ref(atlas_base, latest_snap["inventory_ref"])
                    if inv_path.exists():
                        incremental_inventory = inv_path
                    else:
                        print(f"Warning: Incremental requested, but previous inventory file not found: {inv_path}", file=sys.stderr)
                if latest_snap.get("dirs_ref"):
                    dirs_path = resolve_artifact_ref(atlas_base, latest_snap["dirs_ref"])
                    if dirs_path.exists():
                        incremental_dirs_inventory = dirs_path
                    else:
                        print(f"Warning: Incremental requested, but previous dirs file not found: {dirs_path}", file=sys.stderr)
            else:
                print("Warning: Incremental requested, but no complete prior snapshot found for this root.", file=sys.stderr)

        scanner = AtlasScanner(
            root=scan_root,
            max_depth=args.depth,
            max_entries=args.limit,
            exclude_globs=exclude_globs if exclude_globs else None,
            no_default_excludes=args.no_default_excludes,
            max_file_size=max_file_size,
            snapshot_id=None, # Will inject directly later once hash is computed
            enable_content_stats=(args.mode == "content"),
            incremental_inventory=incremental_inventory,
            incremental_dirs_inventory=incremental_dirs_inventory,
            previous_scan_config_hash=previous_scan_config_hash,
            current_scan_config_hash=short_hash
        )


        snapshot_id = f"snap_{machine_id}__{root_id}__{timestamp}__{short_hash}"
        scanner.snapshot_id = snapshot_id

        registry.create_snapshot(snapshot_id, machine_id, root_id, short_hash, "running")

        try:
            # Set up correct directory structure based on Atlas Blaupause
            snapshot_dir = resolve_snapshot_dir(atlas_base, machine_id, root_id, snapshot_id)
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            planned_outputs = plan_atlas_outputs(args.mode, scan_id=None)

            # Map the planned outputs to the full paths, but let planner just return file names
            planned_paths = {k: snapshot_dir / v for k, v in planned_outputs.items()}

            # For the registry, we'll store the relative path from the canonical atlas base
            # so the SQLite index references the files correctly regardless of CWD.
            registry_artifacts = {}
            for k, v in planned_paths.items():
                try:
                    registry_artifacts[k] = str(v.relative_to(atlas_base))
                except ValueError:
                    # Fallback to absolute if it's not under atlas_base
                    registry_artifacts[k] = str(v)

            print(f"Scanning: {scan_root} (Mode: {args.mode})")
            print("This may take a while depending on the filesystem...")

            inventory_path = planned_paths.get("inventory")
            dirs_path = planned_paths.get("dirs")

            result = scanner.scan(inventory_file=inventory_path, dirs_inventory_file=dirs_path)

            # Write core stats JSON (always)
            out_json = snapshot_dir / "snapshot_meta.json"
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)

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
