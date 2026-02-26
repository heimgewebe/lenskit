import pytest
import json
from pathlib import Path
from merger.lenskit.core.merge import scan_repo, write_reports_v2, ExtrasConfig, parse_human_size

@pytest.fixture
def golden_fixture(tmp_path):
    repo = tmp_path / "golden_repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "test.py").write_text("print('hello')", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "readme.md").write_text("# Readme", encoding="utf-8")
    # Minimal hidden file for implicit include_hidden check
    (repo / ".hidden_dir").mkdir()
    (repo / ".hidden_dir" / "hidden.txt").write_text("secret", encoding="utf-8")
    return repo

def _get_dump_index(output_dir):
    """Finds and loads the dump index JSON from the output directory."""
    candidates = list(output_dir.glob("*.dump_index.json"))
    if not candidates:
        return None
    # Assuming one dump index per run
    return candidates[0]

def run_rlens_fixture(repo_path, output_dir):
    """Mimic rlens (Service) execution logic using plain dict config."""
    # Service defaults (simulated)
    req = {
        "level": "max",
        "mode": "gesamt",
        "max_bytes": "0",
        "split_size": "25MB",
        "extras": "json_sidecar,augment_sidecar",
        "meta_density": "auto",
        "json_sidecar": True,
        "output_mode": "dual",
        "redact_secrets": False,
        "include_hidden": True
    }

    max_bytes = parse_human_size(req["max_bytes"])
    extras_config = ExtrasConfig.from_csv(req["extras"])[0]
    if req["json_sidecar"]:
        extras_config.json_sidecar = True

    summary = scan_repo(
        repo_path,
        None, # extensions
        None, # path_filter
        max_bytes,
        include_paths=None,
        calculate_md5=True,
        include_hidden=req["include_hidden"]
    )

    generator_info = {
        "name": "rlens",
        "version": "dev",
        "platform": "service"
    }

    write_reports_v2(
        output_dir,
        repo_path.parent, # Hub
        [summary],
        req["level"],
        req["mode"],
        max_bytes,
        False, # plan_only
        False, # code_only
        parse_human_size(req["split_size"]),
        debug=False,
        path_filter=None,
        ext_filter=None,
        extras=extras_config,
        meta_density=req["meta_density"],
        output_mode=req["output_mode"],
        redact_secrets=req["redact_secrets"],
        generator_info=generator_info,
    )

def run_repolens_fixture(repo_path, output_dir):
    """Mimic repolens (CLI/Frontend) execution logic using local defaults."""
    # CLI defaults (simulated)
    level = "max"
    mode = "gesamt"
    max_bytes = 0
    split_size = parse_human_size("25MB")
    extras_str = "json_sidecar,augment_sidecar"
    meta_density = "auto"
    include_hidden = True
    output_mode = "dual"
    redact_secrets = False

    extras_config = ExtrasConfig.from_csv(extras_str)[0]
    extras_config.json_sidecar = True

    summary = scan_repo(
        repo_path,
        None,
        None,
        max_bytes,
        include_paths=None,
        calculate_md5=True,
        include_hidden=include_hidden
    )

    generator_info = {
        "name": "repolens",
        "platform": "cli"
    }

    write_reports_v2(
        output_dir,
        repo_path.parent, # Hub
        [summary],
        level,
        mode,
        max_bytes,
        False, # plan_only
        False, # code_only
        split_size,
        debug=False,
        path_filter=None,
        ext_filter=None,
        extras=extras_config,
        meta_density=meta_density,
        output_mode=output_mode,
        redact_secrets=redact_secrets,
        generator_info=generator_info,
    )

def test_tool_parity_contract_invariants(golden_fixture, tmp_path):
    rlens_out = tmp_path / "rlens_out"
    repolens_out = tmp_path / "repolens_out"
    rlens_out.mkdir()
    repolens_out.mkdir()

    run_rlens_fixture(golden_fixture, rlens_out)
    run_repolens_fixture(golden_fixture, repolens_out)

    # 1. Canonical Entry Point: dump_index
    r_dump_path = _get_dump_index(rlens_out)
    p_dump_path = _get_dump_index(repolens_out)

    assert r_dump_path and r_dump_path.exists(), "rlens dump_index missing"
    assert p_dump_path and p_dump_path.exists(), "repolens dump_index missing"

    with open(r_dump_path) as f: r_dump = json.load(f)
    with open(p_dump_path) as f: p_dump = json.load(f)

    # Verify dump contract
    assert r_dump["contract"] == "dump-index"
    assert p_dump["contract"] == "dump-index"

    # 2. Check Artifacts existence via dump_index
    # We expect at least: merge_md, sidecar_json, chunk_index (since dual mode)
    required_artifacts = ["merge_md", "sidecar_json", "chunk_index"]

    for key in required_artifacts:
        # Check rlens
        assert key in r_dump["artifacts"], f"rlens missing artifact {key} in dump_index"
        r_art = r_dump["artifacts"][key]
        assert r_art, f"rlens artifact {key} entry is null"
        r_path = rlens_out / r_art["path"]
        assert r_path.exists(), f"rlens artifact {key} file missing: {r_path}"
        assert len(r_art["sha256"]) == 64, f"rlens artifact {key} sha256 invalid"

        # Check repolens
        assert key in p_dump["artifacts"], f"repolens missing artifact {key} in dump_index"
        p_art = p_dump["artifacts"][key]
        assert p_art, f"repolens artifact {key} entry is null"
        p_path = repolens_out / p_art["path"]
        assert p_path.exists(), f"repolens artifact {key} file missing: {p_path}"
        assert len(p_art["sha256"]) == 64, f"repolens artifact {key} sha256 invalid"

    # 3. Parity on Sidecar Invariants
    r_sidecar_path = rlens_out / r_dump["artifacts"]["sidecar_json"]["path"]
    p_sidecar_path = repolens_out / p_dump["artifacts"]["sidecar_json"]["path"]

    with open(r_sidecar_path) as f: r_meta = json.load(f)["meta"]
    with open(p_sidecar_path) as f: p_meta = json.load(f)["meta"]

    # Contract invariants
    assert r_meta["contract"] == p_meta["contract"]
    assert r_meta["contract_version"] == p_meta["contract_version"]

    # Configuration parity (we invoked them similarly)
    assert r_meta["profile"] == p_meta["profile"]
    assert r_meta["total_files"] == p_meta["total_files"], "Total file count mismatch"

    # Feature parity (Superset check)
    # Ensure all features present in rlens are also in repolens (and vice versa, as we expect exact parity here)
    # But strictly speaking, contract parity means they share the required feature set.
    r_features = set(r_meta.get("features", []))
    p_features = set(p_meta.get("features", []))

    # We expect 'semantic_chunk_fields' and 'architecture_summary' in dual mode
    assert "semantic_chunk_fields" in r_features
    assert "semantic_chunk_fields" in p_features
    assert r_features == p_features, "Feature set mismatch"

    # Allowed differences: Generator info
    assert r_meta["generator"]["name"] == "rlens"
    assert p_meta["generator"]["name"] == "repolens"
    assert r_meta["generator"]["platform"] == "service"
    assert p_meta["generator"]["platform"] == "cli"

    # 4. Chunk Index Contract
    r_chunk_path = rlens_out / r_dump["artifacts"]["chunk_index"]["path"]
    p_chunk_path = repolens_out / p_dump["artifacts"]["chunk_index"]["path"]

    with open(r_chunk_path) as f: r_chunks = [json.loads(line) for line in f]
    with open(p_chunk_path) as f: p_chunks = [json.loads(line) for line in f]

    assert len(r_chunks) > 0, "rlens chunks empty"
    assert len(p_chunks) > 0, "repolens chunks empty"

    # Loose parity on count (allow minor drift if e.g. versions differ, but here versions are same core)
    # Since we use same core version, counts should match exactly.
    assert len(r_chunks) == len(p_chunks), "Chunk count mismatch"

    # Verify fields (Contract v2)
    required_chunk_fields = ["chunk_id", "path", "repo", "sha256", "size"]
    semantic_fields = ["section", "layer", "artifact_type", "concepts"]

    # Check first chunk as sample
    c0 = r_chunks[0]
    for k in required_chunk_fields:
        assert k in c0, f"Missing standard chunk field {k}"

    if "semantic_chunk_fields" in r_features:
        for k in semantic_fields:
            assert k in c0, f"Missing semantic chunk field {k}"

    # 5. Architecture Summary Markers
    r_arch_path = rlens_out / r_dump["artifacts"]["architecture_summary"]["path"]
    p_arch_path = repolens_out / p_dump["artifacts"]["architecture_summary"]["path"]

    r_arch_content = r_arch_path.read_text(encoding="utf-8")
    p_arch_content = p_arch_path.read_text(encoding="utf-8")

    # Robust markers
    assert "Layer Distribution" in r_arch_content
    assert "Layer Distribution" in p_arch_content
    # "Core Modules" might be empty or present depending on file structure of fixture
    # In golden_fixture: src/test.py -> likely layer=test or source?
    # Check `get_semantic_metadata_path_only` logic in core/merge.py:
    # "src" -> not explicitly mapped to layer? Actually:
    #   if "core" in parts -> core
    #   elif "tests" or "test" -> test
    #   elif "cli" -> cli ...
    #   else -> unknown?
    # Wait, `get_semantic_metadata_path_only` in merge.py:
    #   if "core" in parts: layer = "core"
    #   elif "tests" in parts or "test" in parts: layer = "test"
    # src/test.py -> "test" in parts? "test.py" is the file name. "parts" includes filename.
    # So it might be layer=test.
    # Let's check for generic header presence.
    assert "# Lenskit Architecture Snapshot" in r_arch_content
