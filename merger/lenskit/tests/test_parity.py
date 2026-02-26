import pytest
from pathlib import Path
import json
import os
import shutil
from merger.lenskit.core.merge import scan_repo, write_reports_v2, ExtrasConfig, parse_human_size
# Mimic JobRequest from service/models.py
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict

class JobRequest(BaseModel):
    hub: Optional[str] = None
    merges_dir: Optional[str] = None
    repos: Optional[List[str]] = None
    level: Literal["overview", "summary", "dev", "max"] = "dev"
    mode: Literal["gesamt", "pro-repo"] = "gesamt"
    max_bytes: Optional[str] = "0"
    split_size: Optional[str] = "25MB"
    plan_only: bool = False
    code_only: bool = False
    extensions: Optional[List[str]] = None
    path_filter: Optional[str] = None
    include_paths: Optional[List[str]] = None
    include_paths_by_repo: Optional[Dict[str, Optional[List[str]]]] = None
    strict_include_paths_by_repo: bool = False
    extras: Optional[str] = "json_sidecar,augment_sidecar"
    meta_density: Literal["min", "standard", "full", "auto"] = Field(default="auto")
    json_sidecar: bool = True
    force_new: bool = False
    output_mode: Literal["archive", "retrieval", "dual"] = "dual"
    redact_secrets: bool = False
    include_hidden: bool = True

@pytest.fixture
def golden_fixture(tmp_path):
    repo = tmp_path / "golden_repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "test.py").write_text("print('hello')", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "readme.md").write_text("# Readme", encoding="utf-8")
    (repo / ".hidden_dir").mkdir()
    (repo / ".hidden_dir" / "hidden.txt").write_text("secret", encoding="utf-8")
    (repo / ".env.example").write_text("KEY=value", encoding="utf-8")
    (repo / ".env.secret").write_text("KEY=SECRET", encoding="utf-8")
    return repo

def run_rlens_fixture(repo_path, output_dir):
    """Mimic rlens (Service) execution logic."""
    # Force max level to ensure capability parity with repolens (which defaults to max)
    req = JobRequest(
        level="max",
        mode="gesamt",
        max_bytes="0",
        split_size="25MB",
        extras="json_sidecar,augment_sidecar",
        meta_density="auto",
        json_sidecar=True,
        output_mode="dual",
        redact_secrets=False,
        include_hidden=True
    )

    max_bytes = parse_human_size(req.max_bytes)
    extras = ExtrasConfig.from_csv(req.extras)[0]
    if req.json_sidecar:
        extras.json_sidecar = True

    summary = scan_repo(
        repo_path,
        None, # extensions
        None, # path_filter
        max_bytes,
        include_paths=None,
        calculate_md5=True,
        include_hidden=req.include_hidden
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
        req.level,
        req.mode,
        max_bytes,
        req.plan_only,
        req.code_only,
        parse_human_size(req.split_size),
        debug=False,
        path_filter=req.path_filter,
        ext_filter=None,
        extras=extras,
        meta_density=req.meta_density,
        output_mode=req.output_mode,
        redact_secrets=req.redact_secrets,
        generator_info=generator_info,
    )

def run_repolens_fixture(repo_path, output_dir):
    """Mimic repolens (CLI/Frontend) execution logic."""
    # Defaults from repolens.py
    level = "max"
    mode = "gesamt"
    max_bytes = 0
    split_size = parse_human_size("25MB")
    extras_str = "json_sidecar,augment_sidecar"
    meta_density = "auto"
    include_hidden = True

    extras = ExtrasConfig.from_csv(extras_str)[0]
    extras.json_sidecar = True

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
        extras=extras,
        meta_density=meta_density,
        output_mode="dual",
        redact_secrets=False,
        generator_info=generator_info,
    )

def test_tool_parity(golden_fixture, tmp_path):
    rlens_out = tmp_path / "rlens_out"
    repolens_out = tmp_path / "repolens_out"
    rlens_out.mkdir()
    repolens_out.mkdir()

    run_rlens_fixture(golden_fixture, rlens_out)
    run_repolens_fixture(golden_fixture, repolens_out)

    # 1. Compare Merge Sidecar
    rlens_sidecar_candidates = list(rlens_out.glob("*_merge.json"))
    repolens_sidecar_candidates = list(repolens_out.glob("*_merge.json"))

    assert len(rlens_sidecar_candidates) > 0, "rlens output missing sidecar"
    assert len(repolens_sidecar_candidates) > 0, "repolens output missing sidecar"

    rlens_sidecar = rlens_sidecar_candidates[0]
    repolens_sidecar = repolens_sidecar_candidates[0]

    with open(rlens_sidecar) as f: r_data = json.load(f)
    with open(repolens_sidecar) as f: p_data = json.load(f)

    # a) Meta Features (Capabilities)
    # Check if features key exists first
    assert "meta" in r_data
    assert "meta" in p_data
    assert "features" in r_data["meta"]
    assert "features" in p_data["meta"]

    # Sort features list for comparison if it's a list
    if isinstance(r_data["meta"]["features"], list):
        r_data["meta"]["features"].sort()
    if isinstance(p_data["meta"]["features"], list):
        p_data["meta"]["features"].sort()

    assert r_data["meta"]["features"] == p_data["meta"]["features"]

    # b) Profile
    assert r_data["meta"]["profile"] == p_data["meta"]["profile"], "Profile mismatch (level)"

    # c) File Count
    # 'file_count' is likely 'total_files' in meta block
    assert r_data["meta"]["total_files"] == p_data["meta"]["total_files"], "File count (total_files) mismatch"

    # 2. Compare Chunk Index
    # Note: filename format is base.chunk_index.jsonl (dot separator)
    rlens_ci_list = list(rlens_out.glob("*.chunk_index.jsonl"))
    repolens_ci_list = list(repolens_out.glob("*.chunk_index.jsonl"))

    assert len(rlens_ci_list) > 0, "rlens missing chunk index"
    assert len(repolens_ci_list) > 0, "repolens missing chunk index"

    rlens_ci = rlens_ci_list[0]
    repolens_ci = repolens_ci_list[0]

    with open(rlens_ci) as f: r_chunks = [json.loads(line) for line in f]
    with open(repolens_ci) as f: p_chunks = [json.loads(line) for line in f]

    assert len(r_chunks) == len(p_chunks), "Chunk count mismatch"

    # Check Semantic Fields
    for c in r_chunks:
        assert "section" in c
        assert "layer" in c
        assert "artifact_type" in c
        assert "concepts" in c

    for c in p_chunks:
        assert "section" in c
        assert "layer" in c
        assert "artifact_type" in c
        assert "concepts" in c

    # 3. Compare Architecture Summary
    rlens_arch_list = list(rlens_out.glob("*_architecture.md"))
    repolens_arch_list = list(repolens_out.glob("*_architecture.md"))

    assert len(rlens_arch_list) > 0, "rlens missing architecture summary"
    assert len(repolens_arch_list) > 0, "repolens missing architecture summary"

    rlens_arch = rlens_arch_list[0]
    repolens_arch = repolens_arch_list[0]

    r_arch_content = rlens_arch.read_text(encoding="utf-8")
    p_arch_content = repolens_arch.read_text(encoding="utf-8")

    # Content check (keywords)
    # Use robust check as per memory instructions ("- core:" etc, but here generic)
    assert "Layer Distribution" in r_arch_content
    assert "Core Modules" in r_arch_content
    assert "Layer Distribution" in p_arch_content
    assert "Core Modules" in p_arch_content

    # Explicit Allowlist checks (what differs)
    # Generator name/platform is allowed to differ
    assert r_data["meta"]["generator"]["name"] == "rlens"
    assert p_data["meta"]["generator"]["name"] == "repolens"

    assert r_data["meta"]["generator"]["platform"] == "service"
    assert p_data["meta"]["generator"]["platform"] == "cli"
