from pathlib import Path
from typing import Optional

def resolve_atlas_base_dir(registry_db_path: Optional[Path] = None) -> Path:
    """
    Determines the canonical base directory for Atlas artifacts.

    If a registry path is provided, the base is derived deterministically
    from it (two levels up from the registry sqlite file).

    If no registry path is known, it falls back to the current working
    directory's 'atlas' folder (explicit fallback).
    """
    if registry_db_path is not None:
        return registry_db_path.resolve().parent.parent

    # Fallback only used if absolutely unavoidable
    return (Path.cwd() / "atlas").resolve()

def resolve_snapshot_dir(atlas_base_dir: Path, machine_id: str, root_id: str, snapshot_id: str) -> Path:
    """
    Determines the canonical directory for a specific snapshot.
    """
    return atlas_base_dir / "machines" / machine_id / "roots" / root_id / "snapshots" / snapshot_id

def resolve_artifact_ref(atlas_base_dir: Path, ref_path: str) -> Path:
    """
    Resolves a stored artifact reference. If the reference is absolute,
    it is returned as-is. If it is relative, it is resolved against the
    canonical atlas base directory (NOT the process CWD).
    """
    p = Path(ref_path)
    if p.is_absolute():
        return p
    return atlas_base_dir / p
