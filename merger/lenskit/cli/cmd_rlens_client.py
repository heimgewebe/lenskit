"""Read-only rLens HTTP CLI client. No new runtime dependencies."""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional, Tuple

DEFAULT_BASE_URL = "http://127.0.0.1:8787"
DEFAULT_TIMEOUT_SECONDS = 10


def _resolve_base_url(args: argparse.Namespace) -> str:
    base_url = getattr(args, "base_url", None)
    if base_url:
        base = base_url
    else:
        env = os.environ.get("RLENS_BASE_URL")
        base = env if env else DEFAULT_BASE_URL
    parsed = urllib.parse.urlparse(base)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Base URL must be an absolute http:// or https:// URL")
    return base.rstrip("/")


def _resolve_token(args: argparse.Namespace) -> Optional[str]:
    token = getattr(args, "token", None)
    if token:
        return token
    return os.environ.get("RLENS_TOKEN") or None


def _redact(text: str, token: Optional[str]) -> str:
    safe_text = text
    if token and token in text:
        safe_text = safe_text.replace(token, "[REDACTED]")
    safe_text = re.sub(r"Bearer\s+\S+", "Bearer [REDACTED]", safe_text, flags=re.IGNORECASE)
    return safe_text


def _exit_error(
    args: argparse.Namespace,
    error_kind: str,
    message: str,
    token: Optional[str] = None,
) -> int:
    safe_msg = _redact(message, token)
    if args.json:
        print(json.dumps({"status": "error", "error_kind": error_kind, "message": safe_msg}))
    else:
        print(f"Error ({error_kind}): {safe_msg}", file=sys.stderr)
    return 1


def _fetch_json(url: str, token: Optional[str], timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Any:
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
    return json.loads(body)


def _fetch_json_with_errors(
    args: argparse.Namespace, url: str, token: Optional[str]
) -> Tuple[Optional[Any], Optional[int]]:
    try:
        return _fetch_json(url, token), None
    except urllib.error.HTTPError as e:
        return None, _exit_error(args, "remote_error", f"HTTP {e.code}: {e.reason}", token)
    except urllib.error.URLError as e:
        return None, _exit_error(args, "remote_error", f"Connection error: {e.reason}", token)
    except json.JSONDecodeError as e:
        return None, _exit_error(args, "parse_error", f"Invalid JSON response: {e}", token)
    except (ValueError, TimeoutError, OSError) as e:
        return None, _exit_error(args, "remote_error", f"Request failed: {e}", token)


def _add_common_options(parser: argparse.ArgumentParser, suppress_defaults: bool = False) -> None:
    scalar_default = argparse.SUPPRESS if suppress_defaults else None
    flag_default = argparse.SUPPRESS if suppress_defaults else False
    parser.add_argument(
        "--base-url",
        dest="base_url",
        default=scalar_default,
        help="rLens service base URL (overrides RLENS_BASE_URL; default: http://127.0.0.1:8787)",
    )
    parser.add_argument(
        "--token",
        default=scalar_default,
        help="Bearer token (overrides RLENS_TOKEN env var)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=flag_default,
        help="Output raw JSON response",
    )


def register_rlens_client_commands(subparsers: argparse._SubParsersAction) -> None:
    client_parser = subparsers.add_parser(
        "rlens-client", help="Read-only rLens service client"
    )
    _add_common_options(client_parser)
    client_subparsers = client_parser.add_subparsers(
        dest="rlens_cmd", help="rLens client subcommands"
    )

    health_parser = client_subparsers.add_parser("health", help="Check service health")
    _add_common_options(health_parser, suppress_defaults=True)

    artifacts_parser = client_subparsers.add_parser("artifacts", help="List artifacts")
    _add_common_options(artifacts_parser, suppress_defaults=True)
    artifacts_parser.add_argument("--repo", default=None, help="Filter by repository name")

    latest_parser = client_subparsers.add_parser(
        "latest", help="Get latest artifact for a repository"
    )
    _add_common_options(latest_parser, suppress_defaults=True)
    latest_parser.add_argument("--repo", required=True, help="Repository name (required)")
    latest_parser.add_argument("--level", default="max", help="Level (default: max)")
    latest_parser.add_argument("--mode", default="gesamt", help="Mode (default: gesamt)")


def _cmd_health(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    try:
        base_url = _resolve_base_url(args)
    except ValueError as e:
        return _exit_error(args, "remote_error", f"Request failed: {e}", token)
    url = f"{base_url}/api/health"
    data, error_code = _fetch_json_with_errors(args, url, token)
    if error_code is not None:
        return error_code

    if args.json:
        print(json.dumps(data, indent=2))
        return 0

    print(f"status: {data.get('status', '?')}")
    if "version" in data:
        print(f"version: {data['version']}")
    if "server_version" in data:
        print(f"server_version: {data['server_version']}")
    if "hub" in data:
        print(f"hub: {data['hub']}")
    if "running_jobs" in data:
        print(f"running_jobs: {data['running_jobs']}")
    if "auth_enabled" in data:
        print(f"auth_enabled: {data['auth_enabled']}")
    return 0


def _cmd_artifacts(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    try:
        base_url = _resolve_base_url(args)
    except ValueError as e:
        return _exit_error(args, "remote_error", f"Request failed: {e}", token)
    url = f"{base_url}/api/artifacts"
    if args.repo:
        url = f"{url}?{urllib.parse.urlencode({'repo': args.repo})}"
    data, error_code = _fetch_json_with_errors(args, url, token)
    if error_code is not None:
        return error_code

    if args.json:
        print(json.dumps(data, indent=2))
        return 0

    items = data if isinstance(data, list) else []
    if not items:
        print("No artifacts found.")
        return 0
    for item in items:
        artifact_id = item.get("id", "?")
        repos = item.get("repos", item.get("repo", "?"))
        created_at = item.get("created_at", "?")
        paths = item.get("paths") or {}
        primary = None
        if isinstance(paths, dict):
            primary = paths.get("primary") or next(iter(paths.values()), None)
        line = f"  {artifact_id}  repos={repos}  created={created_at}"
        if primary:
            line += f"  path={primary}"
        print(line)
    return 0


def _cmd_latest(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    try:
        base_url = _resolve_base_url(args)
    except ValueError as e:
        return _exit_error(args, "remote_error", f"Request failed: {e}", token)
    params = urllib.parse.urlencode({"repo": args.repo, "level": args.level, "mode": args.mode})
    url = f"{base_url}/api/artifacts/latest?{params}"
    data, error_code = _fetch_json_with_errors(args, url, token)
    if error_code is not None:
        return error_code

    if args.json:
        print(json.dumps(data, indent=2))
        return 0

    print(f"id: {data.get('id', '?')}")
    print(f"repos: {data.get('repos', data.get('repo', '?'))}")
    print(f"created_at: {data.get('created_at', '?')}")
    paths = data.get("paths") or {}
    if isinstance(paths, dict):
        primary = paths.get("primary") or next(iter(paths.values()), None)
        if primary:
            print(f"path: {primary}")
    return 0


def run_rlens_client(args: argparse.Namespace) -> int:
    if not hasattr(args, "rlens_cmd") or args.rlens_cmd is None:
        print("Usage: lenskit rlens-client <subcommand>", file=sys.stderr)
        print("Subcommands: health, artifacts, latest", file=sys.stderr)
        return 2
    if args.rlens_cmd == "health":
        return _cmd_health(args)
    if args.rlens_cmd == "artifacts":
        return _cmd_artifacts(args)
    if args.rlens_cmd == "latest":
        return _cmd_latest(args)
    print(f"Unknown rlens-client subcommand: {args.rlens_cmd!r}", file=sys.stderr)
    return 2
