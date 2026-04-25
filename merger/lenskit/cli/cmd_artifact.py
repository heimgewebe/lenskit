import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from ..service.query_artifact_store import QueryArtifactStore


def _resolve_storage_dir(hub: Optional[str]) -> Optional[Path]:
    if hub:
        return Path(hub) / "merges" / ".rlens-service"
    # fall back to cwd-relative convention
    candidate = Path.cwd() / "merges" / ".rlens-service"
    if candidate.exists():
        return candidate
    return None


def run_artifact_lookup(args: argparse.Namespace) -> int:
    storage_dir = _resolve_storage_dir(getattr(args, "hub", None))
    if storage_dir is None:
        print(
            "Error: could not locate .rlens-service directory. "
            "Pass --hub <hub_path> explicitly.",
            file=sys.stderr,
        )
        return 1

    store = QueryArtifactStore(storage_dir)
    entry = store.get(args.id)

    if entry is None:
        result = {
            "status": "not_found",
            "id": args.id,
            "artifact": None,
            "warnings": [f"No artifact found with id={args.id!r}"],
        }
        print(json.dumps(result, indent=2))
        return 1

    result = {
        "status": "ok",
        "artifact_type": entry["artifact_type"],
        "id": entry["id"],
        "artifact": {
            "provenance": entry["provenance"],
            "created_at": entry["created_at"],
            "data": entry["data"],
        },
        "warnings": [],
    }
    print(json.dumps(result, indent=2))
    return 0
