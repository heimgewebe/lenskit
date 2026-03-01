import json
import pytest
from pathlib import Path

from merger.lenskit.tests._test_constants import make_generator_info
from merger.lenskit.core.merge import write_reports_v2, FileInfo
from merger.lenskit.core.constants import ArtifactRole

import jsonschema

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

    # Verify key roles are present
    roles_present = [item["role"] for item in data["artifacts"]]
    assert ArtifactRole.CANONICAL_MD.value in roles_present
    assert ArtifactRole.INDEX_SIDECAR_JSON.value in roles_present
    assert ArtifactRole.DUMP_INDEX_JSON.value in roles_present
    assert ArtifactRole.CHUNK_INDEX_JSONL.value in roles_present

    # Since it's 'dual' output mode, sqlite_index should exist if fts5_bm25 is true
    if data["capabilities"].get("fts5_bm25"):
        assert ArtifactRole.SQLITE_INDEX.value in roles_present

def test_missing_config_sha256_raises_error(tmp_path):
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
            generator_info={"name": "test", "version": "1.0"}
        )
