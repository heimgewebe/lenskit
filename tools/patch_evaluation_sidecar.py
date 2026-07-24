#!/usr/bin/env python3
"""External Patch Evaluation Sidecar prototype for RBAW-V1-T004.

This executable is intentionally outside ``merger/repoground/core``. It applies
one declared patch in a disposable detached Git worktree, runs an explicit list
of argv-only commands, and emits bounded ``repobrief.patch_evaluation`` v1
evidence. A passing artifact is not approval and does not establish correctness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

PRODUCER_NAME = "repoground-external-patch-evaluation-sidecar"
PRODUCER_VERSION = "0.1.0"
MANDATORY_NON_CLAIMS = [
    "correctness",
    "test_sufficiency",
    "security_correctness",
    "runtime_behavior_outside_evaluated_commands",
    "merge_authorization",
    "merge_readiness",
    "regression_absence",
    "repo_understood",
    "claims_true",
]
_REQUEST_KEYS = {
    "schema_version",
    "repository",
    "base_commit",
    "patch_path",
    "patch_format",
    "commands",
    "global_timeout_seconds",
    "max_log_bytes",
    "repobrief_context",
}
_COMMAND_KEYS = {"argv", "cwd", "timeout_seconds"}
_CONTEXT_KEYS = {
    "bundle_manifest",
    "snapshot_run_id",
    "workbench_outputs",
    "cited_ranges",
    "citations",
}
_MAX_COMMANDS = 32
_MAX_TIMEOUT_SECONDS = 7200
_MAX_LOG_BYTES = 1_000_000


class RequestError(ValueError):
    """The evaluation request is malformed or violates the prototype boundary."""


class EvaluationError(RuntimeError):
    """The isolated evaluation could not be completed with trustworthy provenance."""


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: int


@dataclass(frozen=True)
class EvaluationRequest:
    repository: Path
    base_commit: str
    patch_path: Path
    patch_format: str
    commands: tuple[CommandSpec, ...]
    global_timeout_seconds: int
    max_log_bytes: int
    repobrief_context: dict[str, Any]


@dataclass(frozen=True)
class EvaluationSetup:
    request: EvaluationRequest
    output: Path
    workspace_root: Path
    workspace_id: str
    workspace: Path
    log_directory: Path
    source_head_before: str
    source_fingerprint_before: str
    source_branch: str | None
    exact_base: str


@dataclass
class EvaluationState:
    patch_snapshot: Path | None = None
    patch_sha256: str | None = None
    isolated: bool = False
    patch_applied: bool = False
    changed_files: list[dict[str, Any]] = field(default_factory=list)
    command_records: list[dict[str, Any]] = field(default_factory=list)
    infrastructure_error: bool = False
    error_detail: str | None = None
    workspace_created: bool = False
    workspace_cleaned: bool = False
    source_unchanged: bool = False


def _strict_keys(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise RequestError(
            f"{label} contains unsupported field(s): {', '.join(unknown)}"
        )


def _non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise RequestError(f"{label} must be a non-empty string without NUL bytes")
    return value


def _bounded_int(value: Any, label: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RequestError(f"{label} must be an integer")
    if value < minimum or value > maximum:
        raise RequestError(f"{label} must be between {minimum} and {maximum}")
    return value


def _validate_relative_cwd(value: Any, label: str) -> str:
    cwd = _non_empty_string(value, label)
    pure = PurePosixPath(cwd)
    if pure.is_absolute() or ".." in pure.parts:
        raise RequestError(f"{label} must stay inside the isolated worktree")
    normalized = str(pure)
    return "." if normalized in {"", "."} else normalized


def _validate_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise RequestError(f"{label} must be an array")
    return [
        _non_empty_string(item, f"{label}[{index}]") for index, item in enumerate(value)
    ]


def _validate_context(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise RequestError("repobrief_context must be an object")
    _strict_keys(value, _CONTEXT_KEYS, "repobrief_context")
    result: dict[str, Any] = {}
    for key in ("bundle_manifest", "snapshot_run_id"):
        item = value.get(key)
        if item is not None:
            result[key] = _non_empty_string(item, f"repobrief_context.{key}")
    for key in ("workbench_outputs", "cited_ranges", "citations"):
        if key in value:
            result[key] = _validate_string_list(value[key], f"repobrief_context.{key}")
    return result


def _read_request_object(path: str | Path) -> Mapping[str, Any]:
    request_path = Path(path).expanduser().resolve()
    try:
        data = json.loads(request_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RequestError(f"request could not be read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RequestError(f"request is not valid JSON: {exc}") from exc
    if not isinstance(data, Mapping):
        raise RequestError("request must be a JSON object")
    return data


def _validate_existing_path(value: Any, label: str, *, directory: bool) -> Path:
    path = Path(_non_empty_string(value, label)).expanduser().resolve()
    valid = path.is_dir() if directory else path.is_file()
    if not valid:
        expected = "directory" if directory else "file"
        raise RequestError(f"{label} is not a {expected}: {path}")
    return path


def _validate_base_commit(value: Any) -> str:
    base_commit = _non_empty_string(value, "base_commit")
    if base_commit.startswith("-"):
        raise RequestError("base_commit must not begin with '-'")
    return base_commit


def _validate_patch_format(value: Any) -> str:
    if value not in {"git-diff", "unified-diff"}:
        raise RequestError("patch_format must be git-diff or unified-diff")
    return value


def _validate_command(raw: Any, index: int) -> CommandSpec:
    if not isinstance(raw, Mapping):
        raise RequestError(f"commands[{index}] must be an object")
    label = f"commands[{index}]"
    _strict_keys(raw, _COMMAND_KEYS, label)
    argv = raw.get("argv")
    if not isinstance(argv, list) or not argv:
        raise RequestError(f"{label}.argv must be a non-empty array")
    argv_items = tuple(
        _non_empty_string(item, f"{label}.argv[{position}]")
        for position, item in enumerate(argv)
    )
    cwd = _validate_relative_cwd(raw.get("cwd", "."), f"{label}.cwd")
    timeout = _bounded_int(
        raw.get("timeout_seconds", 300),
        f"{label}.timeout_seconds",
        minimum=1,
        maximum=_MAX_TIMEOUT_SECONDS,
    )
    return CommandSpec(argv_items, cwd, timeout)


def _validate_commands(value: Any) -> tuple[CommandSpec, ...]:
    if not isinstance(value, list):
        raise RequestError("commands must be an array")
    if len(value) > _MAX_COMMANDS:
        raise RequestError(f"commands may contain at most {_MAX_COMMANDS} entries")
    return tuple(_validate_command(raw, index) for index, raw in enumerate(value))


def load_request(path: str | Path) -> EvaluationRequest:
    data = _read_request_object(path)
    _strict_keys(data, _REQUEST_KEYS, "request")
    if data.get("schema_version") != 1:
        raise RequestError("schema_version must be 1")
    repository = _validate_existing_path(
        data.get("repository"), "repository", directory=True
    )
    patch_path = _validate_existing_path(
        data.get("patch_path"), "patch_path", directory=False
    )
    base_commit = _validate_base_commit(data.get("base_commit"))
    return EvaluationRequest(
        repository=repository,
        base_commit=base_commit,
        patch_path=patch_path,
        patch_format=_validate_patch_format(data.get("patch_format", "git-diff")),
        commands=_validate_commands(data.get("commands")),
        global_timeout_seconds=_bounded_int(
            data.get("global_timeout_seconds", 1800),
            "global_timeout_seconds",
            minimum=1,
            maximum=_MAX_TIMEOUT_SECONDS,
        ),
        max_log_bytes=_bounded_int(
            data.get("max_log_bytes", 65536),
            "max_log_bytes",
            minimum=256,
            maximum=_MAX_LOG_BYTES,
        ),
        repobrief_context=_validate_context(data.get("repobrief_context")),
    )


def _sanitized_environment(home: Path, tmpdir: Path) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    tmpdir.mkdir(parents=True, exist_ok=True)
    xdg_config_home = home / ".config"
    xdg_config_home.mkdir(parents=True, exist_ok=True)
    return {
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": os.environ.get("PATH") or os.defpath,
        "PYTHONNOUSERSITE": "1",
        "TMPDIR": str(tmpdir),
        "TZ": "UTC",
        "XDG_CONFIG_HOME": str(xdg_config_home),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _run_bytes(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout: float = 60,
    check: bool = True,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        list(argv),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        shell=False,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise EvaluationError(
            f"command failed ({completed.returncode}): {shlex.join(argv)}: {detail}"
        )
    return completed


def _git(
    repo: Path,
    *args: str,
    timeout: float = 60,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    with tempfile.TemporaryDirectory(
        prefix="repoground-patch-evaluation-git-"
    ) as temporary:
        scratch = Path(temporary)
        env = _sanitized_environment(scratch / "home", scratch / "tmp")
        return _run_bytes(
            (
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.pager=cat",
                "-C",
                str(repo),
                *args,
            ),
            cwd=repo,
            timeout=timeout,
            check=check,
            env=env,
        )


def _git_text(repo: Path, *args: str, timeout: float = 60) -> str:
    return (
        _git(repo, *args, timeout=timeout)
        .stdout.decode("utf-8", errors="strict")
        .strip()
    )


def _snapshot_patch(path: Path, directory: Path) -> tuple[Path, str]:
    """Copy one immutable patch snapshot and bind its digest to applied bytes."""
    digest = hashlib.sha256()
    snapshot: Path | None = None
    try:
        with (
            path.open("rb") as source,
            tempfile.NamedTemporaryFile(
                mode="wb",
                dir=directory,
                prefix=".patch-evaluation-input-",
                suffix=".diff",
                delete=False,
            ) as destination,
        ):
            snapshot = Path(destination.name)
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        return snapshot, digest.hexdigest()
    except Exception:
        if snapshot is not None:
            snapshot.unlink(missing_ok=True)
        raise


def _ensure_outside_repository(path: Path, repository: Path, label: str) -> None:
    resolved = path.expanduser().resolve()
    if resolved == repository or repository in resolved.parents:
        raise RequestError(f"{label} must be outside the source repository")


def _source_snapshot(repository: Path) -> tuple[str, str, str | None]:
    """Fingerprint exact Git-visible source state, including dirty file contents."""
    head = _git_text(repository, "rev-parse", "HEAD")
    digest = hashlib.sha256()
    digest.update(head.encode("ascii"))
    digest.update(b"\0status\0")
    digest.update(
        _git(
            repository, "status", "--porcelain=v1", "-z", "--untracked-files=all"
        ).stdout
    )
    digest.update(b"\0tracked-worktree-diff\0")
    digest.update(
        _git(
            repository,
            "diff",
            "--binary",
            "--no-ext-diff",
            "--no-textconv",
            "HEAD",
            "--",
        ).stdout
    )
    digest.update(b"\0tracked-index-diff\0")
    digest.update(
        _git(
            repository,
            "diff",
            "--binary",
            "--cached",
            "--no-ext-diff",
            "--no-textconv",
            "HEAD",
            "--",
        ).stdout
    )
    untracked = _git(
        repository, "ls-files", "--others", "--exclude-standard", "-z"
    ).stdout
    digest.update(b"\0untracked\0")
    for encoded_path in sorted(item for item in untracked.split(b"\0") if item):
        relative = encoded_path.decode("utf-8", errors="surrogateescape")
        candidate = repository / relative
        digest.update(encoded_path)
        digest.update(b"\0")
        if candidate.is_symlink():
            digest.update(b"symlink\0")
            digest.update(
                os.readlink(candidate).encode("utf-8", errors="surrogateescape")
            )
        elif candidate.is_file():
            digest.update(b"file\0")
            with candidate.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        else:
            digest.update(b"other\0")
    branch_result = _git(
        repository, "symbolic-ref", "--quiet", "--short", "HEAD", check=False
    )
    branch = (
        branch_result.stdout.decode("utf-8", errors="replace").strip()
        if branch_result.returncode == 0
        else None
    )
    return head, digest.hexdigest(), branch or None


def _resolve_base_commit(repository: Path, requested: str) -> str:
    resolved = _git_text(
        repository,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{requested}^{{commit}}",
    )
    if len(resolved) not in {40, 64} or any(
        character not in "0123456789abcdef" for character in resolved
    ):
        raise EvaluationError("base_commit did not resolve to an exact Git object id")
    return resolved


def _parse_changed_files(workspace: Path) -> list[dict[str, Any]]:
    raw = _git(
        workspace, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    ).stdout
    entries = raw.split(b"\0")
    changed: list[dict[str, Any]] = []
    index = 0
    mapping = {
        "A": "added",
        "M": "modified",
        "D": "deleted",
        "R": "renamed",
        "C": "renamed",
        "?": "added",
    }
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        if len(entry) < 4:
            raise EvaluationError("git status returned an unexpected record")
        code = entry[:2].decode("ascii", errors="strict")
        path = entry[3:].decode("utf-8", errors="backslashreplace")
        status = code[0] if code[0] != " " else code[1]
        if status in {"R", "C"} and index < len(entries) and entries[index]:
            path = entries[index].decode("utf-8", errors="backslashreplace")
            index += 1
        changed.append({"path": path, "change": mapping.get(status)})
    return sorted(changed, key=lambda item: item["path"])


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    process.wait(timeout=2)


def _bounded_bytes(path: Path, limit: int) -> tuple[bytes, bool]:
    size = path.stat().st_size
    with path.open("rb") as handle:
        return handle.read(limit), size > limit


def _write_command_log(
    output_path: Path, stdout_path: Path, stderr_path: Path, limit: int
) -> bool:
    header_stdout = b"=== stdout ===\n"
    header_stderr = b"\n=== stderr ===\n"
    budget = max(0, limit - len(header_stdout) - len(header_stderr))
    stdout_budget = budget // 2
    stderr_budget = budget - stdout_budget
    stdout, stdout_truncated = _bounded_bytes(stdout_path, stdout_budget)
    stderr, stderr_truncated = _bounded_bytes(stderr_path, stderr_budget)
    payload = header_stdout + stdout + header_stderr + stderr
    output_path.write_bytes(payload[:limit])
    return stdout_truncated or stderr_truncated or len(payload) > limit


def _run_command(
    spec: CommandSpec,
    *,
    workspace: Path,
    timeout_seconds: float,
    env: Mapping[str, str],
    log_path: Path,
    max_log_bytes: int,
) -> dict[str, Any]:
    command_cwd = (workspace / spec.cwd).resolve()
    if command_cwd != workspace and workspace not in command_cwd.parents:
        raise EvaluationError(f"command cwd escaped isolated worktree: {spec.cwd}")
    if not command_cwd.is_dir():
        raise EvaluationError(f"command cwd is not a directory: {spec.cwd}")

    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="patch-evaluation-command-") as temporary:
        temporary_path = Path(temporary)
        stdout_path = temporary_path / "stdout"
        stderr_path = temporary_path / "stderr"
        with (
            stdout_path.open("wb") as stdout_handle,
            stderr_path.open("wb") as stderr_handle,
        ):
            process = subprocess.Popen(
                list(spec.argv),
                cwd=command_cwd,
                env=dict(env),
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                shell=False,
                start_new_session=True,
            )
            timed_out = False
            try:
                returncode = process.wait(timeout=max(0.001, timeout_seconds))
            except subprocess.TimeoutExpired:
                timed_out = True
                _terminate_process_group(process)
                returncode = None
        truncated = _write_command_log(
            log_path, stdout_path, stderr_path, max_log_bytes
        )
    duration_ms = max(0, round((time.monotonic() - started) * 1000))
    status = "timeout" if timed_out else ("passed" if returncode == 0 else "failed")
    return {
        "command": shlex.join(spec.argv),
        "status": status,
        "exit_code": returncode,
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "duration_ms": duration_ms,
        "log_ref": log_path.name,
        "truncated": truncated,
    }


def _rollup_status(
    records: list[dict[str, Any]], *, patch_applied: bool, infrastructure_error: bool
) -> str:
    if infrastructure_error or not patch_applied:
        return "error"
    if not records:
        return "incomplete"
    statuses = [record["status"] for record in records]
    if any(status == "skipped" for status in statuses):
        return "incomplete"
    if all(status == "passed" for status in statuses):
        return "passed"
    if all(status == "failed" for status in statuses):
        return "failed"
    if all(status in {"error", "timeout", "skipped"} for status in statuses):
        return (
            "error"
            if any(status in {"error", "timeout"} for status in statuses)
            else "incomplete"
        )
    return "mixed"


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _prepare_evaluation(
    request_path: str | Path,
    output_path: str | Path,
    workspace_root: str | Path | None,
) -> EvaluationSetup:
    request = load_request(request_path)
    canonical_repository = Path(
        _git_text(request.repository, "rev-parse", "--show-toplevel")
    ).resolve()
    if canonical_repository != request.repository:
        raise RequestError("repository must name the exact Git worktree root")
    output = Path(output_path).expanduser().resolve()
    _ensure_outside_repository(output, request.repository, "output")
    if output.exists():
        raise RequestError(f"output already exists: {output}")
    requested_workspace_root = (
        Path(workspace_root).expanduser().resolve()
        if workspace_root is not None
        else output.parent / ".patch-evaluation-sidecar-workspaces"
    )
    _ensure_outside_repository(
        requested_workspace_root, request.repository, "workspace_root"
    )
    # Complete read-only provenance preflight before creating output or workspace paths.
    source_head, source_fingerprint, source_branch = _source_snapshot(
        request.repository
    )
    exact_base = _resolve_base_commit(request.repository, request.base_commit)
    if source_head != exact_base:
        source_branch = None
    workspace_id = uuid.uuid4().hex
    log_directory = output.parent / f"{output.stem}.logs"
    if log_directory.exists():
        raise RequestError(f"log directory already exists: {log_directory}")
    requested_workspace_root.mkdir(parents=True, exist_ok=True)
    log_directory.mkdir(parents=True)
    return EvaluationSetup(
        request=request,
        output=output,
        workspace_root=requested_workspace_root,
        workspace_id=workspace_id,
        workspace=requested_workspace_root / workspace_id,
        log_directory=log_directory,
        source_head_before=source_head,
        source_fingerprint_before=source_fingerprint,
        source_branch=source_branch,
        exact_base=exact_base,
    )


def _mark_infrastructure_error(state: EvaluationState, detail: str) -> None:
    state.infrastructure_error = True
    state.error_detail = state.error_detail or detail


def _create_isolated_worktree(setup: EvaluationSetup, state: EvaluationState) -> None:
    # Mark the attempt before Git so transport failure still enters exact-path cleanup.
    state.workspace_created = True
    result = _git(
        setup.request.repository,
        "worktree",
        "add",
        "--detach",
        str(setup.workspace),
        setup.exact_base,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise EvaluationError(f"disposable worktree creation failed: {detail}")
    workspace_head = _git_text(setup.workspace, "rev-parse", "HEAD")
    state.isolated = (
        (setup.workspace / ".git").is_file()
        and workspace_head == setup.exact_base
        and setup.workspace != setup.request.repository
    )
    if not state.isolated:
        raise EvaluationError("disposable worktree isolation could not be proven")


def _apply_patch(setup: EvaluationSetup, state: EvaluationState) -> None:
    assert state.patch_snapshot is not None
    check_result = _git(
        setup.workspace,
        "apply",
        "--check",
        "--recount",
        str(state.patch_snapshot),
        check=False,
    )
    if check_result.returncode != 0:
        detail = check_result.stderr.decode("utf-8", errors="replace").strip()
        raise EvaluationError(f"patch apply check failed: {detail}")
    apply_result = _git(
        setup.workspace,
        "apply",
        "--recount",
        str(state.patch_snapshot),
        check=False,
    )
    if apply_result.returncode != 0:
        detail = apply_result.stderr.decode("utf-8", errors="replace").strip()
        raise EvaluationError(f"patch apply failed: {detail}")
    state.patch_applied = True
    state.changed_files = _parse_changed_files(setup.workspace)


def _skipped_command_record(spec: CommandSpec) -> dict[str, Any]:
    return {
        "command": shlex.join(spec.argv),
        "status": "skipped",
        "exit_code": None,
        "started_at": None,
        "duration_ms": 0,
        "log_ref": None,
        "truncated": False,
    }


def _run_declared_commands(setup: EvaluationSetup, state: EvaluationState) -> None:
    env = _sanitized_environment(
        setup.workspace / ".sidecar-home", setup.workspace / ".sidecar-tmp"
    )
    deadline = time.monotonic() + setup.request.global_timeout_seconds
    for index, spec in enumerate(setup.request.commands, start=1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            state.command_records.append(_skipped_command_record(spec))
            continue
        record = _run_command(
            spec,
            workspace=setup.workspace,
            timeout_seconds=min(float(spec.timeout_seconds), remaining),
            env=env,
            log_path=setup.log_directory / f"command-{index:03d}.log",
            max_log_bytes=setup.request.max_log_bytes,
        )
        record["log_ref"] = f"{setup.log_directory.name}/{record['log_ref']}"
        state.command_records.append(record)


def _perform_evaluation(setup: EvaluationSetup, state: EvaluationState) -> None:
    state.patch_snapshot, state.patch_sha256 = _snapshot_patch(
        setup.request.patch_path, setup.workspace_root
    )
    _create_isolated_worktree(setup, state)
    _apply_patch(setup, state)
    _run_declared_commands(setup, state)


def _cleanup_workspace(setup: EvaluationSetup, state: EvaluationState) -> None:
    if not state.workspace_created:
        state.workspace_cleaned = not setup.workspace.exists()
        return
    try:
        _git(
            setup.request.repository,
            "worktree",
            "remove",
            "--force",
            str(setup.workspace),
            timeout=120,
            check=False,
        )
        # Never prune globally: cleanup and readback are restricted to this workspace.
        listed_result = _git(
            setup.request.repository, "worktree", "list", "--porcelain", check=False
        )
        listed = listed_result.stdout.decode("utf-8", errors="replace")
        state.workspace_cleaned = (
            listed_result.returncode == 0
            and not setup.workspace.exists()
            and str(setup.workspace) not in listed
        )
    except (EvaluationError, OSError, subprocess.SubprocessError) as exc:
        state.workspace_cleaned = False
        state.error_detail = state.error_detail or (
            f"disposable worktree cleanup readback failed: {exc}"
        )
    if not state.workspace_cleaned:
        _mark_infrastructure_error(
            state, "disposable worktree cleanup could not be proven"
        )


def _cleanup_patch_snapshot(state: EvaluationState) -> None:
    if state.patch_snapshot is None:
        return
    try:
        state.patch_snapshot.unlink(missing_ok=True)
    except OSError as exc:
        state.error_detail = (
            state.error_detail or f"patch snapshot cleanup failed: {exc}"
        )
    if state.patch_snapshot.exists():
        _mark_infrastructure_error(state, "patch snapshot cleanup could not be proven")


def _verify_source_unchanged(setup: EvaluationSetup, state: EvaluationState) -> None:
    try:
        source_head, source_fingerprint, _ = _source_snapshot(setup.request.repository)
        state.source_unchanged = (
            source_head == setup.source_head_before
            and source_fingerprint == setup.source_fingerprint_before
        )
    except (EvaluationError, OSError, subprocess.SubprocessError) as exc:
        state.source_unchanged = False
        state.error_detail = (
            state.error_detail or f"source checkout readback failed: {exc}"
        )
    if not state.source_unchanged:
        _mark_infrastructure_error(state, "source checkout changed during evaluation")


def _cleanup_evaluation(setup: EvaluationSetup, state: EvaluationState) -> None:
    _cleanup_workspace(setup, state)
    _cleanup_patch_snapshot(state)
    _verify_source_unchanged(setup, state)


def _git_version(repository: Path) -> str:
    try:
        return (
            _run_bytes(("git", "--version"), cwd=repository, check=False)
            .stdout.decode("utf-8", errors="replace")
            .strip()
        )
    except OSError:
        return "unknown"


def _build_artifact(setup: EvaluationSetup, state: EvaluationState) -> dict[str, Any]:
    status = _rollup_status(
        state.command_records,
        patch_applied=state.patch_applied,
        infrastructure_error=state.infrastructure_error,
    )
    return {
        "kind": "repobrief.patch_evaluation",
        "version": "v1",
        "authority": "external_evaluation_evidence",
        "producer": {
            "name": PRODUCER_NAME,
            "version": PRODUCER_VERSION,
            "commit": None,
            "url": None,
        },
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "input": {
            "repo": str(setup.request.repository),
            "branch": setup.source_branch,
            "base_commit": setup.exact_base,
            "commit": setup.exact_base,
            "pull_request": None,
            "patch_id": state.patch_sha256,
        },
        "repobrief_context": setup.request.repobrief_context,
        "workspace": {
            "isolated": state.isolated,
            "workspace_id": setup.workspace_id,
            "base_commit": setup.exact_base,
        },
        "patch": {
            "applied": state.patch_applied,
            "patch_id": state.patch_sha256,
            "format": setup.request.patch_format,
            "sha256": state.patch_sha256,
            "changed_files": state.changed_files,
        },
        "command_policy": {
            "allowed_commands": [
                shlex.join(command.argv) for command in setup.request.commands
            ],
            "network": "unknown",
            "secrets_policy": "unknown",
            "timeout_seconds": setup.request.global_timeout_seconds,
        },
        "commands_run": state.command_records,
        "environment": {
            "os": platform.platform(),
            "runner": "local-disposable-git-worktree",
            "container": None,
            "tool_versions": {
                "python": platform.python_version(),
                "git": _git_version(setup.request.repository),
            },
        },
        "status": status,
        "does_not_establish": list(MANDATORY_NON_CLAIMS),
    }


def evaluate(
    request_path: str | Path,
    output_path: str | Path,
    *,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    setup = _prepare_evaluation(request_path, output_path, workspace_root)
    state = EvaluationState()
    try:
        _perform_evaluation(setup, state)
    except (EvaluationError, OSError, subprocess.SubprocessError) as exc:
        _mark_infrastructure_error(state, str(exc))
    finally:
        _cleanup_evaluation(setup, state)
    artifact = _build_artifact(setup, state)
    _atomic_write_json(setup.output, artifact)
    if state.error_detail:
        print(f"patch-evaluation-sidecar: {state.error_detail}", file=sys.stderr)
    return {
        "artifact": artifact,
        "output": str(setup.output),
        "workspace_cleaned": state.workspace_cleaned,
        "source_unchanged": state.source_unchanged,
        "error": state.error_detail,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--request", required=True, help="Strict patch-evaluation request JSON"
    )
    parser.add_argument(
        "--output", required=True, help="Artifact path outside the source repository"
    )
    parser.add_argument(
        "--workspace-root",
        help="Optional disposable-worktree parent outside the source repository",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = evaluate(args.request, args.output, workspace_root=args.workspace_root)
    except RequestError as exc:
        print(f"patch-evaluation-sidecar: {exc}", file=sys.stderr)
        return 2
    except (
        EvaluationError,
        OSError,
        UnicodeError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"patch-evaluation-sidecar: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": result["artifact"]["status"],
                "output": result["output"],
                "workspace_cleaned": result["workspace_cleaned"],
                "source_unchanged": result["source_unchanged"],
                "does_not_establish": list(MANDATORY_NON_CLAIMS),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result["artifact"]["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
