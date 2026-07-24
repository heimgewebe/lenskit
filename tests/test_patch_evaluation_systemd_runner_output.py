from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
MODULE = TOOLS / "patch_evaluation_systemd_runner.py"
SPEC = importlib.util.spec_from_file_location(
    "patch_evaluation_systemd_runner_output_cases", MODULE
)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def test_argv_discards_process_output_before_payload_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner,
        "_base_argv",
        lambda run, limits, sidecar: [
            "/usr/bin/systemd-run",
            "--property=PrivateNetwork=yes",
            "--",
            "/usr/bin/env",
        ],
    )

    argv = runner._argv(None, None, Path("/sidecar"))
    boundary = argv.index("--")

    assert "--property=StandardOutput=null" in argv[:boundary]
    assert "--property=StandardError=null" in argv[:boundary]
    assert argv[boundary + 1 :] == ["/usr/bin/env"]


def test_policy_rejects_journal_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner,
        "_base_policy",
        lambda unit, run, limits: (_ for _ in ()).throw(
            AssertionError("base policy must not run")
        ),
    )

    with pytest.raises(runner.RunnerError, match="StandardOutput"):
        runner._policy(
            {"StandardOutput": "journal", "StandardError": "null"},
            None,
            None,
        )


def test_policy_accepts_null_output_and_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = ("a" * 64, {"systemd": {}, "cgroup": {}})
    monkeypatch.setattr(
        runner,
        "_base_policy",
        lambda unit, run, limits: expected,
    )

    assert (
        runner._policy(
            {"StandardOutput": "null", "StandardError": "null"},
            None,
            None,
        )
        == expected
    )


def test_atomic_receipt_accepts_linked_payload_after_directory_fsync_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "receipt.json"
    value = {"status": "passed", "nested": {"proof": True}}
    original_fsync = runner.os.fsync
    calls = 0

    def ambiguous_fsync(descriptor: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("forced directory fsync ambiguity")
        original_fsync(descriptor)

    monkeypatch.setattr(runner.os, "fsync", ambiguous_fsync)

    runner._atomic(output, value)

    assert json.loads(output.read_text(encoding="utf-8")) == value
