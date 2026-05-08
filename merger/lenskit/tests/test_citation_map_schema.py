import json
from pathlib import Path

import jsonschema
import pytest


SCHEMA_PATH = (
    Path(__file__).parent.parent / "contracts" / "citation-map.v1.schema.json"
)
EXAMPLE_PATH = (
    Path(__file__).parent.parent
    / "contracts"
    / "examples"
    / "citation_map_minimal.jsonl"
)

CANONICAL_SHA = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
SOURCE_SHA = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"


@pytest.fixture
def schema():
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _minimal_entry():
    return {
        "citation_id": "cit-0001",
        "repo_id": "lenskit",
        "canonical_range": {
            "file_path": "out.merge.md",
            "start_byte": 0,
            "end_byte": 42,
            "start_line": 1,
            "end_line": 3,
            "content_sha256": CANONICAL_SHA,
        },
    }


def test_minimal_entry_is_valid(schema):
    jsonschema.validate(instance=_minimal_entry(), schema=schema)


def test_entry_with_source_range_and_chunk_id_is_valid(schema):
    entry = _minimal_entry()
    entry["source_range"] = {
        "file_path": "docs/architecture/range-semantics.md",
        "start_byte": 0,
        "end_byte": 86,
        "start_line": 1,
        "end_line": 4,
        "content_sha256": SOURCE_SHA,
        "status": "exact",
    }
    entry["chunk_id"] = "chunk-0007"
    jsonschema.validate(instance=entry, schema=schema)


def test_source_range_status_is_required_when_present(schema):
    entry = _minimal_entry()
    entry["source_range"] = {
        "file_path": "docs/architecture/range-semantics.md"
        # status missing
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=entry, schema=schema)


def test_source_range_unavailable_minimal_is_valid(schema):
    entry = _minimal_entry()
    entry["source_range"] = {
        "file_path": "docs/architecture/range-semantics.md",
        "status": "unavailable",
    }
    jsonschema.validate(instance=entry, schema=schema)


def test_source_range_status_unknown_value_rejected(schema):
    entry = _minimal_entry()
    entry["source_range"] = {
        "file_path": "docs/architecture/range-semantics.md",
        "status": "guessed",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=entry, schema=schema)


def test_canonical_range_required(schema):
    entry = _minimal_entry()
    del entry["canonical_range"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=entry, schema=schema)


def test_canonical_range_content_sha256_must_be_lower_hex(schema):
    entry = _minimal_entry()
    entry["canonical_range"]["content_sha256"] = "NOT-A-HASH"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=entry, schema=schema)


def test_additional_properties_rejected_at_root(schema):
    entry = _minimal_entry()
    entry["evidence_use"] = "this belongs to a later evidence/health track"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=entry, schema=schema)


def test_additional_properties_rejected_in_canonical_range(schema):
    entry = _minimal_entry()
    entry["canonical_range"]["semantic_boundary"] = "not in v1"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=entry, schema=schema)


def test_citation_id_must_be_non_empty(schema):
    entry = _minimal_entry()
    entry["citation_id"] = ""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=entry, schema=schema)


def test_example_jsonl_lines_all_validate(schema):
    with EXAMPLE_PATH.open("r", encoding="utf-8") as f:
        lines = [line for line in f if line.strip()]
    assert lines, "example file must contain at least one entry"
    for line in lines:
        entry = json.loads(line)
        jsonschema.validate(instance=entry, schema=schema)
