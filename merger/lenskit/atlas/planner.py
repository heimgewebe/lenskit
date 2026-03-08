import json
from pathlib import Path
from typing import Dict, Any

def plan_atlas_outputs(scan_mode: str, scan_id: str) -> Dict[str, str]:
    """
    Determines the set of artifacts to generate based on the scan mode.
    Returns a mapping of logical artifact keys to their expected filenames.
    """
    outputs = {
        "summary": f"{scan_id}.summary.md"
    }

    if scan_mode == "inventory":
        outputs["inventory"] = f"{scan_id}.inventory.jsonl"
        outputs["dirs"] = f"{scan_id}.dirs.jsonl"
    elif scan_mode == "topology":
        outputs["topology"] = f"{scan_id}.topology.json"
    elif scan_mode == "content":
        outputs["inventory"] = f"{scan_id}.inventory.jsonl"
        outputs["content"] = f"{scan_id}.content.json"
    elif scan_mode == "workspace":
        outputs["workspaces"] = f"{scan_id}.workspaces.json"
        outputs["hotspots"] = f"{scan_id}.hotspots.json"

    return outputs

def write_mode_placeholders(planned_outputs: Dict[str, str], result_stats: Dict[str, Any], output_dir: Path) -> None:
    """
    Writes placeholder JSON artifacts for structural modes (topology, content, workspace)
    and hotspot artifacts to the given output directory.
    """
    import tempfile
    import os

    def _write_json_atomic(file_path: Path, data: dict):
        # We write atomically like app.py does but locally
        dir_path = file_path.parent
        dir_path.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=str(dir_path), prefix=f".tmp_{file_path.name}")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(temp_path, str(file_path))
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    if "topology" in planned_outputs:
        topology_path = output_dir / planned_outputs["topology"]
        _write_json_atomic(topology_path, {"mode": "topology", "status": "placeholder"})

    if "content" in planned_outputs:
        content_path = output_dir / planned_outputs["content"]
        _write_json_atomic(content_path, {"mode": "content", "status": "placeholder"})

    if "workspaces" in planned_outputs:
        workspaces_path = output_dir / planned_outputs["workspaces"]
        _write_json_atomic(workspaces_path, {"mode": "workspace", "status": "placeholder"})

    if "hotspots" in planned_outputs:
        hotspots_path = output_dir / planned_outputs["hotspots"]
        hotspots_data = {"top_dirs": result_stats.get("stats", {}).get("top_dirs", [])}
        _write_json_atomic(hotspots_path, hotspots_data)
