import sys
import json
import hashlib
from pathlib import Path
from typing import Optional

def _compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return "ERROR"

def check_stale_index(index_path: Path) -> None:
    """
    Non-fatally checks if the given SQLite index is stale by comparing the
    'canonical_dump_sha256' in the adjacent derived manifest with the actual
    hash of the adjacent dump manifest. Warns via sys.stderr on mismatch.
    """
    try:
        # Expected naming: <base>.chunk_index.index.sqlite
        # Derived manifest: <base>.derived_index.json
        # Dump manifest: <base>.dump_index.json
        if not index_path.name.endswith(".index.sqlite"):
            return

        base_name = index_path.name.replace(".chunk_index.index.sqlite", "").replace(".index.sqlite", "")
        dir_path = index_path.parent

        derived_path = dir_path / f"{base_name}.derived_index.json"
        dump_path = dir_path / f"{base_name}.dump_index.json"

        if not derived_path.exists() or not dump_path.exists():
            return

        derived_data = json.loads(derived_path.read_text(encoding="utf-8"))
        recorded_sha = derived_data.get("canonical_dump_sha256")
        if not recorded_sha:
            return

        actual_sha = _compute_file_sha256(dump_path)

        if recorded_sha != actual_sha:
            print(
                f"Warning: The index '{index_path.name}' appears to be stale. "
                f"The canonical dump manifest has changed.",
                file=sys.stderr
            )
    except Exception:
        # Fail silently if JSON parsing or file reading fails
        pass
