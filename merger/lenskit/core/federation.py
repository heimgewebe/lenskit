import json
import datetime
from pathlib import Path
from typing import Optional

FEDERATION_KIND = "repolens.federation.index"
FEDERATION_VERSION = "1.0"

def load_federation_schema() -> Optional[dict]:
    """Loads the federation schema."""
    # Attempt to resolve from module path
    module_dir = Path(__file__).parent
    schema_path = module_dir.parent / "contracts" / "federation-index.v1.schema.json"
    if schema_path.exists():
        with schema_path.open() as f:
            return json.load(f)
    return None

def init_federation(federation_id: str, out_path: Path) -> dict:
    """
    Initializes a new empty federation index adhering to the federation-index.v1.schema.json contract.
    If the file already exists, it raises an exception to prevent accidental overwrites.
    """
    if out_path.exists():
        raise FileExistsError(f"Federation index already exists at: {out_path.resolve().as_posix()}")

    # We do a quick check to see if the schema exists
    # If not, we fail fast.
    schema = load_federation_schema()
    if not schema:
        raise RuntimeError("Federation schema missing at expected path (contracts/federation-index.v1.schema.json)")

    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()

    fed_data = {
        "kind": FEDERATION_KIND,
        "version": FEDERATION_VERSION,
        "federation_id": federation_id,
        "created_at": now,
        "updated_at": now,
        "bundles": []
    }

    # Validate against our own schema before writing (fail safe)
    import jsonschema
    try:
        jsonschema.validate(instance=fed_data, schema=schema)
    except jsonschema.exceptions.ValidationError as e:
        raise ValueError(f"Failed to generate valid federation index schema: {e}")

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(fed_data, f, indent=2, sort_keys=True)

    return fed_data

def validate_federation(index_path: Path) -> bool:
    """
    Validates a federation index against its schema and additional logical constraints.
    Returns True if valid, raises an exception otherwise.
    """
    if not index_path.exists():
        raise FileNotFoundError(f"Federation index not found at: {index_path.resolve().as_posix()}")

    with index_path.open("r", encoding="utf-8") as f:
        fed_data = json.load(f)

    # 1. Schema Validation
    schema = load_federation_schema()
    if schema:
        import jsonschema
        try:
            jsonschema.validate(instance=fed_data, schema=schema)
        except jsonschema.exceptions.ValidationError as e:
            raise ValueError(f"Schema validation failed: {e.message} at path {list(e.path)}")
    else:
        print("Warning: Federation schema missing, skipping structural validation.")

    # 2. Logical Constraints
    bundles = fed_data.get("bundles", [])
    repo_ids = set()
    for b in bundles:
        repo_id = b.get("repo_id")
        bundle_path = b.get("bundle_path")

        if not repo_id:
            raise ValueError("Invalid bundle: missing 'repo_id'.")
        if not bundle_path:
            raise ValueError("Invalid bundle: missing 'bundle_path'.")

        # check uniqueness
        if repo_id in repo_ids:
            raise ValueError(f"Duplicate 'repo_id' found: {repo_id}")
        repo_ids.add(repo_id)

    return True

def inspect_federation(index_path: Path) -> dict:
    """
    Returns a brief, readable summary of a federation index.
    """
    if not index_path.exists():
        raise FileNotFoundError(f"Federation index not found at: {index_path.resolve().as_posix()}")

    with index_path.open("r", encoding="utf-8") as f:
        fed_data = json.load(f)

    federation_id = fed_data.get("federation_id", "<unknown>")
    bundles = fed_data.get("bundles", [])
    updated_at = fed_data.get("updated_at", "<unknown>")

    repo_ids = [b.get("repo_id") for b in bundles if "repo_id" in b]

    return {
        "federation_id": federation_id,
        "bundle_count": len(bundles),
        "repo_ids": repo_ids,
        "updated_at": updated_at
    }

def add_bundle(index_path: Path, repo_id: str, bundle_path: str) -> dict:
    """
    Adds a bundle to an existing federation index.
    Ensures that repo_id is unique and valid before writing.
    """
    if not index_path.exists():
        raise FileNotFoundError(f"Federation index not found at: {index_path.resolve().as_posix()}")

    with index_path.open("r", encoding="utf-8") as f:
        fed_data = json.load(f)

    # Check for uniqueness of repo_id
    for bundle in fed_data.get("bundles", []):
        if bundle.get("repo_id") == repo_id:
            raise ValueError(f"repo_id '{repo_id}' already exists in federation index.")

    # Soft check for bundle_path existence
    bp = Path(bundle_path)
    if not bp.exists():
        print(f"Warning: Bundle path '{bundle_path}' does not currently exist. Adding anyway.")

    # Update state
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()

    new_bundle = {
        "repo_id": repo_id,
        "bundle_path": bp.as_posix() if bp.is_absolute() else str(bp) # preserve raw or convert abs
    }

    if "bundles" not in fed_data:
        fed_data["bundles"] = []

    fed_data["bundles"].append(new_bundle)
    fed_data["updated_at"] = now

    # Validate against our own schema before writing (fail safe)
    schema = load_federation_schema()
    if schema:
        import jsonschema
        try:
            jsonschema.validate(instance=fed_data, schema=schema)
        except jsonschema.exceptions.ValidationError as e:
            raise ValueError(f"Failed to generate valid federation index schema after modification: {e}")

    with index_path.open("w", encoding="utf-8") as f:
        json.dump(fed_data, f, indent=2, sort_keys=True)

    return fed_data
