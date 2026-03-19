import argparse
import sys
import json
import os
import socket
import datetime
import hashlib
import tempfile
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


def _resolve_snapshot_ref(ref: str, registry) -> str:
    if ":" in ref:
        machine_id, root_value = ref.split(":", 1)

        def normalize_path(p: str) -> str:
            # Conservative normalization for trivial differences (e.g. trailing slashes, /./).
            # Does not semantically reinterpret absolute vs. relative paths.
            import posixpath
            return posixpath.normpath(p)

        target_root_ids = []
        norm_root_value = normalize_path(root_value)

        for r in registry.list_roots():
            if r["machine_id"] == machine_id and normalize_path(r["root_value"]) == norm_root_value:
                target_root_ids.append(r["root_id"])

        if not target_root_ids:
            raise ValueError(f"No root found for machine '{machine_id}' and path '{root_value}'")

        if len(target_root_ids) > 1:
            raise ValueError(f"Ambiguous root reference: multiple roots match machine '{machine_id}' and path '{root_value}'")

        target_root_id = target_root_ids[0]

        snapshots = registry.list_complete_snapshots(root_id=target_root_id)
        if not snapshots:
            raise ValueError(f"No complete snapshots found for root '{target_root_id}'")

        # Ensure deterministic sort by created_at descending just in case DB defaults shift
        # missing created_at should sink to bottom or error, but they should all have it
        def safe_sort_key(s):
            return (s.get("created_at", ""), s.get("snapshot_id", ""))

        sorted_snaps = sorted(snapshots, key=safe_sort_key, reverse=True)
        return sorted_snaps[0]["snapshot_id"]
    return ref

def run_atlas_diff(args: argparse.Namespace) -> int:
    from merger.lenskit.atlas.diff import compute_snapshot_delta, compute_snapshot_comparison
    registry_path = Path("atlas/registry/atlas_registry.sqlite").resolve()
    try:
        with AtlasRegistry(registry_path) as registry:
            from_snap_id = _resolve_snapshot_ref(args.from_snapshot, registry)
            to_snap_id = _resolve_snapshot_ref(args.to_snapshot, registry)

            from_snap = registry.get_snapshot(from_snap_id)
            to_snap = registry.get_snapshot(to_snap_id)

            if not from_snap:
                raise ValueError(f"Snapshot not found: {from_snap_id}")
            if not to_snap:
                raise ValueError(f"Snapshot not found: {to_snap_id}")

            if from_snap["machine_id"] == to_snap["machine_id"] and from_snap["root_id"] == to_snap["root_id"]:
                delta = compute_snapshot_delta(registry, from_snap_id, to_snap_id)
                print(f"Delta: {delta['delta_id']} ({delta['from_snapshot_id']} -> {delta['to_snapshot_id']})")
                print(f"Mode: same-root-delta")
            else:
                delta = compute_snapshot_comparison(registry, from_snap_id, to_snap_id)
                print(f"Comparison: {delta['comparison_id']}")
                print(f"Mode: cross-root-comparison")
                from_desc = f"{delta['from_machine_id']}:{delta['from_root_value']} ({delta['from_snapshot_id']})"
                to_desc = f"{delta['to_machine_id']}:{delta['to_root_value']} ({delta['to_snapshot_id']})"
                print(f"From: {from_desc}")
                print(f"To:   {to_desc}")

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
    if args.analyze_command == "orphans":
        return _run_analyze_orphans(args.snapshot_id)
    if args.analyze_command == "disk":
        return _run_analyze_disk(args.snapshot_id)
    return 1

def _run_analyze_orphans(snapshot_id: str) -> int:
    from merger.lenskit.atlas.registry import AtlasRegistry
    from merger.lenskit.atlas.paths import resolve_atlas_base_dir, resolve_artifact_ref, resolve_snapshot_dir

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

    root_path = Path(root['root_value'])
    if not root_path.exists() or not root_path.is_dir():
        print(f"Error: Root path '{root_path}' does not exist or is not a directory.", file=sys.stderr)
        return 1

    # Load files from the snapshot
    snapshot_files = set()
    with inventory_path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                rel_path = entry.get('rel_path')
                if rel_path:
                    # Treat snapshot files directly as canonical string representation
                    snapshot_files.add(rel_path)
            except json.JSONDecodeError:
                continue

    # Load live files from the root
    live_files = set()
    for root_dir, dirs, files in os.walk(root_path):
        rel_root = Path(root_dir).relative_to(root_path)
        for name in files:
            rel_file_path = rel_root / name
            live_files.add(rel_file_path.as_posix())

    # Orphans are files in the live system that are not in the snapshot
    orphans = live_files - snapshot_files
    # Dead files are files in the snapshot that are not in the live system
    dead_files = snapshot_files - live_files

    report = {
        "snapshot_id": snapshot_id,
        "analyzed_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "root_path": str(root_path),
        "total_live_files": len(live_files),
        "total_snapshot_files": len(snapshot_files),
        "orphan_count": len(orphans),
        "dead_file_count": len(dead_files),
        "orphans": sorted(list(orphans)),
        "dead_files": sorted(list(dead_files))
    }

    # Write to orphans.json in the snapshot directory
    snapshot_dir = resolve_snapshot_dir(base_dir, snapshot['machine_id'], snapshot['root_id'], snapshot_id)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    out_path = snapshot_dir / "orphans.json"

    fd, temp_path = tempfile.mkstemp(dir=str(snapshot_dir), prefix=".tmp_orphans.json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, str(out_path))
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

    try:
        rel_out = out_path.relative_to(base_dir)
        ref = rel_out.as_posix()
    except ValueError:
        ref = out_path.as_posix()

    # Register in SQLite
    with AtlasRegistry(registry_path) as registry:
        registry.update_snapshot_artifacts(snapshot_id, {"orphans": ref})

    print(json.dumps(report, indent=2))
    return 0


def _run_analyze_duplicates(snapshot_id: str) -> int:
    from merger.lenskit.atlas.registry import AtlasRegistry
    from merger.lenskit.atlas.paths import resolve_atlas_base_dir, resolve_artifact_ref, resolve_snapshot_dir

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

            rel_path = entry.get('rel_path')
            size = entry.get('size_bytes')

            # Defensive guard: skip invalid entries
            if not rel_path or not isinstance(size, int):
                continue

            if size not in size_groups:
                size_groups[size] = []

            # Store only what is needed
            min_entry = {
                "rel_path": rel_path,
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
                try:
                    # Securely resolve path and ensure it doesn't escape the root
                    f_path = (root_path / entry['rel_path']).resolve()
                    if f_path.is_file() and f_path.is_relative_to(root_path.resolve()):
                        sha256 = hashlib.sha256()
                        with f_path.open('rb') as hf:
                            for chunk in iter(lambda: hf.read(8192), b""):
                                sha256.update(chunk)
                        grouping_key = f"sha256:{sha256.hexdigest()}"
                        is_verified = True
                except (OSError, ValueError, RuntimeError):
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

    # Output to snapshot directory and update registry
    snapshot_dir = resolve_snapshot_dir(base_dir, snapshot['machine_id'], snapshot['root_id'], snapshot_id)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    duplicates_path = snapshot_dir / "duplicates.json"

    # Write atomically
    fd, temp_path = tempfile.mkstemp(dir=str(snapshot_dir), prefix=".tmp_duplicates.json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, str(duplicates_path))
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

    try:
        dup_ref = duplicates_path.relative_to(base_dir).as_posix()
    except ValueError:
        dup_ref = duplicates_path.as_posix()

    registry_path = Path("atlas/registry/atlas_registry.sqlite").resolve()
    with AtlasRegistry(registry_path) as registry:
        registry.update_snapshot_artifacts(snapshot_id, {"duplicates": dup_ref})

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

def _run_analyze_disk(snapshot_id: str) -> int:
    from merger.lenskit.atlas.registry import AtlasRegistry
    from merger.lenskit.atlas.paths import resolve_atlas_base_dir, resolve_artifact_ref, resolve_snapshot_dir

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
        print(f"Error: Snapshot '{snapshot_id}' has no inventory_ref. Cannot analyze disk.", file=sys.stderr)
        return 1

    base_dir = resolve_atlas_base_dir(registry_path)
    inv_path = resolve_artifact_ref(base_dir, snapshot['inventory_ref'])
    if not inv_path.exists():
        print(f"Error: Inventory file '{inv_path}' not found.", file=sys.stderr)
        return 1

    dirs_path = None
    if snapshot.get('dirs_ref'):
        d_path = resolve_artifact_ref(base_dir, snapshot['dirs_ref'])
        if d_path.exists():
            dirs_path = d_path

    largest_files = []
    oldest_files = []
    total_files = 0
    total_bytes = 0

    with open(inv_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Skip symlinks for strict file size counting if desired,
            # but usually they are 0 or small. We keep them but they won't make largest files.

            size = item.get("size_bytes", 0)
            if not isinstance(size, int) or size < 0:
                size = 0
            mtime = item.get("mtime")
            rel_path = item.get("rel_path", "")

            total_files += 1
            total_bytes += size

            largest_files.append({"path": rel_path, "size": size})
            if mtime:
                oldest_files.append({"path": rel_path, "mtime": mtime})

            # Keep only top N to save memory
            if len(largest_files) > 1000:
                largest_files.sort(key=lambda x: x["size"], reverse=True)
                largest_files = largest_files[:100]

            if len(oldest_files) > 1000:
                oldest_files.sort(key=lambda x: x["mtime"])
                oldest_files = oldest_files[:100]

    # Final sort
    largest_files.sort(key=lambda x: x["size"], reverse=True)
    largest_files = largest_files[:50]

    oldest_files.sort(key=lambda x: x["mtime"])
    oldest_files = oldest_files[:50]

    largest_dirs = []
    most_populated_dirs = []

    if dirs_path:
        with open(dirs_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue

                size = item.get("subtree_total_bytes", item.get("recursive_bytes", 0))
                if not isinstance(size, int) or size < 0:
                    size = 0
                count = item.get("subtree_file_count", item.get("n_files", item.get("kept_file_count", 0)))
                if not isinstance(count, int) or count < 0:
                    count = 0
                rel_path = item.get("rel_path", "")

                largest_dirs.append({"path": rel_path, "size": size})
                most_populated_dirs.append({"path": rel_path, "count": count})

                if len(largest_dirs) > 1000:
                    largest_dirs.sort(key=lambda x: x["size"], reverse=True)
                    largest_dirs = largest_dirs[:100]
                if len(most_populated_dirs) > 1000:
                    most_populated_dirs.sort(key=lambda x: x["count"], reverse=True)
                    most_populated_dirs = most_populated_dirs[:100]

        largest_dirs.sort(key=lambda x: x["size"], reverse=True)
        largest_dirs = largest_dirs[:50]

        most_populated_dirs.sort(key=lambda x: x["count"], reverse=True)
        most_populated_dirs = most_populated_dirs[:50]

    report = {
        "snapshot_id": snapshot_id,
        "analyzed_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "largest_files": largest_files,
        "oldest_files": oldest_files,
        "largest_dirs": largest_dirs,
        "most_populated_dirs": most_populated_dirs
    }

    # Output to snapshot directory and update registry
    snapshot_dir = resolve_snapshot_dir(base_dir, snapshot['machine_id'], snapshot['root_id'], snapshot_id)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    disk_path = snapshot_dir / "disk.json"

    fd, temp_path = tempfile.mkstemp(dir=str(snapshot_dir), prefix=".tmp_disk.json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, str(disk_path))
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

    try:
        rel_disk = disk_path.relative_to(base_dir).as_posix()
    except ValueError:
        rel_disk = disk_path.as_posix()
    with AtlasRegistry(registry_path) as registry:
        registry.update_snapshot_artifacts(snapshot_id, {"disk": rel_disk})

    print(json.dumps(report, indent=2))

    return 0
