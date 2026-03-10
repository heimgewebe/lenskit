#!/usr/bin/env python3
"""
rLens Service Entry Point (Canonical)

Strictly acts as a launcher for the app defined in service/app.py.
Enforces configuration validity and security constraints before startup.
"""
import os
import sys
import argparse
import ipaddress
from pathlib import Path
import uvicorn

# Ensure correct path for imports if run as script
SCRIPT_DIR = Path(__file__).resolve().parent
# SCRIPT_DIR is lenskit/cli. Parent is lenskit. Parent of that is merger.
MERGER_ROOT = SCRIPT_DIR.parent.parent
if str(MERGER_ROOT) not in sys.path:
    sys.path.insert(0, str(MERGER_ROOT))

try:
    # Primary Canonical Import: relative to package
    from ..service.app import app, init_service
except ImportError:
    # Fallback for standalone execution (if sys.path is set correctly for top-level)
    try:
        from merger.lenskit.service.app import app, init_service
    except ImportError as e:
        print("[rlens] Fatal Error: Could not import 'lenskit.service.app'.", file=sys.stderr)
        print(f"[rlens] Debug info: sys.path={sys.path}", file=sys.stderr)
        print(f"[rlens] Original error: {e}", file=sys.stderr)
        sys.exit(1)


def _is_loopback_host(host: str) -> bool:
    h = (host or "").strip().lower()
    if h in ("127.0.0.1", "localhost", "::1"):
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except Exception:
        return False


def _get_port() -> int:
    raw = os.environ.get("RLENS_PORT", "")
    if not raw:
        return 8787
    try:
        return int(raw)
    except ValueError:
        print(f"[rlens] Warning: Invalid RLENS_PORT='{raw}', defaulting to 8787", file=sys.stderr)
        return 8787


def main():
    parser = argparse.ArgumentParser(prog="rlens")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Atlas command
    # NOTE: These Atlas CLI definitions are duplicated in cli/main.py.
    # Keep them in sync to prevent drift.
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
    atlas_scan_parser.add_argument("--mode", choices=["inventory", "topology", "content", "workspace"], default="inventory", help="The scan mode to execute")

    atlas_machines_parser = atlas_subparsers.add_parser("machines", help="List registered machines")
    atlas_roots_parser = atlas_subparsers.add_parser("roots", help="List registered roots")
    atlas_snapshots_parser = atlas_subparsers.add_parser("snapshots", help="List registered snapshots")

    # Architecture command
    arch_parser = subparsers.add_parser("architecture", help="Extract architectural views of a repository")
    arch_parser.add_argument("repo", nargs="?", default=".", help="The repository path to scan (default: current directory)")
    arch_parser.add_argument("--entrypoints", action="store_true", help="Extract python entrypoints as JSON")

    # Server mode (default when no subcommands provided)
    parser.add_argument("--host", default=os.environ.get("RLENS_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=_get_port())
    parser.add_argument("--hub", default=os.environ.get("RLENS_HUB"), help="Path to the Hub directory (Required)")
    parser.add_argument("--merges", default=os.environ.get("RLENS_MERGES"), help="Path to output directory")
    parser.add_argument("--token", default=os.environ.get("RLENS_TOKEN"), help="Auth token (Required for non-loopback)")
    parser.add_argument("--open", action="store_true", help="ignored (legacy)")

    args, unknown = parser.parse_known_args()

    if unknown:
        print(f"rlens: error: unrecognized arguments: {' '.join(unknown)}", file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(2)

    if args.command == "atlas":
        from . import cmd_atlas
        if args.atlas_cmd == "scan":
            sys.exit(cmd_atlas.run_atlas_scan(args))
        elif args.atlas_cmd == "machines":
            sys.exit(cmd_atlas.run_atlas_machines(args))
        elif args.atlas_cmd == "roots":
            sys.exit(cmd_atlas.run_atlas_roots(args))
        elif args.atlas_cmd == "snapshots":
            sys.exit(cmd_atlas.run_atlas_snapshots(args))
        else:
            parser.parse_args(["atlas", "--help"])
            sys.exit(0)

    if args.command == "architecture":
        from . import cmd_architecture
        sys.exit(cmd_architecture.run_architecture_cmd(args))

    # 1. Validate Hub Path
    if not args.hub:
         print("[rlens] Error: Missing hub path. Set --hub or RLENS_HUB.", file=sys.stderr)
         sys.exit(1)

    try:
        hub_path = Path(args.hub).expanduser().resolve()
    except Exception as e:
        print(f"[rlens] Error: Invalid hub path syntax: {e}", file=sys.stderr)
        sys.exit(1)

    if not hub_path.exists():
        print(f"[rlens] Error: Hub path does not exist: {hub_path}", file=sys.stderr)
        sys.exit(1)
    if not hub_path.is_dir():
        print(f"[rlens] Error: Hub path is not a directory: {hub_path}", file=sys.stderr)
        sys.exit(1)

    # 2. Validate/Create Merges Path
    merges_path = None
    if args.merges:
        try:
            merges_path = Path(args.merges).expanduser().resolve()
            merges_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[rlens] Error: Could not create merges directory '{args.merges}': {e}", file=sys.stderr)
            sys.exit(1)

    # 3. Security Checks

    # Check 1: Token Requirement for non-loopback
    token = args.token
    if not _is_loopback_host(args.host) and not token:
        print(f"[rlens] Security Error: Refusing to bind to non-loopback host '{args.host}' without a token.", file=sys.stderr)
        print("[rlens] Hint: Set --token or RLENS_TOKEN.", file=sys.stderr)
        sys.exit(1)

    if not _is_loopback_host(args.host):
        print("[rlens] Notice: Root browsing will be refused by policy (non-loopback host).", file=sys.stderr)

    # 4. Initialize Service
    init_service(
        hub_path=hub_path,
        token=token,
        host=args.host,
        merges_dir=merges_path
    )

    # 5. Startup Logging
    print(f"[rlens] serving on http://{args.host}:{args.port}", flush=True)
    print(f"[rlens] hub: {hub_path}", flush=True)
    print(f"[rlens] output: {merges_path if merges_path else '(default: hub/merges)'}", flush=True)
    print(f"[rlens] token: {'(set)' if token else '(not set)'}", flush=True)
    if args.open:
        print("[rlens] note: --open flag is deprecated and ignored.", flush=True)

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
    )

if __name__ == "__main__":
    main()
