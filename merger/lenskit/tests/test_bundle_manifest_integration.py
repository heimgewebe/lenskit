import json
import re
from pathlib import Path

import jsonschema
import pytest

from merger.lenskit.core.constants import ArtifactRole
from merger.lenskit.core.merge import FileInfo, write_reports_v2
from merger.lenskit.tests._test_constants import make_generator_info

class MockExtras:
    json_sidecar = True
    skip_md = False
    format = "markdown"
    augment_sidecar = False
    health = False
    organism_index = False
    fleet_panorama = False
    delta_reports = False
    heatmap = False

    @classmethod
    def none(cls):
        return cls()

def test_generate_bundle_manifest_integration(tmp_path):
    # Setup dummy source file
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    f1 = src_dir / "file1.txt"
    f1.write_text("Hello World", encoding="utf-8")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    hub_dir = tmp_path / "hub"
    hub_dir.mkdir()

    fi1 = FileInfo(
        root_label="test-repo",
        abs_path=f1,
        rel_path=Path("file1.txt"),
        size=11,
        is_text=True,
        md5="test",
        category="docs",
        tags=[],
        ext=".txt",
        skipped=False,
    )

    repo_summary = {
        "name": "test-repo",
        "path": str(src_dir),
        "root": src_dir,
        "files": [fi1],
        "source_files": [fi1]
    }

    artifacts = write_reports_v2(
        merges_dir=out_dir,
        hub=hub_dir,
        repo_summaries=[repo_summary],
        detail="test",
        mode="gesamt",
        max_bytes=1000,
        plan_only=False,
        code_only=False,
        extras=MockExtras(),
        output_mode="dual",
        generator_info=make_generator_info()
    )

    # bundle_manifest should exist
    assert artifacts.bundle_manifest is not None
    assert artifacts.bundle_manifest.exists()

    data = json.loads(artifacts.bundle_manifest.read_text(encoding="utf-8"))

    # Load schema
    schema_path = Path(__file__).parent.parent / "contracts" / "bundle-manifest.v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    # Validate schema
    jsonschema.validate(instance=data, schema=schema)

    # Verify key roles are present and contracts are assigned for structured artifacts
    roles_map = {item["role"]: item for item in data["artifacts"]}
    assert ArtifactRole.CANONICAL_MD.value in roles_map

    sidecar_entry = roles_map.get(ArtifactRole.INDEX_SIDECAR_JSON.value)
    assert sidecar_entry and "contract" in sidecar_entry
    assert sidecar_entry["contract"]["id"] == "repolens-agent"
    assert sidecar_entry["interpretation"]["mode"] == "contract"

    dump_entry = roles_map.get(ArtifactRole.DUMP_INDEX_JSON.value)
    assert dump_entry and "contract" not in dump_entry
    assert dump_entry["interpretation"]["mode"] == "role_only"

    chunk_entry = roles_map.get(ArtifactRole.CHUNK_INDEX_JSONL.value)
    assert chunk_entry and "contract" not in chunk_entry
    assert chunk_entry["interpretation"]["mode"] == "role_only"

    # Since it's 'dual' output mode, sqlite_index should exist if fts5_bm25 is true
    if data["capabilities"].get("fts5_bm25"):
        assert ArtifactRole.SQLITE_INDEX.value in roles_map

def test_invalid_config_sha256_raises_error(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    f1 = src_dir / "file1.txt"
    f1.write_text("Hello", encoding="utf-8")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    hub_dir = tmp_path / "hub"
    hub_dir.mkdir()

    fi1 = FileInfo(
        root_label="test-repo",
        abs_path=f1,
        rel_path=Path("file1.txt"),
        size=5,
        is_text=True,
        md5="test",
        category="docs",
        tags=[],
        ext=".txt",
        skipped=False,
    )

    repo_summary = {
        "name": "test-repo",
        "path": str(src_dir),
        "root": src_dir,
        "files": [fi1],
        "source_files": [fi1]
    }

    with pytest.raises(ValueError, match="generator_info.config_sha256 \\(64 hex lowercase\\) is required"):
        write_reports_v2(
            merges_dir=out_dir,
            hub=hub_dir,
            repo_summaries=[repo_summary],
            detail="test",
            mode="gesamt",
            max_bytes=1000,
            plan_only=False,
            code_only=False,
            extras=MockExtras(),
            output_mode="dual",
            generator_info={"name": "test", "version": "1.0", "config_sha256": "invalid_hash"}
        )

def test_missing_config_sha256_is_computed_and_manifest_contains_valid_hash(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    f1 = src_dir / "file1.txt"
    f1.write_text("Hello", encoding="utf-8")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    hub_dir = tmp_path / "hub"
    hub_dir.mkdir()

    fi1 = FileInfo(
        root_label="test-repo",
        abs_path=f1,
        rel_path=Path("file1.txt"),
        size=5,
        is_text=True,
        md5="test",
        category="docs",
        tags=[],
        ext=".txt",
        skipped=False,
    )

    repo_summary = {
        "name": "test-repo",
        "path": str(src_dir),
        "root": src_dir,
        "files": [fi1],
        "source_files": [fi1]
    }

    artifacts = write_reports_v2(
        merges_dir=out_dir,
        hub=hub_dir,
        repo_summaries=[repo_summary],
        detail="test",
        mode="gesamt",
        max_bytes=1000,
        plan_only=False,
        code_only=False,
        extras=MockExtras(),
        output_mode="dual",
        generator_info={"name": "test", "version": "1.0"}
    )

    assert artifacts.bundle_manifest is not None
    assert artifacts.bundle_manifest.exists()

    data = json.loads(artifacts.bundle_manifest.read_text(encoding="utf-8"))

    assert "generator" in data
    assert "config_sha256" in data["generator"]
    assert re.fullmatch(r"[a-f0-9]{64}", data["generator"]["config_sha256"])


def test_producer_emits_authority_metadata_per_role(tmp_path):
    """Phase 1 of Artifact Integrity blueprint: the producer must annotate
    well-defined roles with authority/canonicality/regenerable/staleness_sensitive
    so consumers can distinguish content, index, cache and diagnostic artifacts
    without parsing role strings by hand."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    f1 = src_dir / "file1.txt"
    f1.write_text("Hello World", encoding="utf-8")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    hub_dir = tmp_path / "hub"
    hub_dir.mkdir()

    fi1 = FileInfo(
        root_label="test-repo",
        abs_path=f1,
        rel_path=Path("file1.txt"),
        size=11,
        is_text=True,
        md5="test",
        category="docs",
        tags=[],
        ext=".txt",
        skipped=False,
    )

    repo_summary = {
        "name": "test-repo",
        "path": str(src_dir),
        "root": src_dir,
        "files": [fi1],
        "source_files": [fi1]
    }

    artifacts = write_reports_v2(
        merges_dir=out_dir,
        hub=hub_dir,
        repo_summaries=[repo_summary],
        detail="test",
        mode="gesamt",
        max_bytes=1000,
        plan_only=False,
        code_only=False,
        extras=MockExtras(),
        output_mode="dual",
        generator_info=make_generator_info()
    )

    assert artifacts.bundle_manifest is not None
    assert artifacts.bundle_manifest.exists()

    data = json.loads(artifacts.bundle_manifest.read_text(encoding="utf-8"))

    # Schema guard: emitted manifest still validates with the new fields present.
    schema_path = Path(__file__).parent.parent / "contracts" / "bundle-manifest.v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=data, schema=schema)

    roles_map = {item["role"]: item for item in data["artifacts"]}

    # canonical_md is the single canonical content authority in the bundle.
    can_md = roles_map.get(ArtifactRole.CANONICAL_MD.value)
    assert can_md is not None, "canonical_md must be present in the manifest"
    assert can_md["authority"] == "canonical_content"
    assert can_md["canonicality"] == "content_source"
    assert can_md["regenerable"] is True
    assert can_md["staleness_sensitive"] is False

    # index_sidecar_json is navigation, not content.
    sidecar = roles_map.get(ArtifactRole.INDEX_SIDECAR_JSON.value)
    assert sidecar is not None
    assert sidecar["authority"] == "navigation_index"
    assert sidecar["canonicality"] == "index_only"
    assert sidecar["staleness_sensitive"] is True

    # dump_index_json is navigation/index_only as well.
    dump_idx = roles_map.get(ArtifactRole.DUMP_INDEX_JSON.value)
    assert dump_idx is not None
    assert dump_idx["authority"] == "navigation_index"
    assert dump_idx["canonicality"] == "index_only"

    # chunk_index_jsonl is the derived retrieval index input.
    chunk_idx = roles_map.get(ArtifactRole.CHUNK_INDEX_JSONL.value)
    assert chunk_idx is not None
    assert chunk_idx["authority"] == "retrieval_index"
    assert chunk_idx["canonicality"] == "derived"

    # derived_manifest_json (file: <base>.derived_index.json) is a navigation
    # artifact linking derived artifacts back to their dump_index source —
    # not a retrieval index itself.
    derived_manifest = roles_map.get(ArtifactRole.DERIVED_MANIFEST_JSON.value)
    assert derived_manifest is not None
    assert derived_manifest["authority"] == "navigation_index"
    assert derived_manifest["canonicality"] == "derived"
    assert derived_manifest["regenerable"] is True
    assert derived_manifest["staleness_sensitive"] is True

    # sqlite_index is a runtime cache rebuilt from chunk_index_jsonl;
    # it must never be advertised as canonical content.
    if data["capabilities"].get("fts5_bm25"):
        sqlite_idx = roles_map.get(ArtifactRole.SQLITE_INDEX.value)
        assert sqlite_idx is not None
        assert sqlite_idx["authority"] == "runtime_cache"
        assert sqlite_idx["canonicality"] == "cache"
        assert sqlite_idx["regenerable"] is True
        assert sqlite_idx["staleness_sensitive"] is True


def test_generator_info_none_is_supported_and_hash_is_computed(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir(exist_ok=True)
    f1 = src_dir / "file1.txt"
    f1.write_text("Hello", encoding="utf-8")

    out_dir = tmp_path / "out"
    out_dir.mkdir(exist_ok=True)
    hub_dir = tmp_path / "hub"
    hub_dir.mkdir(exist_ok=True)

    fi1 = FileInfo(
        root_label="test-repo",
        abs_path=f1,
        rel_path=Path("file1.txt"),
        size=5,
        is_text=True,
        md5="test",
        category="docs",
        tags=[],
        ext=".txt",
        skipped=False,
    )

    repo_summary = {
        "name": "test-repo",
        "path": str(src_dir),
        "root": src_dir,
        "files": [fi1],
        "source_files": [fi1]
    }

    artifacts = write_reports_v2(
        merges_dir=out_dir,
        hub=hub_dir,
        repo_summaries=[repo_summary],
        detail="test",
        mode="gesamt",
        max_bytes=1000,
        plan_only=False,
        code_only=False,
        extras=MockExtras(),
        output_mode="dual",
        generator_info=None
    )

    assert artifacts.bundle_manifest is not None
    assert artifacts.bundle_manifest.exists()

    data = json.loads(artifacts.bundle_manifest.read_text(encoding="utf-8"))

    assert "generator" in data
    assert "config_sha256" in data["generator"]
    assert re.fullmatch(r"[a-f0-9]{64}", data["generator"]["config_sha256"])
