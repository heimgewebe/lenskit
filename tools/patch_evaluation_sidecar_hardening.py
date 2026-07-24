"""Runtime hardening overlay for the RBAW-V1-T004 Patch Evaluation Sidecar.

The original implementation is retained byte-for-byte as a legacy core.  This
module replaces only boundary-sensitive operations so the resulting evidence is
bound to the applied patch state and resource use is bounded while commands run.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

_LEGACY: Any = None
_WRAPPER_PATH: Path | None = None

_MAX_ADDRESS_SPACE_BYTES = 4 * 1024 * 1024 * 1024
_MAX_COMMAND_FILE_BYTES = 1024 * 1024 * 1024
_MAX_COMMAND_PROCESSES = 256
_MAX_COMMAND_OPEN_FILES = 1024


def _m() -> Any:
    if _LEGACY is None:
        raise RuntimeError("sidecar hardening has not been installed")
    return _LEGACY


def _producer_digest() -> str:
    legacy = _m()
    digest = hashlib.sha256()
    paths = [Path(legacy.__file__).resolve(), Path(__file__).resolve()]
    if _WRAPPER_PATH is not None:
        paths.append(_WRAPPER_PATH.resolve())
    for path in sorted(set(paths), key=str):
        digest.update(str(path.name).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _sanitized_environment(home: Path, tmpdir: Path) -> dict[str, str]:
    legacy = _m()
    environment = legacy._original_sanitized_environment(home, tmpdir)
    environment["GIT_NO_LAZY_FETCH"] = "1"
    return environment


def _sandbox_command_argv(
    spec: Any,
    *,
    sandbox_binary: Path,
    workspace: Path,
    sandbox_home: Path,
    sandbox_tmp: Path,
    ready_marker: str | None = None,
) -> list[str]:
    legacy = _m()
    sandbox_cwd = PurePosixPath("/workspace") / PurePosixPath(spec.cwd)
    argv = [
        str(sandbox_binary),
        "--die-with-parent",
        "--new-session",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--unshare-net",
        "--unshare-cgroup-try",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind-try",
        "/bin",
        "/bin",
        "--ro-bind-try",
        "/lib",
        "/lib",
        "--ro-bind-try",
        "/lib64",
        "/lib64",
        "--ro-bind-try",
        "/opt",
        "/opt",
        "--dir",
        "/etc",
        "--ro-bind-try",
        "/etc/passwd",
        "/etc/passwd",
        "--ro-bind-try",
        "/etc/group",
        "/etc/group",
        "--ro-bind-try",
        "/etc/nsswitch.conf",
        "/etc/nsswitch.conf",
        "--ro-bind-try",
        "/etc/hosts",
        "/etc/hosts",
        "--ro-bind-try",
        "/etc/resolv.conf",
        "/etc/resolv.conf",
        "--ro-bind-try",
        "/etc/ssl",
        "/etc/ssl",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--dir",
        "/home",
        "--bind",
        str(sandbox_home),
        "/home/sidecar",
        "--bind",
        str(sandbox_tmp),
        "/tmp",
        "--bind",
        str(workspace),
        "/workspace",
        "--chdir",
        str(sandbox_cwd),
        "--clearenv",
    ]
    for key, value in _sanitized_environment(sandbox_home, sandbox_tmp).items():
        argv.extend(
            (
                "--setenv",
                key,
                value.replace(str(sandbox_home), "/home/sidecar").replace(
                    str(sandbox_tmp), "/tmp"
                ),
            )
        )
    payload = list(spec.argv)
    if ready_marker is not None:
        wrapper = (
            "import os,sys; "
            "open(sys.argv[1], 'x').close(); "
            "os.execvpe(sys.argv[2], sys.argv[2:], os.environ)"
        )
        payload = [
            str(legacy._resolve_system_tool("python3")),
            "-c",
            wrapper,
            f"/tmp/{ready_marker}",
            *payload,
        ]
    argv.extend(payload)
    return argv


def _limited_sandbox_argv(argv: Sequence[str], timeout_seconds: float) -> list[str]:
    legacy = _m()
    prlimit = legacy._resolve_system_tool("prlimit")
    cpu_seconds = max(2, int(math.ceil(timeout_seconds)) + 2)
    return [
        str(prlimit),
        f"--as={_MAX_ADDRESS_SPACE_BYTES}",
        f"--fsize={_MAX_COMMAND_FILE_BYTES}",
        f"--nproc={_MAX_COMMAND_PROCESSES}",
        f"--nofile={_MAX_COMMAND_OPEN_FILES}",
        f"--cpu={cpu_seconds}",
        "--",
        *argv,
    ]


def _sandbox_binary() -> Path:
    legacy = _m()
    if platform.system() != "Linux":
        raise legacy.RequestError("the prototype requires Linux bubblewrap isolation")
    try:
        binary = legacy._resolve_system_tool("bwrap")
        with tempfile.TemporaryDirectory(
            prefix="repoground-patch-evaluation-bwrap-probe-"
        ) as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            home = root / "home"
            tmpdir = root / "tmp"
            workspace.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            tmpdir.mkdir(mode=0o700)
            marker = f".sandbox-ready-{uuid.uuid4().hex}"
            probe = legacy.CommandSpec(("/usr/bin/true",), ".", 10, ())
            completed = subprocess.run(
                _limited_sandbox_argv(
                    _sandbox_command_argv(
                        probe,
                        sandbox_binary=binary,
                        workspace=workspace,
                        sandbox_home=home,
                        sandbox_tmp=tmpdir,
                        ready_marker=marker,
                    ),
                    10,
                ),
                cwd=workspace,
                env=_sanitized_environment(home, tmpdir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
                shell=False,
            )
            ready = (tmpdir / marker).is_file()
    except legacy.EvaluationError as exc:
        raise legacy.RequestError(str(exc)) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise legacy.RequestError(f"bubblewrap runtime probe failed: {exc}") from exc
    if completed.returncode != 0 or not ready:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        if not ready:
            detail = detail or "sandbox payload did not start"
        raise legacy.RequestError(f"bubblewrap runtime is not usable: {detail}")
    return binary


def _snapshot_patch(path: Path, directory: Path) -> tuple[Path, str]:
    legacy = _m()
    digest = hashlib.sha256()
    snapshot: Path | None = None
    copied = 0
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
                copied += len(chunk)
                if copied > legacy._MAX_PATCH_BYTES:
                    raise legacy.EvaluationError(
                        f"patch snapshot exceeds the {legacy._MAX_PATCH_BYTES}-byte limit"
                    )
                digest.update(chunk)
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        snapshot.chmod(0o600)
        return snapshot, digest.hexdigest()
    except Exception:
        if snapshot is not None:
            snapshot.unlink(missing_ok=True)
        raise


def _update_workspace_path_digest(
    digest: Any, workspace: Path, relative: str
) -> None:
    legacy = _m()
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise legacy.EvaluationError(f"changed path escaped workspace: {relative}")
    candidate = workspace.joinpath(*pure.parts)
    encoded = relative.encode("utf-8", errors="surrogateescape")
    digest.update(encoded)
    digest.update(b"\0")
    if candidate.is_symlink():
        digest.update(b"symlink\0")
        digest.update(os.readlink(candidate).encode("utf-8", errors="surrogateescape"))
    elif candidate.is_file():
        digest.update(b"file\0")
        with candidate.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    elif candidate.is_dir():
        digest.update(b"directory\0")
    else:
        digest.update(b"missing\0")


def _workspace_snapshot(
    workspace: Path, changed_files: Sequence[Mapping[str, Any]]
) -> str:
    legacy = _m()
    digest = hashlib.sha256()
    commands = (
        ("head", ("rev-parse", "HEAD")),
        ("local-config", ("config", "--local", "--null", "--list")),
        ("refs", ("for-each-ref", "--format=%(refname)%00%(objectname)")),
        (
            "tracked-worktree-diff",
            (
                "diff",
                "--binary",
                "--no-ext-diff",
                "--no-textconv",
                "HEAD",
                "--",
            ),
        ),
        (
            "tracked-index-diff",
            (
                "diff",
                "--binary",
                "--cached",
                "--no-ext-diff",
                "--no-textconv",
                "HEAD",
                "--",
            ),
        ),
    )
    for label, argv in commands:
        completed = legacy._git(workspace, *argv, check=False)
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise legacy.EvaluationError(
                f"workspace fingerprint command failed for {label}: {detail}"
            )
        digest.update(label.encode("ascii"))
        digest.update(b"\0")
        digest.update(completed.stdout)
        digest.update(b"\0")
    digest.update(b"patch-paths\0")
    for item in sorted(changed_files, key=lambda value: str(value["path"])):
        _update_workspace_path_digest(digest, workspace, str(item["path"]))
    return digest.hexdigest()


def _capture_stream(stream: Any, limit: int, result: dict[str, Any]) -> None:
    captured = bytearray()
    truncated = False
    try:
        while True:
            chunk = stream.read(64 * 1024)
            if not chunk:
                break
            remaining = max(0, limit - len(captured))
            if remaining:
                captured.extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated = True
    finally:
        stream.close()
    result["content"] = bytes(captured)
    result["truncated"] = truncated


def _redact_captured_bytes(
    content: bytes, limit: int, redactions: Sequence[bytes]
) -> tuple[bytes, bool]:
    redacted = content
    for value in sorted((item for item in redactions if item), key=len, reverse=True):
        redacted = redacted.replace(value, b"<redacted>")
    return redacted[:limit], len(redacted) > limit


def _write_command_log(
    output_path: Path,
    stdout: bytes,
    stderr: bytes,
    limit: int,
    *,
    stdout_truncated: bool,
    stderr_truncated: bool,
    redactions: Sequence[bytes] = (),
) -> bool:
    header_stdout = b"=== stdout ===\n"
    header_stderr = b"\n=== stderr ===\n"
    budget = max(0, limit - len(header_stdout) - len(header_stderr))
    stdout_budget = budget // 2
    stderr_budget = budget - stdout_budget
    stdout, stdout_redaction_truncated = _redact_captured_bytes(
        stdout, stdout_budget, redactions
    )
    stderr, stderr_redaction_truncated = _redact_captured_bytes(
        stderr, stderr_budget, redactions
    )
    payload = header_stdout + stdout + header_stderr + stderr
    output_path.write_bytes(payload[:limit])
    output_path.chmod(0o600)
    return (
        stdout_truncated
        or stderr_truncated
        or stdout_redaction_truncated
        or stderr_redaction_truncated
        or len(payload) > limit
    )


def _run_command(
    spec: Any,
    *,
    sandbox_binary: Path,
    workspace: Path,
    sandbox_home: Path,
    sandbox_tmp: Path,
    timeout_seconds: float,
    log_path: Path,
    max_log_bytes: int,
) -> dict[str, Any]:
    legacy = _m()
    command_cwd = (workspace / spec.cwd).resolve()
    if command_cwd != workspace and workspace not in command_cwd.parents:
        raise legacy.EvaluationError(
            f"command cwd escaped isolated repository: {spec.cwd}"
        )
    if not command_cwd.is_dir():
        raise legacy.EvaluationError(f"command cwd is not a directory: {spec.cwd}")

    header_bytes = len(b"=== stdout ===\n\n=== stderr ===\n")
    redaction_extra = max(
        (len(spec.argv[index].encode("utf-8")) for index in spec.redact_argv_indexes),
        default=0,
    )
    capture_budget = max(0, max_log_bytes - header_bytes)
    stdout_budget = capture_budget // 2 + redaction_extra
    stderr_budget = capture_budget - capture_budget // 2 + redaction_extra
    stdout_result: dict[str, Any] = {}
    stderr_result: dict[str, Any] = {}
    ready_marker = f".sandbox-ready-{uuid.uuid4().hex}"
    ready_path = sandbox_tmp / ready_marker
    started_at = legacy.datetime.now(legacy.timezone.utc)
    started = time.monotonic()
    sandbox_argv = legacy._sandbox_command_argv(
        spec,
        sandbox_binary=sandbox_binary,
        workspace=workspace,
        sandbox_home=sandbox_home,
        sandbox_tmp=sandbox_tmp,
        ready_marker=ready_marker,
    )
    process = subprocess.Popen(
        _limited_sandbox_argv(sandbox_argv, timeout_seconds),
        cwd=workspace,
        env=_sanitized_environment(sandbox_home, sandbox_tmp),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        start_new_session=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    stdout_thread = threading.Thread(
        target=_capture_stream,
        args=(process.stdout, stdout_budget, stdout_result),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_capture_stream,
        args=(process.stderr, stderr_budget, stderr_result),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    timed_out = False
    try:
        returncode = process.wait(timeout=max(0.001, timeout_seconds))
    except subprocess.TimeoutExpired:
        timed_out = True
        legacy._terminate_process_group(process)
        returncode = None
    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    if stdout_thread.is_alive() or stderr_thread.is_alive():
        raise legacy.EvaluationError("command output capture did not terminate")
    sandbox_ready = ready_path.is_file()
    ready_path.unlink(missing_ok=True)
    truncated = _write_command_log(
        log_path,
        stdout_result.get("content", b""),
        stderr_result.get("content", b""),
        max_log_bytes,
        stdout_truncated=bool(stdout_result.get("truncated", False)),
        stderr_truncated=bool(stderr_result.get("truncated", False)),
        redactions=tuple(
            spec.argv[index].encode("utf-8") for index in spec.redact_argv_indexes
        ),
    )
    duration_ms = max(0, round((time.monotonic() - started) * 1000))
    if not sandbox_ready:
        status = "error"
        returncode = None
    elif timed_out:
        status = "timeout"
    else:
        status = "passed" if returncode == 0 else "failed"
    return {
        "command": legacy._display_command(spec),
        "status": status,
        "exit_code": returncode,
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "duration_ms": duration_ms,
        "log_ref": log_path.name,
        "truncated": truncated,
    }


def _error_command_record(spec: Any) -> dict[str, Any]:
    legacy = _m()
    return {
        "command": legacy._display_command(spec),
        "status": "error",
        "exit_code": None,
        "started_at": None,
        "duration_ms": 0,
        "log_ref": None,
        "truncated": False,
    }


def _workspace_is_intact(setup: Any, state: Any, phase: str) -> bool:
    legacy = _m()
    fingerprint = getattr(state, "workspace_fingerprint", None)
    if fingerprint is None:
        legacy._mark_infrastructure_error(
            state, f"workspace fingerprint is unavailable before {phase}"
        )
        return False
    try:
        current = _workspace_snapshot(setup.workspace, state.changed_files)
    except (legacy.EvaluationError, OSError, subprocess.SubprocessError) as exc:
        legacy._mark_infrastructure_error(
            state, f"workspace fingerprint failed during {phase}: {exc}"
        )
        return False
    if current != fingerprint:
        legacy._mark_infrastructure_error(
            state, f"applied patch workspace changed during {phase}"
        )
        return False
    return True


def _identity(path: Path) -> tuple[int, int]:
    stat = path.stat(follow_symlinks=False)
    return stat.st_dev, stat.st_ino


def _owned(path: Path, identity: tuple[int, int] | None) -> bool:
    if identity is None or not path.exists():
        return False
    try:
        return _identity(path) == identity
    except OSError:
        return False


def _run_declared_commands(setup: Any, state: Any) -> None:
    legacy = _m()
    deadline = time.monotonic() + setup.request.global_timeout_seconds
    commands = setup.request.commands
    if commands:
        setup.log_directory.parent.mkdir(parents=True, exist_ok=True)
        setup.log_directory.mkdir(mode=0o700)
        state.log_directory_identity = _identity(setup.log_directory)
    for offset, spec in enumerate(commands):
        index = offset + 1
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            state.command_records.extend(
                legacy._skipped_command_record(item) for item in commands[offset:]
            )
            break
        if not _workspace_is_intact(setup, state, f"command {index} preflight"):
            state.command_records.append(_error_command_record(spec))
            state.command_records.extend(
                legacy._skipped_command_record(item)
                for item in commands[offset + 1 :]
            )
            break
        record = _run_command(
            spec,
            sandbox_binary=setup.sandbox_binary,
            workspace=setup.workspace,
            sandbox_home=setup.sandbox_home,
            sandbox_tmp=setup.sandbox_tmp,
            timeout_seconds=min(float(spec.timeout_seconds), remaining),
            log_path=setup.log_directory / f"command-{index:03d}.log",
            max_log_bytes=setup.request.max_log_bytes,
        )
        record["log_ref"] = f"{setup.log_directory.name}/{record['log_ref']}"
        if not _workspace_is_intact(setup, state, f"command {index} readback"):
            record["status"] = "error"
            record["exit_code"] = None
            state.command_records.append(record)
            state.command_records.extend(
                legacy._skipped_command_record(item)
                for item in commands[offset + 1 :]
            )
            break
        state.command_records.append(record)
        if record["status"] == "error":
            legacy._mark_infrastructure_error(
                state, f"sandbox payload did not start for command {index}"
            )
            state.command_records.extend(
                legacy._skipped_command_record(item)
                for item in commands[offset + 1 :]
            )
            break
        if setup.request.fail_fast and record["status"] != "passed":
            state.command_records.extend(
                legacy._skipped_command_record(item)
                for item in commands[offset + 1 :]
            )
            break


def _rollup_status(
    records: list[dict[str, Any]], *, patch_applied: bool, infrastructure_error: bool
) -> str:
    if infrastructure_error or not patch_applied:
        return "error"
    if not records:
        return "incomplete"
    statuses = [record["status"] for record in records]
    if any(status in {"error", "timeout"} for status in statuses):
        return "error"
    if any(status == "failed" for status in statuses):
        return "mixed" if any(status == "passed" for status in statuses) else "failed"
    if any(status == "skipped" for status in statuses):
        return "incomplete"
    if all(status == "passed" for status in statuses):
        return "passed"
    return "mixed"


def _prepare_evaluation(
    request_path: str | Path,
    output_path: str | Path,
    workspace_root: str | Path | None,
) -> Any:
    legacy = _m()
    request = legacy.load_request(request_path)
    legacy._configured_filter_drivers.cache_clear()
    sandbox_binary = _sandbox_binary()
    canonical_repository = Path(
        legacy._git_text(request.repository, "rev-parse", "--show-toplevel")
    ).resolve()
    if canonical_repository != request.repository:
        raise legacy.RequestError("repository must name the exact Git worktree root")
    output = Path(output_path).expanduser().resolve()
    legacy._ensure_outside_repository(output, request.repository, "output")
    if output.exists():
        raise legacy.RequestError(f"output already exists: {output}")
    requested_workspace_root = (
        Path(workspace_root).expanduser().resolve()
        if workspace_root is not None
        else output.parent / ".patch-evaluation-sidecar-workspaces"
    )
    legacy._ensure_outside_repository(
        requested_workspace_root, request.repository, "workspace_root"
    )
    source_head, source_fingerprint, source_branch = legacy._source_snapshot(
        request.repository
    )
    exact_base = legacy._resolve_base_commit(request.repository, request.base_commit)
    if source_head != exact_base:
        source_branch = None
    workspace_id = uuid.uuid4().hex
    workspace = requested_workspace_root / f"{workspace_id}-repository"
    runtime_root = requested_workspace_root / f"{workspace_id}-runtime"
    log_directory = output.parent / f"{output.stem}.{workspace_id}.logs"
    for candidate, label in (
        (workspace, "workspace"),
        (runtime_root, "runtime directory"),
        (log_directory, "log directory"),
    ):
        if candidate.exists():
            raise legacy.RequestError(f"{label} already exists: {candidate}")
    setup = legacy.EvaluationSetup(
        request=request,
        output=output,
        workspace_root=requested_workspace_root,
        workspace_id=workspace_id,
        workspace=workspace,
        log_directory=log_directory,
        source_head_before=source_head,
        source_fingerprint_before=source_fingerprint,
        source_branch=source_branch,
        exact_base=exact_base,
        sandbox_binary=sandbox_binary,
        runtime_root=runtime_root,
        sandbox_home=runtime_root / "home",
        sandbox_tmp=runtime_root / "tmp",
        git_scratch=runtime_root / "git-scratch",
    )
    object.__setattr__(setup, "producer_source_sha256", _producer_digest())
    return setup


def _create_isolated_repository(setup: Any, state: Any) -> None:
    legacy = _m()
    setup.workspace.mkdir(mode=0o700)
    state.workspace_identity = _identity(setup.workspace)
    state.workspace_created = True
    init_result = legacy._git(setup.workspace, "init", "--quiet", check=False)
    if init_result.returncode != 0:
        detail = init_result.stderr.decode("utf-8", errors="replace").strip()
        raise legacy.EvaluationError(
            f"independent repository initialization failed: {detail}"
        )
    pack_path = legacy._write_pack_snapshot(setup)
    legacy._import_pack_snapshot(setup, pack_path)
    checkout_result = legacy._git(
        setup.workspace,
        "checkout",
        "--detach",
        "--force",
        "--quiet",
        setup.exact_base,
        timeout=120,
        check=False,
    )
    if checkout_result.returncode != 0:
        detail = checkout_result.stderr.decode("utf-8", errors="replace").strip()
        raise legacy.EvaluationError(
            f"independent repository checkout failed: {detail}"
        )
    state.isolated = legacy._verify_independent_repository(setup)
    if not state.isolated:
        raise legacy.EvaluationError(
            "independent repository isolation could not be proven"
        )


def _apply_patch(setup: Any, state: Any) -> None:
    legacy = _m()
    legacy._original_apply_patch(setup, state)
    state.workspace_fingerprint = _workspace_snapshot(
        setup.workspace, state.changed_files
    )


def _perform_evaluation(setup: Any, state: Any) -> None:
    legacy = _m()
    setup.workspace_root.mkdir(parents=True, exist_ok=True)
    setup.runtime_root.mkdir(mode=0o700)
    state.runtime_identity = _identity(setup.runtime_root)
    setup.sandbox_home.mkdir(mode=0o700)
    setup.sandbox_tmp.mkdir(mode=0o700)
    setup.git_scratch.mkdir(mode=0o700)
    state.patch_snapshot, state.patch_sha256 = _snapshot_patch(
        setup.request.patch_path, setup.runtime_root
    )
    legacy._create_isolated_repository(setup, state)
    legacy._apply_patch(setup, state)
    legacy._run_declared_commands(setup, state)


def _cleanup_workspace(setup: Any, state: Any) -> None:
    legacy = _m()
    identity = getattr(state, "workspace_identity", None)
    try:
        if _owned(setup.workspace, identity):
            legacy.shutil.rmtree(setup.workspace)
        state.workspace_cleaned = not setup.workspace.exists()
    except OSError as exc:
        state.workspace_cleaned = False
        state.error_detail = state.error_detail or (
            f"independent repository cleanup readback failed: {exc}"
        )
    if not state.workspace_cleaned:
        legacy._mark_infrastructure_error(
            state, "independent repository cleanup could not be proven"
        )


def _cleanup_runtime(setup: Any, state: Any) -> None:
    legacy = _m()
    identity = getattr(state, "runtime_identity", None)
    try:
        if _owned(setup.runtime_root, identity):
            legacy.shutil.rmtree(setup.runtime_root)
    except OSError as exc:
        state.error_detail = state.error_detail or f"runtime cleanup failed: {exc}"
    if setup.runtime_root.exists():
        legacy._mark_infrastructure_error(state, "runtime cleanup could not be proven")


def _cleanup_empty_logs(setup: Any, state: Any) -> None:
    identity = getattr(state, "log_directory_identity", None)
    try:
        if (
            _owned(setup.log_directory, identity)
            and not any(setup.log_directory.iterdir())
        ):
            setup.log_directory.rmdir()
    except OSError:
        return


def _verify_producer_unchanged(setup: Any, state: Any) -> None:
    legacy = _m()
    try:
        unchanged = _producer_digest() == setup.producer_source_sha256
    except OSError as exc:
        unchanged = False
        state.error_detail = state.error_detail or f"producer source readback failed: {exc}"
    if not unchanged:
        legacy._mark_infrastructure_error(
            state, "producer source changed during evaluation"
        )


def _cleanup_evaluation(setup: Any, state: Any) -> None:
    legacy = _m()
    legacy._cleanup_workspace(setup, state)
    legacy._cleanup_patch_snapshot(state)
    legacy._cleanup_runtime(setup, state)
    _cleanup_empty_logs(setup, state)
    legacy._verify_source_unchanged(setup, state)
    _verify_producer_unchanged(setup, state)


def _build_artifact(setup: Any, state: Any) -> dict[str, Any]:
    legacy = _m()
    artifact = legacy._original_build_artifact(setup, state)
    artifact["producer"]["commit"] = setup.producer_source_sha256
    artifact["command_policy"]["network"] = "deny"
    artifact["environment"]["container"] = "bubblewrap-fs-pid-net-rlimit-sandbox"
    return artifact


def _published_artifact_matches(path: Path, expected: Mapping[str, Any]) -> bool:
    try:
        return json.loads(path.read_text(encoding="utf-8")) == expected
    except (OSError, ValueError, TypeError):
        return False


def _cleanup_owned_logs(setup: Any, state: Any) -> None:
    legacy = _m()
    identity = getattr(state, "log_directory_identity", None)
    if _owned(setup.log_directory, identity):
        legacy.shutil.rmtree(setup.log_directory)


def evaluate(
    request_path: str | Path,
    output_path: str | Path,
    *,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    legacy = _m()
    setup = legacy._prepare_evaluation(request_path, output_path, workspace_root)
    state = legacy.EvaluationState()
    try:
        legacy._perform_evaluation(setup, state)
    except (legacy.EvaluationError, OSError, subprocess.SubprocessError) as exc:
        legacy._mark_infrastructure_error(state, str(exc))
    finally:
        legacy._cleanup_evaluation(setup, state)
    artifact = legacy._build_artifact(setup, state)
    try:
        legacy._atomic_write_json(setup.output, artifact)
    except OSError:
        if not _published_artifact_matches(setup.output, artifact):
            _cleanup_owned_logs(setup, state)
            raise
    except Exception:
        _cleanup_owned_logs(setup, state)
        raise
    if state.error_detail:
        print(f"patch-evaluation-sidecar: {state.error_detail}", file=legacy.sys.stderr)
    return {
        "artifact": artifact,
        "output": str(setup.output),
        "workspace_cleaned": state.workspace_cleaned,
        "source_unchanged": state.source_unchanged,
        "error": state.error_detail,
    }


def apply_hardening(legacy: Any, *, wrapper_path: str | Path) -> None:
    global _LEGACY, _WRAPPER_PATH
    _LEGACY = legacy
    _WRAPPER_PATH = Path(wrapper_path)

    legacy._original_sanitized_environment = legacy._sanitized_environment
    legacy._original_apply_patch = legacy._apply_patch
    legacy._original_build_artifact = legacy._build_artifact

    legacy._producer_digest = _producer_digest
    legacy._sanitized_environment = _sanitized_environment
    legacy._sandbox_command_argv = _sandbox_command_argv
    legacy._sandbox_binary = _sandbox_binary
    legacy._snapshot_patch = _snapshot_patch
    legacy._workspace_snapshot = _workspace_snapshot
    legacy._capture_stream = _capture_stream
    legacy._write_command_log = _write_command_log
    legacy._run_command = _run_command
    legacy._run_declared_commands = _run_declared_commands
    legacy._rollup_status = _rollup_status
    legacy._prepare_evaluation = _prepare_evaluation
    legacy._create_isolated_repository = _create_isolated_repository
    legacy._apply_patch = _apply_patch
    legacy._perform_evaluation = _perform_evaluation
    legacy._cleanup_workspace = _cleanup_workspace
    legacy._cleanup_runtime = _cleanup_runtime
    legacy._cleanup_empty_logs = _cleanup_empty_logs
    legacy._cleanup_evaluation = _cleanup_evaluation
    legacy._build_artifact = _build_artifact
    legacy.evaluate = evaluate
