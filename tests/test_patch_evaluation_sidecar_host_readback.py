from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "tests" / "test_patch_evaluation_sidecar.py"
SPEC = importlib.util.spec_from_file_location(
    "patch_sidecar_cases_for_host_readback", CASES_PATH
)
assert SPEC is not None and SPEC.loader is not None
cases = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cases
SPEC.loader.exec_module(cases)

sidecar = cases.sidecar
_repo = cases._repo
_patch = cases._patch
_request = cases._request
_evaluate = cases._evaluate
_run = cases._run


def test_workspace_snapshot_refreshes_filter_inventory_before_host_git(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    (repo / ".gitattributes").write_text(
        "message.txt filter=late-driver\n", encoding="utf-8"
    )
    _run("git", "add", ".gitattributes", cwd=repo)
    _run("git", "commit", "-qm", "attributes", cwd=repo)

    sidecar._configured_filter_drivers.cache_clear()
    sidecar._workspace_snapshot(repo, [{"path": "message.txt"}])

    marker = tmp_path / "host-filter-ran"
    script = tmp_path / "late-filter.py"
    script.write_text(
        "import pathlib,sys\n"
        f"pathlib.Path({str(marker)!r}).touch()\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
        encoding="utf-8",
    )
    _run(
        "git",
        "config",
        "filter.late-driver.clean",
        f"{sys.executable} {script}",
        cwd=repo,
    )
    (repo / "message.txt").write_text("changed\n", encoding="utf-8")
    marker.unlink(missing_ok=True)

    sidecar._workspace_snapshot(repo, [{"path": "message.txt"}])

    assert not marker.exists()


def test_command_sandbox_overlays_git_metadata_read_only(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    home = tmp_path / "home"
    tmpdir = tmp_path / "tmp"
    home.mkdir()
    tmpdir.mkdir()
    spec = sidecar.CommandSpec((sys.executable, "-c", "pass"), ".", 10, ())

    argv = sidecar._sandbox_command_argv(
        spec,
        sandbox_binary=Path("/usr/bin/bwrap"),
        workspace=repo,
        sandbox_home=home,
        sandbox_tmp=tmpdir,
    )

    mount = ["--ro-bind", str(repo / ".git"), "/workspace/.git"]
    assert any(argv[index : index + 3] == mount for index in range(len(argv) - 2))
    assert argv.index("--ro-bind", argv.index(str(repo))) < argv.index("--chdir")


def test_python_command_cannot_prepare_git_alternates_for_host_readback(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    _, artifact = _evaluate(
        tmp_path,
        _request(
            repo,
            patch,
            [
                {
                    "argv": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; "
                        "Path('.git/objects/info/alternates').write_text('/tmp/foreign')",
                    ],
                    "cwd": ".",
                    "timeout_seconds": 10,
                }
            ],
        ),
    )

    assert artifact["commands_run"][0]["status"] == "failed"
    assert artifact["status"] == "failed"


def test_git_mutation_rejection_remains_infrastructure_error(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    _, artifact = _evaluate(
        tmp_path,
        _request(
            repo,
            patch,
            [
                {
                    "argv": ["git", "config", "sidecar.escape", "yes"],
                    "cwd": ".",
                    "timeout_seconds": 10,
                }
            ],
        ),
    )

    source_value = subprocess.run(
        ["git", "config", "--get", "sidecar.escape"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    assert artifact["commands_run"][0]["status"] == "error"
    assert artifact["status"] == "error"
    assert source_value.returncode == 1
