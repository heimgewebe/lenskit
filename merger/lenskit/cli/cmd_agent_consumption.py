import argparse
import json
import sys
from pathlib import Path


def register_agent_consumption_commands(subparsers) -> None:
    parser = subparsers.add_parser(
        "agent-consumption", help="Agent consumption operations (Required Reading & Trace Validation)"
    )
    subparsers_ac = parser.add_subparsers(
        dest="agent_consumption_cmd", required=True, help="Agent consumption commands"
    )

    # required command
    req_parser = subparsers_ac.add_parser(
        "required", help="Generate a Required Reading Result"
    )
    req_parser.add_argument("--task-profile", required=True, help="Task profile (e.g., pr_review)")
    req_parser.add_argument("--available-roles", help="Comma-separated list of available roles")
    req_parser.add_argument("--available-roles-file", help="Path to JSON file containing available roles")
    req_parser.add_argument("--out", "--output", dest="out", help="Output path for the result JSON")

    # validate-trace command
    val_parser = subparsers_ac.add_parser(
        "validate-trace", help="Compare Required Reading Result with Answer Compliance"
    )
    val_parser.add_argument("--required-reading", required=True, help="Path to Required Reading Result JSON")
    val_parser.add_argument("--answer-compliance", required=True, help="Path to Answer Compliance JSON")
    val_parser.add_argument("--available-roles", help="Comma-separated list of available roles")
    val_parser.add_argument("--available-roles-file", help="Path to JSON file containing available roles")
    val_parser.add_argument("--strict", action="store_true", help="Treat 'warn' status as exit code 1")
    val_parser.add_argument("--out", "--output", dest="out", help="Output path for the trace JSON")


def _read_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(2)
    except OSError as e:
        print(f"Error: Could not read {path}: {e}", file=sys.stderr)
        sys.exit(2)

def _write_json_or_stdout(payload: dict, out: Path | None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True)
    if out is None:
        print(text)
    else:
        try:
            out.write_text(text + "\n", encoding="utf-8")
        except OSError as e:
            print(f"Error: Could not write to {out}: {e}", file=sys.stderr)
            sys.exit(2)

def _parse_roles_csv(value: str | None) -> set[str]:
    if not value:
        return set()
    return {r.strip() for r in value.split(",") if r.strip()}

def _load_roles_file(path: Path | None) -> set[str]:
    if not path:
        return set()
    data = _read_json(path)
    if isinstance(data, list):
        return {str(x) for x in data}
    if isinstance(data, dict):
        roles = data.get("available_roles", [])
        return {str(x) for x in roles}
    return set()

def _collect_available_roles(csv_value: str | None, roles_file: Path | None) -> set[str]:
    roles = _parse_roles_csv(csv_value)
    roles |= _load_roles_file(roles_file)
    return roles

def _exit_for_status(status: str, *, strict: bool = False) -> int:
    if status == "pass":
        return 0
    if status == "warn":
        return 1 if strict else 0
    if status in ("fail", "not_applicable"):
        return 1
    return 2


def run_agent_consumption_required(args: argparse.Namespace) -> int:
    from merger.lenskit.core.required_reading import (
        default_required_reading_protocol,
        resolve_required_reading,
    )

    roles_file_path = Path(args.available_roles_file) if args.available_roles_file else None
    available_roles = _collect_available_roles(args.available_roles, roles_file_path)

    protocol = default_required_reading_protocol()
    try:
        result = resolve_required_reading(
            protocol, available_roles, args.task_profile
        )
    except Exception as e:
        print(f"Error: unexpected failure: {e}", file=sys.stderr)
        return 2

    out_path = Path(args.out) if args.out else None
    _write_json_or_stdout(result, out_path)

    return _exit_for_status(result.get("status", "unknown"))


def run_agent_consumption_validate_trace(args: argparse.Namespace) -> int:
    from merger.lenskit.core.agent_consumption_validate import validate_agent_consumption

    rr_path = Path(args.required_reading)
    ac_path = Path(args.answer_compliance)

    rr_data = _read_json(rr_path)
    ac_data = _read_json(ac_path)

    roles_file_path = Path(args.available_roles_file) if args.available_roles_file else None
    available_roles = _collect_available_roles(args.available_roles, roles_file_path)

    # When no explicit roles are provided via CLI, pass None to fallback to validator defaults
    if not args.available_roles and not args.available_roles_file:
        available_roles_arg = None
    else:
        available_roles_arg = available_roles

    try:
        trace = validate_agent_consumption(
            rr_data, ac_data, available_roles=available_roles_arg
        )
    except Exception as e:
        print(f"Error: unexpected failure: {e}", file=sys.stderr)
        return 2

    out_path = Path(args.out) if args.out else None
    _write_json_or_stdout(trace, out_path)

    return _exit_for_status(trace.get("status", "unknown"), strict=args.strict)


def run_agent_consumption(args: argparse.Namespace) -> int:
    if args.agent_consumption_cmd == "required":
        return run_agent_consumption_required(args)
    elif args.agent_consumption_cmd == "validate-trace":
        return run_agent_consumption_validate_trace(args)
    return 2
