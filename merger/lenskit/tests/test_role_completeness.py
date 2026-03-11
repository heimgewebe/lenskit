import os
import sys
from pathlib import Path
import json
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from merger.lenskit.core.constants import ArtifactRole

def test_role_completeness():
    """
    Enforces Phase 1 (Schwerpunkt B): ArtifactRole enum must stay in sync with JSON schemas.
    """
    contracts_dir = Path(__file__).parent.parent / "contracts"
    bundle_manifest_schema = contracts_dir / "bundle-manifest.v1.schema.json"

    with bundle_manifest_schema.open() as f:
        schema = json.load(f)

    schema_roles = set(schema["properties"]["artifacts"]["items"]["properties"]["role"]["enum"])

    # We collect all roles from python enum
    python_roles = {r.value for r in ArtifactRole}

    # Exclude virtual/internal roles that are not strictly artifacts in a bundle
    # source_file is used for references, not as a standalone artifact.
    expected_in_schema = python_roles - {"source_file"}

    # Ensure all expected python roles are in the schema
    missing_in_schema = expected_in_schema - schema_roles
    assert not missing_in_schema, f"Roles defined in code but missing from schema: {missing_in_schema}"
