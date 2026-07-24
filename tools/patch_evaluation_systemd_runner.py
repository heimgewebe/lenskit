#!/usr/bin/env python3
"""Run the external Patch Evaluation Sidecar in a bounded systemd user unit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import patch_evaluation_systemd_runner_support as _support

KIND = _support.KIND
VERSION = _support.VERSION
AUTHORITY = _support.AUTHORITY
PRODUCER_NAME = _support.PRODUCER_NAME
PRODUCER_VERSION = _support.PRODUCER_VERSION
_REQUIRED_CONTROLLERS = _support._REQUIRED_CONTROLLERS
_RESOURCE_RESULTS = _support._RESOURCE_RESULTS
_ARTIFACT_STATUSES = frozenset({"passed", "failed", "mixed", "error", "incomplete"})
RunnerError = _support.RunnerError
Limits = _support.Limits
Run = _support.Run
_limits = _support._limits
_tool = _support._tool
_sha = _support._sha
_owned = _support._owned
_json = _support._json
_prepare = _support._prepare
_argv = _support._argv
_run = _support._run
_show = _support._show
_wait = _support._wait
_num = _support._num
_policy = _support._policy


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
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
        os.link(temporary, path)
        temporary.unlink()
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _producer(sidecar: Path) -> str:
    digest = hashlib.sha256()
    paths = {
        Path(__file__).resolve(),
        Path(_support.__file__).resolve(),
        sidecar.resolve(),
    }
    for path in sorted(paths, key=str):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _unit_absent(systemctl: Path, unit: str, timeout: float = 3) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        probe = _run(
            (
                str(systemctl),
                "--user",
                "show",
                unit,
                "--property",
                "LoadState",
            ),
            20,
        )
        if b"LoadState=not-found" in probe.stdout:
            return True
        time.sleep(0.05)
    return False


def _cleanup_transient(
    systemctl: Path,
    run: Run,
    unit: Mapping[str, str],
) -> tuple[bool, str | None]:
    invocation = unit.get("InvocationID")
    if not invocation:
        return False, "unit InvocationID is unavailable; cleanup refused"
    try:
        before = _show(systemctl, run.unit)
    except (OSError, subprocess.SubprocessError, RunnerError) as exc:
        return False, f"unit cleanup readback failed: {exc}"
    if before.get("InvocationID") != invocation:
        return False, "unit InvocationID changed; cleanup refused"
    stopped = _run((str(systemctl), "--user", "stop", run.unit), 20)
    if _unit_absent(systemctl, run.unit):
        return True, None
    reset = _run((str(systemctl), "--user", "reset-failed", run.unit), 20)
    if _unit_absent(systemctl, run.unit):
        return True, None
    details = " | ".join(
        item
        for item in (
            stopped.stderr.decode(errors="replace").strip(),
            reset.stderr.decode(errors="replace").strip(),
        )
        if item
    )
    return False, details or "transient unit cleanup could not be proven"


def _recover_unit(systemctl: Path, run: Run) -> dict[str, str]:
    try:
        return _show(systemctl, run.unit)
    except (OSError, subprocess.SubprocessError, RunnerError):
        return {}


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if platform.system() != "Linux":
        raise RunnerError("Linux is required")
    controllers = Path("/sys/fs/cgroup/cgroup.controllers")
    available = (
        frozenset(controllers.read_text(encoding="ascii").split())
        if controllers.is_file()
        else frozenset()
    )
    missing = _REQUIRED_CONTROLLERS - available
    if missing:
        raise RunnerError(
            "required cgroup-v2 controllers are unavailable: "
            + ", ".join(sorted(missing))
        )
    limits = _limits(args)
    systemctl = _tool("systemctl")
    manager_probe = _run((str(systemctl), "--user", "show-environment"), 10)
    if manager_probe.returncode:
        raise RunnerError("systemd user manager is unavailable")
    sidecar = Path(args.sidecar).expanduser().resolve()
    if not sidecar.is_file():
        raise RunnerError("Sidecar is unavailable")
    producer = _producer(sidecar)
    run = _prepare(Path(args.request), Path(args.output), Path(args.receipt))

    unit: dict[str, str] = {}
    artifact: Mapping[str, Any] | None = None
    artifact_sha: str | None = None
    policy_hash: str | None = None
    policy_readback: dict[str, Any] | None = None
    cleanup = False
    error: str | None = None
    launcher: int | None = None
    launched = False

    try:
        probe = _run(
            (
                str(systemctl),
                "--user",
                "show",
                run.unit,
                "--property",
                "LoadState",
            ),
            20,
        )
        if b"LoadState=not-found" not in probe.stdout:
            raise RunnerError("transient unit absence could not be proven")
        launch = _run(_argv(run, limits, sidecar), 30)
        launcher = launch.returncode
        if launcher:
            detail = launch.stderr.decode(errors="replace").strip()
            raise RunnerError(detail or "unit launch failed")
        launched = True
        unit = _wait(systemctl, run.unit, limits.runtime)
        result = unit.get("Result")
        if result in _RESOURCE_RESULTS:
            raise RunnerError(f"systemd classified unit as {result}")
        if result not in {"success", "exit-code"}:
            raise RunnerError(f"unsupported terminal systemd result: {result}")
        policy_hash, policy_readback = _policy(unit, run, limits)
        if _sha(run.source_request) != run.source_request_sha256:
            raise RunnerError("source request changed during evaluation")
        if (
            _sha(run.request) != run.effective_request_sha256
            or _sha(run.patch) != run.patch_sha256
            or stat.S_IMODE(run.request.stat().st_mode) != 0o400
            or stat.S_IMODE(run.patch.stat().st_mode) != 0o400
        ):
            raise RunnerError("immutable input snapshot changed")
        if _producer(sidecar) != producer:
            raise RunnerError("producer source changed")
        if not _owned(run.output.parent, run.output_identity):
            raise RunnerError("persistent output root identity changed")
        artifact = _json(run.output, 16 * 1024**2)
        artifact_sha = _sha(run.output)
        if (
            artifact.get("kind") != "repobrief.patch_evaluation"
            or artifact.get("version") != "v1"
        ):
            raise RunnerError("Sidecar artifact kind or version is invalid")
        if artifact.get("status") not in _ARTIFACT_STATUSES:
            raise RunnerError("Sidecar artifact status is invalid")
    except (OSError, ValueError, subprocess.SubprocessError, RunnerError) as exc:
        error = str(exc)
    finally:
        if launched and not unit:
            unit = _recover_unit(systemctl, run)
        if launched:
            cleanup, cleanup_error = _cleanup_transient(systemctl, run, unit)
            if cleanup_error:
                error = error or cleanup_error
        if _owned(run.staging, run.staging_identity):
            try:
                shutil.rmtree(run.staging)
            except OSError as exc:
                error = error or f"staging cleanup failed: {exc}"
        if run.staging.exists():
            error = error or "staging cleanup could not be proven"
        if launched and not cleanup:
            error = error or "transient unit cleanup could not be proven"

    artifact_status = artifact.get("status") if artifact else None
    status = "error"
    if (
        error is None
        and cleanup
        and policy_hash is not None
        and artifact_status in _ARTIFACT_STATUSES
        and unit.get("Result") in {"success", "exit-code"}
    ):
        status = str(artifact_status)
    devices = len(run.devices)
    value = {
        "kind": KIND,
        "version": VERSION,
        "authority": AUTHORITY,
        "producer": {
            "name": PRODUCER_NAME,
            "version": PRODUCER_VERSION,
            "commit": producer,
        },
        "created_at": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "input": {
            "source_request_sha256": run.source_request_sha256,
            "effective_request_sha256": run.effective_request_sha256,
            "patch_sha256": run.patch_sha256,
        },
        "runner": {
            "mode": "systemd-user-transient-service",
            "unit": run.unit,
            "invocation_id": unit.get("InvocationID"),
            "control_group": unit.get("ControlGroup"),
            "systemd_result": unit.get("Result"),
            "exec_main_code": unit.get("ExecMainCode"),
            "exec_main_status": _num(unit.get("ExecMainStatus")),
            "launcher_returncode": launcher,
            "cleanup_proven": cleanup,
            "policy_verified": policy_hash is not None,
            "policy_readback_sha256": policy_hash,
            "policy_readback": policy_readback,
        },
        "policy": {
            "workspace_max_bytes": limits.workspace,
            "memory_max_bytes": limits.memory,
            "memory_swap_max_bytes": limits.swap,
            "cpu_quota_percent": limits.cpu_percent,
            "cpu_time_max_usec": limits.cpu_time_usec,
            "tasks_max": limits.tasks,
            "runtime_max_seconds": limits.runtime,
            "io_device_count": devices,
            "io_read_bandwidth_per_device_bps": limits.read_bps,
            "io_write_bandwidth_per_device_bps": limits.write_bps,
            "io_read_total_max_bytes": limits.read_total(devices),
            "io_write_total_max_bytes": limits.write_total(devices),
            "network": "deny",
            "input_snapshot": "read-only",
            "persistent_write_root": str(run.output.parent),
            "io_devices": [str(item) for item in run.devices],
        },
        "accounting": {
            "cpu_usage_nsec": _num(unit.get("CPUUsageNSec")),
            "memory_peak_bytes": _num(unit.get("MemoryPeak")),
            "memory_current_bytes": _num(unit.get("MemoryCurrent")),
            "tasks_current": _num(unit.get("TasksCurrent")),
            "io_read_bytes": _num(unit.get("IOReadBytes")),
            "io_write_bytes": _num(unit.get("IOWriteBytes")),
        },
        "artifact": {
            "path": str(run.output),
            "sha256": artifact_sha,
            "status": artifact_status,
        },
        "status": status,
        "error": error,
        "does_not_establish": [
            "correctness",
            "test_sufficiency",
            "security_correctness",
            "merge_readiness",
            "merge_authorization",
            "microvm_equivalence",
        ],
    }
    if not _owned(run.output.parent, run.output_identity):
        raise RunnerError("persistent output root identity changed; receipt refused")
    _atomic(run.receipt, value)
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument(
        "--sidecar",
        default=str(
            Path(__file__).resolve().with_name("patch_evaluation_sidecar.py")
        ),
    )
    parser.add_argument(
        "--workspace-max-bytes",
        type=int,
        default=2 * 1024**3,
    )
    parser.add_argument(
        "--memory-max-bytes",
        type=int,
        default=4 * 1024**3,
    )
    parser.add_argument("--memory-swap-max-bytes", type=int, default=0)
    parser.add_argument("--cpu-quota-percent", type=int, default=200)
    parser.add_argument("--tasks-max", type=int, default=256)
    parser.add_argument("--runtime-max-seconds", type=int, default=1800)
    parser.add_argument(
        "--io-read-bandwidth-bps",
        type=int,
        default=100 * 1024**2,
    )
    parser.add_argument(
        "--io-write-bandwidth-bps",
        type=int,
        default=50 * 1024**2,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        value = execute(args)
    except RunnerError as exc:
        print(f"patch-evaluation-systemd-runner: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": value["status"],
                "receipt": str(Path(args.receipt).expanduser().resolve()),
                "unit": value["runner"]["unit"],
            },
            sort_keys=True,
        )
    )
    return 0 if value["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
