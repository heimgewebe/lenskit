import pytest
import json
import sys
from pathlib import Path

# Add repo root to sys.path
sys.path.append(str(Path(__file__).parents[3]))

from merger.lenskit.core.merge import scan_repo, write_reports_v2, ExtrasConfig, FileInfo

def test_scan_repo_hidden_files_behavior(tmp_path):
    # Setup
    repo_root = tmp_path / "test_repo"
    repo_root.mkdir()
    (repo_root / "visible.txt").write_text("visible", encoding="utf-8")
    (repo_root / ".hidden_dir").mkdir()
    (repo_root / ".hidden_dir" / "hidden_file.txt").write_text("hidden", encoding="utf-8")
    (repo_root / "visible_dir").mkdir()
    (repo_root / "visible_dir" / ".dotfile").write_text("dotfile", encoding="utf-8")

    # Case 1: include_hidden=True (default/repolens)
    summary_inc = scan_repo(repo_root, include_hidden=True)
    files_inc = [f.rel_path.as_posix() for f in summary_inc["files"]]
    assert "visible.txt" in files_inc
    assert ".hidden_dir/hidden_file.txt" in files_inc
    assert "visible_dir/.dotfile" in files_inc

    # Case 2: include_hidden=False (strict)
    summary_exc = scan_repo(repo_root, include_hidden=False)
    files_exc = [f.rel_path.as_posix() for f in summary_exc["files"]]
    assert "visible.txt" in files_exc
    assert ".hidden_dir/hidden_file.txt" not in files_exc
    assert "visible_dir/.dotfile" not in files_exc

def test_write_reports_parity_features(tmp_path):
    # Setup
    merges_dir = tmp_path / "merges"
    merges_dir.mkdir()
    hub = tmp_path

    # Mock content for semantic check
    content = "def hello(): pass\n"
    f = tmp_path / "test.py"
    f.write_text(content, encoding="utf-8")

    fi = FileInfo(
        root_label="repo",
        abs_path=f,
        rel_path=Path("test.py"),
        size=len(content),
        is_text=True,
        md5="dummy",
        category="source",
        tags=[],
        ext=".py"
    )

    summary = {
        "name": "repo",
        "root": tmp_path,
        "files": [fi]
    }

    gen_info = {"name": "parity_test", "version": "1.0", "platform": "test"}

    # Run with dual mode
    write_reports_v2(
        merges_dir,
        hub,
        [summary],
        detail="max",
        mode="gesamt",
        max_bytes=0,
        plan_only=False,
        output_mode="dual", # Should generate architecture + chunk index
        generator_info=gen_info,
        extras=ExtrasConfig(json_sidecar=True)
    )

    # Verify Architecture Summary
    arch_files = list(merges_dir.glob("*_architecture.md"))
    assert len(arch_files) == 1, "Architecture summary not generated"

    # Verify Chunk Index Semantics
    chunk_files = list(merges_dir.glob("*.chunk_index.jsonl"))
    assert len(chunk_files) == 1, "Chunk index not generated"
    chunk_lines = chunk_files[0].read_text(encoding="utf-8").splitlines()
    assert len(chunk_lines) > 0
    chunk = json.loads(chunk_lines[0])

    # Check for semantic fields
    assert "section" in chunk
    assert "layer" in chunk
    assert "concepts" in chunk

    # Verify JSON Sidecar Metadata
    json_files = list(merges_dir.glob("*.json"))
    # sidecar usually follows base name.
    sidecar = None
    for p in json_files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("meta", {}).get("contract") == "repolens-agent":
                sidecar = data
                break
        except Exception:
            continue

    assert sidecar is not None, "JSON sidecar not found"
    meta = sidecar["meta"]
    assert "generator" in meta
    assert meta["generator"]["name"] == "parity_test"
    assert "features" in meta
    assert "semantic_chunk_fields" in meta["features"]
