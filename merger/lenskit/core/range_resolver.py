import json
import hashlib
from pathlib import Path
from typing import Dict, Any

import jsonschema
from .constants import ArtifactRole

def resolve_range_ref(manifest_path: Path, ref: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolves a range_ref against a bundle.manifest.json or dump_index.json to extract
    exact bytes and verify content_sha256.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Validate ref against schema
    schema_path = Path(__file__).parent.parent / "contracts" / "range-ref.v1.schema.json"
    if schema_path.exists():
        with schema_path.open("r", encoding="utf-8") as f:
            schema = json.load(f)
        try:
            jsonschema.validate(instance=ref, schema=schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"range_ref failed schema: {schema_path.name}: {e.message}")

    role_str = ref.get("artifact_role")

    try:
        role = ArtifactRole(role_str)
    except ValueError:
        raise ValueError(f"Unknown artifact_role: {role_str}")

    target_path_str = None

    # Try resolving via bundle manifest format
    if manifest.get("kind") == "repolens.bundle.manifest":
        for artifact in manifest.get("artifacts", []):
            if artifact.get("role") == role.value:
                target_path_str = artifact.get("path")
                break
    # Try resolving via dump_index format
    elif manifest.get("contract") == "dump-index":
        artifacts = manifest.get("artifacts", {})
        # O(1) resolution first
        if role.value in artifacts and isinstance(artifacts[role.value], dict):
            target_path_str = artifacts[role.value].get("path")
        else:
            # Fallback to iteration for older formats
            for _, artifact in artifacts.items():
                if isinstance(artifact, dict) and artifact.get("role") == role.value:
                    target_path_str = artifact.get("path")
                    break
    else:
        raise ValueError("Unsupported manifest format (must be bundle.manifest or dump_index)")

    if not target_path_str:
        raise ValueError(f"Artifact with role '{role_str}' not found in manifest")

    ref_file_path = ref.get("file_path")
    if ref_file_path and ref_file_path != target_path_str:
        raise ValueError(f"file_path mismatch: ref={ref_file_path} manifest={target_path_str}")

    target_path = manifest_path.parent / target_path_str

    if not target_path.exists():
        raise FileNotFoundError(f"Resolved artifact file not found: {target_path}")

    start_byte = ref.get("start_byte")
    end_byte = ref.get("end_byte")
    expected_sha256 = ref.get("content_sha256")

    if start_byte is None or end_byte is None:
        raise ValueError("range_ref must include 'start_byte' and 'end_byte'")

    with target_path.open("rb") as f:
        file_size = target_path.stat().st_size
        if start_byte < 0 or end_byte > file_size or start_byte > end_byte:
            raise ValueError(f"Range [{start_byte}:{end_byte}] is out of bounds for file size {file_size}")

        f.seek(start_byte)
        content_bytes = f.read(end_byte - start_byte)

    actual_sha256 = hashlib.sha256(content_bytes).hexdigest()
    if expected_sha256 and actual_sha256 != expected_sha256:
        raise ValueError(f"Hash mismatch. Expected: {expected_sha256}, Actual: {actual_sha256}")

    try:
        text = content_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"Extracted range could not be decoded as UTF-8: {e}")

    provenance = {
        "run_id": manifest.get("run_id"),
        "artifact_role": role.value
    }

    if "generator" in manifest and "config_sha256" in manifest["generator"]:
        provenance["config_sha256"] = manifest["generator"]["config_sha256"]

    return {
        "text": text,
        "sha256": actual_sha256,
        "bytes": len(content_bytes),
        "lines": [ref.get("start_line", -1), ref.get("end_line", -1)],
        "provenance": provenance
    }
