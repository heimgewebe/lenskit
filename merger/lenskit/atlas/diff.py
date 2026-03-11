import json
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List

def compute_snapshot_delta(registry, from_snap_id: str, to_snap_id: str) -> Dict[str, Any]:
    from_snap = registry.get_snapshot(from_snap_id)
    to_snap = registry.get_snapshot(to_snap_id)

    if not from_snap:
        raise ValueError(f"Snapshot not found: {from_snap_id}")
    if not to_snap:
        raise ValueError(f"Snapshot not found: {to_snap_id}")

    if from_snap["status"] != "complete" or to_snap["status"] != "complete":
        raise ValueError("Deltas can only be computed between snapshots with status='complete'.")

    if from_snap["machine_id"] != to_snap["machine_id"] or from_snap["root_id"] != to_snap["root_id"]:
        raise ValueError("Snapshots must belong to the same machine and root for a direct delta calculation.")

    machine_id = from_snap["machine_id"]
    root_id = from_snap["root_id"]

    from_inv_path = None
    if from_snap["inventory_ref"]:
        from_inv_path = Path(from_snap["inventory_ref"])
    to_inv_path = None
    if to_snap["inventory_ref"]:
        to_inv_path = Path(to_snap["inventory_ref"])

    if not from_inv_path or not from_inv_path.exists():
        raise FileNotFoundError(f"Inventory missing for snapshot {from_snap_id}")
    if not to_inv_path or not to_inv_path.exists():
        raise FileNotFoundError(f"Inventory missing for snapshot {to_snap_id}")

    from_files = {}
    with open(from_inv_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            item = json.loads(line)
            from_files[item["rel_path"]] = item

    to_files = {}
    with open(to_inv_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            item = json.loads(line)
            to_files[item["rel_path"]] = item

    new_files = []
    removed_files = []
    changed_files = []

    for path in to_files:
        if path not in from_files:
            new_files.append(path)
        else:
            old_item = from_files[path]
            new_item = to_files[path]

            if old_item.get("size_bytes") != new_item.get("size_bytes") or old_item.get("mtime") != new_item.get("mtime") or old_item.get("is_symlink") != new_item.get("is_symlink"):
                changed_files.append(path)

    for path in from_files:
        if path not in to_files:
            removed_files.append(path)

    new_files.sort()
    removed_files.sort()
    changed_files.sort()

    delta_id = f"delta_{uuid.uuid4().hex[:8]}"
    created_at = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()

    delta = {
        "delta_id": delta_id,
        "from_snapshot_id": from_snap_id,
        "to_snapshot_id": to_snap_id,
        "created_at": created_at,
        "new_files": new_files,
        "removed_files": removed_files,
        "changed_files": changed_files,
        "summary": {
            "new_count": len(new_files),
            "removed_count": len(removed_files),
            "changed_count": len(changed_files)
        }
    }

    # Store in the to_snapshot directory as per convention: snapshots/<snapshot_id>/
    snapshot_dir = Path("atlas") / "machines" / machine_id / "roots" / root_id / "snapshots" / to_snap_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    delta_filename = f"{delta_id}.json"
    delta_path = snapshot_dir / delta_filename

    with open(delta_path, "w", encoding="utf-8") as f:
        json.dump(delta, f, indent=2)

    delta_ref = str(delta_path)
    registry.register_delta(delta_id, from_snap_id, to_snap_id, delta_ref, created_at)

    return delta
