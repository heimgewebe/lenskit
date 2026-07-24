from __future__ import annotations

import argparse
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "patch_evaluation_systemd_runner.py"
SPEC = importlib.util.spec_from_file_location("patch_evaluation_systemd_runner", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def _limits() -> runner.Limits:
    return runner.Limits(
        workspace_max_bytes=2 * 1024**3,
        memory_max_bytes=4 * 1024**3,
        memory_swap_max_bytes=0,
        cpu_quota_percent=200,
        tasks_max=256,
        runtime_max_seconds=30,
        io_read_bandwidth_bps=1000,
        io_write_bandwidth_bps=500,
    )


def _prepared(tmp_path: Path) -> runner.Prepared:
    staging = tmp_path / "staging"
    staging.mkdir()
    request = staging / "request.json"
    patch = staging / "patch.diff"
    request.write_text("{}\n", encoding="utf-8")
    patch.write_text("diff\n", encoding="utf-8")
    output_parent = tmp_path / "out"
    output_parent.mkdir()
    return runner.Prepared(
        run_id="a" * 32,
        unit=f"repoground-patch-evaluation-{'a' * 32}.service",
        request_snapshot=request,
        patch_snapshot=patch,
        staging_root=staging,
        staging_identity=runner._identity(staging),
        output=output_parent / "evaluation.json",
        receipt=output_parent / "receipt.json",
        source_repository=tmp_path / "source",
        output_parent=output_parent,
        device_paths=(Path("/dev/sda"),),
        request_sha256="1" * 64,
        patch_sha256="2" * 64,
    )


def test_limits_derive_aggregate_cpu_and_io_budgets() -> None:
    limits = _limits()
    assert limits.cpu_time_max_usec == 60_000_000
    assert limits.io_read_max_bytes == 30_000
    assert limits.io_write_max_bytes == 15_000


def test_parse_limits_rejects_bool_and_out_of_range() -> None:
    args = argparse.Namespace(
        workspace_max_bytes=True,
        memory_max_bytes=4 * 1024**3,
        memory_swap_max_bytes=0,
        cpu_quota_percent=200,
        tasks_max=256,
        runtime_max_seconds=30,
        io_read_bandwidth_bps=1000,
        io_write_bandwidth_bps=500,
    )
    with pytest.raises(runner.RunnerError, match="workspace_max_bytes"):
        runner._parse_limits(args)


def test_copy_snapshot_binds_copied_bytes_and_mode(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.write_bytes(b"payload")
    digest = runner._copy_snapshot(source, target, max_bytes=7)
    assert digest == __import__("hashlib").sha256(b"payload").hexdigest()
    assert target.read_bytes() == b"payload"
    assert stat.S_IMODE(target.stat().st_mode) == 0o400


def test_copy_snapshot_enforces_limit_during_copy(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.write_bytes(b"12345678")
    with pytest.raises(runner.RunnerError, match="snapshot exceeds"):
        runner._copy_snapshot(source, target, max_bytes=7)


def test_parse_show_is_exact_key_value() -> None:
    assert runner._parse_show(b"Result=success\nExecMainStatus=1\nempty=\n") == {
        "Result": "success",
        "ExecMainStatus": "1",
        "empty": "",
    }


def test_unit_argv_contains_aggregate_limits_and_namespace_policy(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    prepared.source_repository.mkdir()
    argv = runner._unit_argv(
        prepared,
        _limits(),
        Path("/repo/tools/patch_evaluation_sidecar.py"),
        Path("/usr/bin/python3"),
        Path("/usr/bin/systemd-run"),
        Path("/usr/bin/env"),
    )
    joined = "\n".join(argv)
    assert "--user" in argv
    assert "--wait" not in argv
    assert "MemoryMax=4294967296" in joined
    assert "MemorySwapMax=0" in joined
    assert "CPUQuota=200%" in joined
    assert "TasksMax=256" in joined
    assert "RuntimeMaxSec=30" in joined
    assert "TemporaryFileSystem=/tmp:rw,size=2147483648,mode=0700" in joined
    assert "PrivateNetwork=yes" in joined
    assert "ProtectSystem=strict" in joined
    assert "ReadOnlyPaths=" + str(prepared.source_repository) in joined
    assert "ReadOnlyPaths=" + str(prepared.staging_root) in joined
    assert (
        "BindPaths=" + str(prepared.output_parent) + ":/run/repoground-output"
        in joined
    )
    assert "IOReadBandwidthMax=/dev/sda 1000" in joined
    assert "IOWriteBandwidthMax=/dev/sda 500" in joined
    assert "-i" in argv
    assert "PYTHONNOUSERSITE=1" in argv
    assert argv[-2:] == ["--workspace-root", "/tmp/repoground-sidecar-workspaces"]


def test_receipt_preserves_sidecar_failure_as_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = _prepared(tmp_path)
    monkeypatch.setattr(runner, "_producer_digest", lambda sidecar: "sha256:" + "a" * 64)
    value = runner._receipt(
        prepared,
        _limits(),
        {"Result": "exit-code", "InvocationID": "abc", "ControlGroup": "/user.slice/x", "ExecMainStatus": "1"},
        {"kind": "repobrief.patch_evaluation", "version": "v1", "status": "failed"},
        "b" * 64,
        1,
        True,
        None,
        Path("/sidecar"),
    )
    assert value["status"] == "failed"
    assert value["artifact"]["status"] == "failed"
    assert value["runner"]["systemd_run_returncode"] == 1


def test_receipt_promotes_oom_to_infrastructure_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = _prepared(tmp_path)
    monkeypatch.setattr(runner, "_producer_digest", lambda sidecar: "sha256:" + "a" * 64)
    value = runner._receipt(
        prepared,
        _limits(),
        {"Result": "oom-kill", "InvocationID": "abc", "ControlGroup": "/user.slice/x"},
        {"status": "passed"},
        "b" * 64,
        137,
        True,
        None,
        Path("/sidecar"),
    )
    assert value["status"] == "error"


def test_receipt_requires_cleanup_proof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = _prepared(tmp_path)
    monkeypatch.setattr(runner, "_producer_digest", lambda sidecar: "sha256:" + "a" * 64)
    value = runner._receipt(
        prepared,
        _limits(),
        {"Result": "success", "InvocationID": "abc", "ControlGroup": "/user.slice/x"},
        {"status": "passed"},
        "b" * 64,
        0,
        False,
        None,
        Path("/sidecar"),
    )
    assert value["status"] == "error"


def test_owned_refuses_replaced_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "owned"
    directory.mkdir()
    identity = runner._identity(directory)
    monkeypatch.setattr(runner, "_identity", lambda path: (identity[0], identity[1] + 1))
    assert runner._owned(directory, identity) is False


def test_atomic_json_refuses_existing_destination(tmp_path: Path) -> None:
    destination = tmp_path / "receipt.json"
    destination.write_text("foreign\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        runner._atomic_json(destination, {"status": "passed"})
    assert destination.read_text(encoding="utf-8") == "foreign\n"


def test_device_path_requires_block_device(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "target"
    target.write_text("x", encoding="utf-8")
    monkeypatch.setattr(runner.os, "major", lambda value: 8)
    monkeypatch.setattr(runner.os, "minor", lambda value: 1)
    original_exists = Path.exists

    def fake_exists(path: Path) -> bool:
        if str(path) == "/dev/block/8:1":
            return True
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(Path, "resolve", lambda self: target if str(self) == "/dev/block/8:1" else self)
    with pytest.raises(runner.RunnerError, match="not a block device"):
        runner._device_path(target)


def test_prepare_snapshots_patch_and_rewrites_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    patch = tmp_path / "change.diff"
    patch.write_text("diff\n", encoding="utf-8")
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"repository": str(repository), "patch_path": str(patch)}), encoding="utf-8")
    output_parent = tmp_path / "out"
    output_parent.mkdir()
    output = output_parent / "evaluation.json"
    receipt = output_parent / "receipt.json"
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    runtime.chmod(0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    monkeypatch.setattr(runner, "_device_path", lambda path: Path("/dev/sda"))
    prepared = runner._prepare(request, output, receipt)
    rewritten = json.loads(prepared.request_snapshot.read_text(encoding="utf-8"))
    assert rewritten["repository"] == str(repository)
    assert rewritten["patch_path"] == str(prepared.patch_snapshot)
    assert prepared.patch_snapshot.read_text(encoding="utf-8") == "diff\n"
    assert stat.S_IMODE(prepared.staging_root.stat().st_mode) == 0o700
    assert prepared.device_paths == (Path("/dev/sda"),)


def test_prepare_refuses_receipt_inside_source_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    patch = tmp_path / "change.diff"
    patch.write_text("diff\n", encoding="utf-8")
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"repository": str(repository), "patch_path": str(patch)}), encoding="utf-8")
    monkeypatch.setattr(runner, "_device_path", lambda path: Path("/dev/sda"))
    with pytest.raises(runner.RunnerError, match="receipt must stay outside"):
        runner._prepare(request, tmp_path / "out.json", repository / "receipt.json")


def test_controllers_fail_closed_when_cgroup_v2_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    with pytest.raises(runner.RunnerError, match="cgroup v2"):
        runner._controllers()


def test_example_receipt_conforms_to_schema() -> None:
    import jsonschema

    schema = json.loads(
        (ROOT / "merger" / "repoground" / "contracts" / "patch-evaluation-runner-receipt.v1.schema.json").read_text(encoding="utf-8")
    )
    example = json.loads(
        (ROOT / "merger" / "repoground" / "contracts" / "examples" / "patch-evaluation-runner-receipt.v1.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft7Validator(schema).validate(example)
