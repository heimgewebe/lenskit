from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEGACY_TESTS = ROOT / "tests" / "patch_evaluation_sidecar_legacy_cases.py"
SPEC = importlib.util.spec_from_file_location(
    "patch_evaluation_sidecar_legacy_cases", LEGACY_TESTS
)
assert SPEC is not None and SPEC.loader is not None
_legacy_tests = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = _legacy_tests
SPEC.loader.exec_module(_legacy_tests)

# Preserve the original adversarial suite.  The four names below are deliberately
# redefined because this hardening changes their contracts.
for _name, _value in vars(_legacy_tests).items():
    if _name.startswith("test_"):
        globals()[_name] = _value

sidecar = _legacy_tests.sidecar
_repo = _legacy_tests._repo
_patch = _legacy_tests._patch
_request = _legacy_tests._request
_evaluate = _legacy_tests._evaluate
_run = _legacy_tests._run


def test_declared_git_config_mutation_is_rejected_fail_closed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    _, artifact = _evaluate(
        tmp_path,
        _request(
            repo,
            patch,
            [
                {
                    "argv": ["git", "config", "sidecar.pwned", "yes"],
                    "cwd": ".",
                    "timeout_seconds": 10,
                }
            ],
        ),
    )
    source_value = subprocess.run(
        ["git", "config", "--get", "sidecar.pwned"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    assert artifact["status"] == "error"
    assert artifact["commands_run"][0]["status"] == "error"
    assert source_value.returncode == 1


def test_declared_git_ref_mutation_is_rejected_fail_closed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    _, artifact = _evaluate(
        tmp_path,
        _request(
            repo,
            patch,
            [
                {
                    "argv": ["git", "tag", "sidecar-only"],
                    "cwd": ".",
                    "timeout_seconds": 10,
                }
            ],
        ),
    )
    tags = _run("git", "tag", "--list", "sidecar-only", cwd=repo).stdout
    assert artifact["status"] == "error"
    assert artifact["commands_run"][0]["status"] == "error"
    assert tags == ""


def test_fail_fast_preserves_observed_failure(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    request = _request(
        repo,
        patch,
        [
            {
                "argv": [sys.executable, "-c", "raise SystemExit(3)"],
                "cwd": ".",
                "timeout_seconds": 10,
            },
            {
                "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                "cwd": ".",
                "timeout_seconds": 10,
            },
        ],
    )
    request["fail_fast"] = True
    _, artifact = _evaluate(tmp_path, request)
    assert [item["status"] for item in artifact["commands_run"]] == [
        "failed",
        "skipped",
    ]
    assert artifact["status"] == "failed"


def test_foreign_legacy_log_directory_no_longer_blocks_run(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    foreign = tmp_path / "out" / "evaluation.logs"
    foreign.mkdir(parents=True)
    marker = foreign / "foreign"
    marker.write_text("retain\n", encoding="utf-8")

    _, artifact = _evaluate(
        tmp_path,
        _request(
            repo,
            patch,
            [
                {
                    "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                    "cwd": ".",
                    "timeout_seconds": 10,
                }
            ],
        ),
    )

    assert artifact["status"] == "passed"
    assert marker.read_text(encoding="utf-8") == "retain\n"
    assert artifact["commands_run"][0]["log_ref"].startswith("evaluation.")


def test_patch_cannot_be_removed_before_later_success(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    _, artifact = _evaluate(
        tmp_path,
        _request(
            repo,
            patch,
            [
                {
                    "argv": ["git", "reset", "--hard", "HEAD"],
                    "cwd": ".",
                    "timeout_seconds": 10,
                },
                {
                    "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                    "cwd": ".",
                    "timeout_seconds": 10,
                },
            ],
        ),
    )

    assert artifact["patch"]["applied"] is True
    assert [item["status"] for item in artifact["commands_run"]] == [
        "error",
        "skipped",
    ]
    assert artifact["status"] == "error"


def test_sandbox_setup_failure_is_infrastructure_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)

    def never_starts(*args: object, **kwargs: object) -> list[str]:
        return ["/usr/bin/false"]

    monkeypatch.setattr(sidecar, "_sandbox_command_argv", never_starts)
    _, artifact = _evaluate(
        tmp_path,
        _request(
            repo,
            patch,
            [
                {
                    "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                    "cwd": ".",
                    "timeout_seconds": 10,
                }
            ],
        ),
    )
    assert artifact["commands_run"][0]["status"] == "error"
    assert artifact["status"] == "error"


def test_runtime_policy_is_network_denied_and_lazy_fetch_disabled(
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
                        "import os; assert os.environ['GIT_NO_LAZY_FETCH'] == '1'",
                    ],
                    "cwd": ".",
                    "timeout_seconds": 10,
                }
            ],
        ),
    )
    assert artifact["status"] == "passed"
    assert artifact["command_policy"]["network"] == "deny"
    assert artifact["environment"]["container"] == (
        "bubblewrap-fs-pid-net-rlimit-sandbox"
    )
    assert artifact["producer"]["commit"].startswith("sha256:")


def test_output_capture_is_bounded_while_process_runs(tmp_path: Path) -> None:
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
                        "import os; chunk=b'x'*65536; [os.write(1, chunk) for _ in range(256)]",
                    ],
                    "cwd": ".",
                    "timeout_seconds": 10,
                }
            ],
            max_log_bytes=512,
        ),
    )
    record = artifact["commands_run"][0]
    log_path = tmp_path / "out" / record["log_ref"]
    assert artifact["status"] == "passed"
    assert record["truncated"] is True
    assert log_path.stat().st_size <= 512
    assert log_path.stat().st_mode & 0o777 == 0o600


def test_cleanup_refuses_mismatched_workspace_identity(tmp_path: Path) -> None:
    workspace = tmp_path / "foreign"
    workspace.mkdir()
    setup = type("Setup", (), {"workspace": workspace})()
    state = sidecar.EvaluationState()
    state.workspace_identity = (0, 0)
    sidecar._cleanup_workspace(setup, state)
    assert workspaace.is_dir()
    assert state.workspace_cleaned is False
    assert state.infrastructure_error is True


def test_artifact_publication_readback_accepts_already_linked_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    original = sidecarn._atomic_write_json
 
    def ambiguous_write(path: Path, value: dict[str, object]) -> None:
        original(path, value)
        raise OSError("forced directory fsync ambiguity")

    monkeypatch.setattr(sidecar, "_atomic_write_json", ambiguous_write)
    result, artifact = _evaluate(
        tmp_path,
        _request(
            repo,
            patch,
            [
                {
                    "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                    "cwd": ".",
                    "timeout_seconds": 10,
                }
            ],
        ),
    )
    assert result["artifact"]["status"] == "passed"
    assert artifact["status"] == "passed"


# Remove the superseded legacy contracts from this module's collection surface.
for _superseded in (
    "test_declared_git_config_mutates_only_independent_repository",
    "test_declared_git_ref_mutation_does_not_reach_source",
    "test_fail_fast_marks_remaining_commands_skipped",
    "test_log_directory_collision_fails_without_using_foreign_path",
):
    globals().pop(_superseded, None)
