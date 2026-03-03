import json
import sys
import jsonschema
from pathlib import Path
from typing import Dict, Any

def load_and_validate_embedding_policy(path: Path) -> Dict[str, Any]:
    """
    Loads an embedding policy JSON file and validates it against the schema.
    Returns the parsed JSON dictionary. Exits the program with return code 1
    if validation fails or the file cannot be read.
    """
    if not path.exists():
        print(f"Error: Embedding policy file not found: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        with path.open("r", encoding="utf-8") as f:
            policy_instance = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse embedding policy JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error: Could not read embedding policy file: {e}", file=sys.stderr)
        sys.exit(1)

    schema_path = Path(__file__).parent.parent / "contracts" / "embedding-policy.v1.schema.json"
    if not schema_path.exists():
        # Fallback to absolute if running from odd location, but typically relative to this file
        schema_path = Path("merger/lenskit/contracts/embedding-policy.v1.schema.json")

    try:
        with schema_path.open("r", encoding="utf-8") as sf:
            schema = json.load(sf)
    except Exception as e:
        print(f"Error: Could not load embedding policy schema for validation: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        jsonschema.validate(instance=policy_instance, schema=schema)
    except jsonschema.ValidationError as e:
        print(f"Error: Embedding policy validation failed: {e.message}", file=sys.stderr)
        sys.exit(1)

    return policy_instance
