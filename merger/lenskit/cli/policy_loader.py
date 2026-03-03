import json
import jsonschema
from pathlib import Path
from typing import Dict, Any

class EmbeddingPolicyError(RuntimeError):
    pass

def load_and_validate_embedding_policy(path: Path) -> Dict[str, Any]:
    """
    Loads an embedding policy JSON file and validates it against the schema.
    Returns the parsed JSON dictionary. Raises EmbeddingPolicyError
    if validation fails or the file cannot be read.
    """
    if not path.exists():
        raise EmbeddingPolicyError(f"Embedding policy file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            policy_instance = json.load(f)
    except json.JSONDecodeError as e:
        raise EmbeddingPolicyError(f"Failed to parse embedding policy JSON: {e}")
    except IOError as e:
        raise EmbeddingPolicyError(f"Could not read embedding policy file: {e}")

    schema_path = (Path(__file__).resolve().parent.parent / "contracts" / "embedding-policy.v1.schema.json")
    if not schema_path.exists():
        raise EmbeddingPolicyError(f"Embedding policy schema not found at: {schema_path}")

    try:
        with schema_path.open("r", encoding="utf-8") as sf:
            schema = json.load(sf)
    except Exception as e:
        raise EmbeddingPolicyError(f"Could not load embedding policy schema for validation: {e}")

    try:
        jsonschema.validate(instance=policy_instance, schema=schema)
    except jsonschema.ValidationError as e:
        raise EmbeddingPolicyError(f"Embedding policy validation failed: {e.message}")

    return policy_instance
