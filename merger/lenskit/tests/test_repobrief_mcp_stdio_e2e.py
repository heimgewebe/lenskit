from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from merger.lenskit.cli.repobrief_mcp_stdio import PROTOCOL_VERSION
from merger.lenskit.core.repobrief_live_freshness import evaluate_live_freshness

REPO_ROOT = Path(__file__).resolve().parents[3]


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(path: Path, *, repo: Path, commit: str) -> Path:
    manifest = path / "demo.bundle.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "kind": "repolens.bundle.manifest",
                "run_id": "demo",
                "artifacts": [],
                "snapshot_provenance": {
                    "version": "v1",
                    "repositories": [
                        {
                            "name": repo.name,
                            "repo_root": str(repo.resolve()),
                            "git_commit": commit,
                            "git_dirty": False,
                            "git_branch": "main",
                            "provenance_status": "present",
                            "freshness_basis": "git_commit_and_working_tree",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_mcp_stdio_module_process_completes_real_handshake(tmp_path: Path) -> None:
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1"},
            },
        },
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
    ]
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "merger.lenskit.cli.repobrief_mcp_stdio",
            "--bundle-root",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        input="".join(json.dumps(request) + "\n" for request in requests),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    assert [response["id"] for response in responses] == [1, 2]
    assert responses[0]["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert {
        tool["name"] for tool in responses[1]["result"]["tools"]
    } == {"ask_context", "grounding_verify", "live_freshness"}


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable unavailable")
def test_live_freshness_real_git_probe_is_read_only_and_detects_dirtiness(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "--initial-branch=main")
    _git(repo, "config", "user.name", "RepoBrief Test")
    _git(repo, "config", "user.email", "repobrief@example.invalid")
    source = repo / "example.py"
    source.write_text("value = 1\n", encoding="utf-8")
    _git(repo, "add", "example.py")
    _git(repo, "commit", "-q", "-m", "initial")
    commit = _git(repo, "rev-parse", "HEAD")
    manifest = _manifest(tmp_path, repo=repo, commit=commit)
    index_path = repo / ".git" / "index"
    index_before = _sha256(index_path)

    clean = evaluate_live_freshness(manifest, repo_root=repo)

    assert clean["status"] == "fresh"
    assert clean["current_provenance"]["git_commit"] == commit
    assert _sha256(index_path) == index_before
    assert _git(repo, "rev-parse", "HEAD") == commit

    source.write_text("value = 2\n", encoding="utf-8")
    dirty = evaluate_live_freshness(manifest, repo_root=repo)

    assert dirty["status"] == "stale"
    assert dirty["reason"] == "current_working_tree_is_dirty"
    assert _sha256(index_path) == index_before
    assert _git(repo, "rev-parse", "HEAD") == commit
