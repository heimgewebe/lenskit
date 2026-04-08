import pytest
from pathlib import Path
from merger.lenskit.adapters.atlas import AtlasScanner

def test_atlas_workspace_signal_detection(tmp_path):
    """
    Verifies that AtlasScanner correctly identifies workspaces based on signals.
    This test ensures that the centralized WORKSPACE_SIGNALS constant is correctly
    utilized during the scan process.
    """
    # 1. Setup a directory structure with various workspace signals

    # A Python project
    py_proj = tmp_path / "python_project"
    py_proj.mkdir()
    (py_proj / "pyproject.toml").write_text("[tool.poetry]", encoding="utf-8")
    (py_proj / "README.md").write_text("Python Project", encoding="utf-8")

    # A Node project
    node_proj = tmp_path / "node_project"
    node_proj.mkdir()
    (node_proj / "package.json").write_text('{"name": "test"}', encoding="utf-8")

    # A Git repo (with .git as a directory)
    git_repo = tmp_path / "git_repo"
    git_repo.mkdir()
    (git_repo / ".git").mkdir()
    (git_repo / "README.md").write_text("Git Repo", encoding="utf-8")

    # Mixed workspace
    mixed_ws = tmp_path / "mixed"
    mixed_ws.mkdir()
    (mixed_ws / "compose.yml").write_text("version: '3'", encoding="utf-8")
    (mixed_ws / ".ai-context.yml").write_text("context: test", encoding="utf-8")

    # 2. Run the scanner
    scanner = AtlasScanner(tmp_path)
    result = scanner.scan()
    workspaces = result["stats"]["workspaces"]

    # 3. Verify detection
    # Sort by path for stable assertions
    workspaces.sort(key=lambda x: x["root_path"])

    # git_repo (path: "git_repo")
    # Note: .git is handled via has_git, README.md is in WORKSPACE_SIGNALS
    git_ws = next(w for w in workspaces if w["root_path"] == "git_repo")
    assert git_ws["workspace_kind"] == "git_repo"
    assert ".git" in git_ws["signals"]
    assert "README.md" in git_ws["signals"]

    # mixed (path: "mixed")
    # Note: .ai-context.yml and compose.yml are in WORKSPACE_SIGNALS
    mixed_found = next(w for w in workspaces if w["root_path"] == "mixed")
    assert mixed_found["workspace_kind"] == "mixed_workspace" or mixed_found["workspace_kind"] == "compose_stack"
    assert ".ai-context.yml" in mixed_found["signals"]
    assert "compose.yml" in mixed_found["signals"]

    # node_project (path: "node_project")
    node_found = next(w for w in workspaces if w["root_path"] == "node_project")
    assert node_found["workspace_kind"] == "node_project"
    assert "package.json" in node_found["signals"]

    # python_project (path: "python_project")
    py_found = next(w for w in workspaces if w["root_path"] == "python_project")
    assert py_found["workspace_kind"] == "python_project"
    assert "pyproject.toml" in py_found["signals"]
    assert "README.md" in py_found["signals"]

def test_atlas_scanner_constants_accessible():
    """Ensures constants are correctly defined on the class."""
    assert isinstance(AtlasScanner.WORKSPACE_SIGNALS, tuple)
    assert ".ai-context.yml" in AtlasScanner.WORKSPACE_SIGNALS
    assert isinstance(AtlasScanner.DEFAULT_ATLAS_EXCLUDES, tuple)
    assert "proc/**" in AtlasScanner.DEFAULT_ATLAS_EXCLUDES
