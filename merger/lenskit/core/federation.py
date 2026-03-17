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
