from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from merger.repoground.core.patch_evaluation import validate_patch_evaluation

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "patch_evaluation_sidecar.py"
SPEC = importlib.util.spec_from_file_location("patch_evaluation_sidecar", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
sidecar = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sidecar
SPEC.loader.exec_module(sidecar)


def _run(*argv: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "source"
    repo.mkdir()
    _run("git", "init", "-q", cwd=repo)
    _run("git", "config", "user.email", "test@example.invalid", cwd=repo)
    _run("git", "config", "user.name", "Patch Evaluation Test", cwd=repo)
    (repo / "message.txt").write_text("before\n", encoding="utf-8")
    _run("git", "add", "message.txt", cwd=repo)
    _run("git", "commit", "-qm", "initial", cwd=repo)
    return repo


def _patch(repo: Path, tmp_path: Path, content: str = "after\n") -> Path:
    path = repo / "message.txt"
    path.write_text(content, encoding="utf-8")
    patch = tmp_path / "change.diff"
    patch.write_text(_run("git", "diff", "--binary", cwd=repo).stdout, encoding="utf-8")
    _run("git", "checkout", "--", "message.txt", cwd=repo)
    return patch


def _request(
    repo: Path,
    patch: Path,
    commands: list[dict[str, object]],
    *,
    max_log_bytes: int = 4096,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "repository": str(repo),
        "base_commit": _run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip(),
        "patch_path": str(patch),
        "patch_format": "git-diff",
        "commands": commands,
        "global_timeout_seconds": 30,
        "max_log_bytes": max_log_bytes,
        "repobrief_context": {
            "workbench_outputs": ["symbol-index"],
            "citations": ["message.txt:1"],
        },
    }


def _evaluate(
    tmp_path: Path, request: dict[str, object]
) -> tuple[dict[str, object], dict[str, object]]:
    request_path = tmp_path / "request.json"
    output = tmp_path / "out" / "evaluation.json"
    workspace_root = tmp_path / "workspaces"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    result = sidecar.evaluate(request_path, output, workspace_root=workspace_root)
    return result, json.loads(output.read_text(encoding="utf-8"))


def _source_state(repo: Path) -> tuple[str, str]:
    return (
        _run("git", "rev-parse", "HEAD", cwd=repo).stdout,
        _run(
            "git", "status", "--porcelain=v1", "--untracked-files=all", cwd=repo
        ).stdout,
    )


def test_success_isolated_schema_valid_source_unchanged_and_cleaned(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    before = _source_state(repo)
    request = _request(
        repo,
        patch,
        [
            {
                "argv": [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; assert Path('message.txt').read_text() == 'after\\n'",
                ],
                "cwd": ".",
                "timeout_seconds": 10,
            }
        ],
    )
    result, artifact = _evaluate(tmp_path, request)
    assert artifact["status"] == "passed"
    assert artifact["authority"] == "external_evaluation_evidence"
    assert artifact["workspace"]["isolated"] is True
    assert artifact["patch"]["applied"] is True
    assert artifact["patch"]["changed_files"] == [
        {"change": "modified", "path": "message.txt"}
    ]
    assert artifact["commands_run"][0]["status"] == "passed"
    assert result["workspace_cleaned"] is True
    assert result["source_unchanged"] is True
    assert _source_state(repo) == before
    assert not any((tmp_path / "workspaces").iterdir())
    assert validate_patch_evaluation(artifact)["status"] == "pass"


def test_failing_command_is_evidence_not_approval(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    _, artifact = _evaluate(
        tmp_path,
        _request(
            repo,
            patch,
            [
                {
                    "argv": [sys.executable, "-c", "raise SystemExit(7)"],
                    "cwd": ".",
                    "timeout_seconds": 10,
                }
            ],
        ),
    )
    assert artifact["status"] == "failed"
    assert artifact["commands_run"][0]["status"] == "failed"
    assert artifact["commands_run"][0]["exit_code"] == 7
    assert "merge_authorization" in artifact["does_not_establish"]
    assert "correctness" in artifact["does_not_establish"]
    assert validate_patch_evaluation(artifact)["status"] == "pass"


def test_path_traversal_and_unknown_request_fields_fail_closed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    traversal = _request(
        repo,
        patch,
        [
            {
                "argv": [sys.executable, "-c", "pass"],
                "cwd": "../outside",
                "timeout_seconds": 10,
            }
        ],
    )
    request_path = tmp_path / "traversal.json"
    request_path.write_text(json.dumps(traversal), encoding="utf-8")
    with pytest.raises(sidecar.RequestError, match="inside the isolated worktree"):
        sidecar.load_request(request_path)
    unknown = _request(repo, patch, [])
    unknown["approve"] = True
    request_path.write_text(json.dumps(unknown), encoding="utf-8")
    with pytest.raises(sidecar.RequestError, match="unsupported field"):
        sidecar.load_request(request_path)

    option_shaped = _request(repo, patch, [])
    option_shaped["base_commit"] = "--help"
    request_path.write_text(json.dumps(option_shaped), encoding="utf-8")
    with pytest.raises(sidecar.RequestError, match="must not begin"):
        sidecar.load_request(request_path)

    null_format = _request(repo, patch, [])
    null_format["patch_format"] = None
    request_path.write_text(json.dumps(null_format), encoding="utf-8")
    with pytest.raises(sidecar.RequestError, match="patch_format must be"):
        sidecar.load_request(request_path)


def test_patch_apply_failure_runs_no_commands_and_cleans_workspace(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    invalid_patch = tmp_path / "invalid.diff"
    invalid_patch.write_text("this is not a patch\n", encoding="utf-8")
    marker = tmp_path / "must-not-exist"
    request = _request(
        repo,
        invalid_patch,
        [
            {
                "argv": [
                    sys.executable,
                    "-c",
                    f"from pathlib import Path; Path({str(marker)!r}).touch()",
                ],
                "cwd": ".",
                "timeout_seconds": 10,
            }
        ],
    )
    result, artifact = _evaluate(tmp_path, request)
    assert artifact["status"] == "error"
    assert artifact["patch"]["applied"] is False
    assert artifact["commands_run"] == []
    assert result["workspace_cleaned"] is True
    assert not marker.exists()
    assert validate_patch_evaluation(artifact)["status"] == "pass"


def test_logs_are_bounded_and_marked_truncated(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    _, artifact = _evaluate(
        tmp_path,
        _request(
            repo,
            patch,
            [
                {
                    "argv": [sys.executable, "-c", "print('x' * 20000)"],
                    "cwd": ".",
                    "timeout_seconds": 10,
                }
            ],
            max_log_bytes=512,
        ),
    )
    command = artifact["commands_run"][0]
    log_path = tmp_path / "out" / command["log_ref"]
    assert command["truncated"] is True
    assert log_path.stat().st_size <= 512


def test_timeout_is_bounded_and_reported_without_leaving_worktree(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    request = _request(
        repo,
        patch,
        [
            {
                "argv": [sys.executable, "-c", "import time; time.sleep(30)"],
                "cwd": ".",
                "timeout_seconds": 1,
            }
        ],
    )
    result, artifact = _evaluate(tmp_path, request)
    assert artifact["status"] == "error"
    assert artifact["commands_run"][0]["status"] == "timeout"
    assert result["workspace_cleaned"] is True
    assert result["source_unchanged"] is True
    assert validate_patch_evaluation(artifact)["status"] == "pass"


def test_cli_emits_passed_artifact_and_machine_readable_summary(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    request_path = tmp_path / "cli-request.json"
    output = tmp_path / "cli-out" / "evaluation.json"
    workspace_root = tmp_path / "cli-workspaces"
    request_path.write_text(
        json.dumps(
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
            )
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--request",
            str(request_path),
            "--output",
            str(output),
            "--workspace-root",
            str(workspace_root),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert summary["status"] == "passed"
    assert summary["workspace_cleaned"] is True
    assert artifact["status"] == "passed"


def test_internal_git_ignores_repository_hook_configuration(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    hook_directory = tmp_path / "hooks"
    hook_directory.mkdir()
    marker = tmp_path / "hook-ran"
    hook = hook_directory / "post-checkout"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
    hook.chmod(0o755)
    _run("git", "config", "core.hooksPath", str(hook_directory), cwd=repo)

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
    assert not marker.exists()


def test_patch_snapshot_binds_hash_and_applied_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path, "after\n")
    original_bytes = patch.read_bytes()
    replacement = _patch(repo, tmp_path, "replacement\n").read_bytes()
    patch.write_bytes(original_bytes)
    original_git = sidecar._git
    mutated = False

    def mutating_git(repository: Path, *args: str, **kwargs: object):
        nonlocal mutated
        if not mutated and args[:2] == ("worktree", "add"):
            patch.write_bytes(replacement)
            mutated = True
        return original_git(repository, *args, **kwargs)

    monkeypatch.setattr(sidecar, "_git", mutating_git)
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
                        "from pathlib import Path; assert Path('message.txt').read_text() == 'after\\n'",
                    ],
                    "cwd": ".",
                    "timeout_seconds": 10,
                }
            ],
        ),
    )

    expected_sha256 = hashlib.sha256(original_bytes).hexdigest()
    assert mutated is True
    assert artifact["status"] == "passed"
    assert artifact["patch"]["sha256"] == expected_sha256
    assert artifact["patch"]["patch_id"] == expected_sha256


def test_skipped_commands_roll_up_as_incomplete() -> None:
    records = [
        {"status": "passed"},
        {"status": "skipped"},
    ]
    assert (
        sidecar._rollup_status(records, patch_applied=True, infrastructure_error=False)
        == "incomplete"
    )


def test_allowlisted_environment_does_not_inherit_secret_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    monkeypatch.setenv("PATCH_EVALUATION_TEST_SECRET", "must-not-leak")
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
                        "import os; print(os.environ.get('PATCH_EVALUATION_TEST_SECRET', 'absent'))",
                    ],
                    "cwd": ".",
                    "timeout_seconds": 10,
                }
            ],
        ),
    )
    command = artifact["commands_run"][0]
    log_path = tmp_path / "out" / command["log_ref"]
    assert "must-not-leak" not in log_path.read_text(encoding="utf-8")
    assert "absent" in log_path.read_text(encoding="utf-8")
    assert artifact["command_policy"]["secrets_policy"] == "unknown"


def test_dirty_source_content_change_is_detected_fail_closed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    (repo / "source-only.txt").write_text("before command\n", encoding="utf-8")
    request = _request(
        repo,
        patch,
        [
            {
                "argv": [
                    sys.executable,
                    "-c",
                    f"from pathlib import Path; Path({str(repo / 'source-only.txt')!r}).write_text('tampered\\n')",
                ],
                "cwd": ".",
                "timeout_seconds": 10,
            }
        ],
    )
    result, artifact = _evaluate(tmp_path, request)
    assert result["source_unchanged"] is False
    assert artifact["status"] == "error"
    assert validate_patch_evaluation(artifact)["status"] == "pass"


def test_source_fingerprint_includes_staged_index_content(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "message.txt").write_text("staged-one\n", encoding="utf-8")
    _run("git", "add", "message.txt", cwd=repo)
    before = sidecar._source_snapshot(repo)[1]

    replacement = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=repo,
        input="staged-two\n",
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    _run(
        "git",
        "update-index",
        "--cacheinfo",
        f"100644,{replacement},message.txt",
        cwd=repo,
    )

    after = sidecar._source_snapshot(repo)[1]
    assert after != before


def test_non_utf8_changed_path_is_json_safe(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    encoded_path = bytes(repo) + b"/invalid-\xff.txt"
    descriptor = __import__("os").open(
        encoded_path, __import__("os").O_WRONLY | __import__("os").O_CREAT, 0o600
    )
    __import__("os").write(descriptor, b"content\n")
    __import__("os").close(descriptor)

    changed = sidecar._parse_changed_files(repo)
    assert changed == [{"path": "invalid-\\xff.txt", "change": "added"}]
    json.dumps(changed, ensure_ascii=False)


def test_all_mandatory_non_claims_are_always_emitted(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    patch = _patch(repo, tmp_path)
    _, artifact = _evaluate(tmp_path, _request(repo, patch, []))
    assert set(sidecar.MANDATORY_NON_CLAIMS).issubset(artifact["does_not_establish"])
    assert artifact["status"] == "incomplete"
    assert validate_patch_evaluation(artifact)["status"] == "pass"
