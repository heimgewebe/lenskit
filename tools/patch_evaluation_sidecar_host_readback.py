"""Host-side Git readback hardening for the patch evaluation sidecar.

The command sandbox is untrusted.  It must not be able to prepare Git metadata
that changes what the later host-side provenance readback executes or reads.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Mapping, Sequence


_GIT_MUTATING_SUBCOMMANDS = {
    "add",
    "am",
    "apply",
    "branch",
    "checkout",
    "cherry-pick",
    "clean",
    "commit",
    "config",
    "merge",
    "mv",
    "rebase",
    "reset",
    "restore",
    "revert",
    "rm",
    "stash",
    "switch",
    "tag",
    "update-index",
    "update-ref",
    "worktree",
}


def _producer_digest(legacy: Any, hardening: Any, wrapper_path: Path) -> str:
    digest = hashlib.sha256()
    paths = {
        Path(legacy.__file__).resolve(),
        Path(hardening.__file__).resolve(),
        Path(__file__).resolve(),
        wrapper_path.resolve(),
    }
    for path in sorted(paths, key=str):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _insert_read_only_git_mount(argv: list[str], workspace: Path) -> list[str]:
    git_directory = workspace / ".git"
    if not git_directory.is_dir():
        return argv
    destination = "/workspace/.git"
    for index in range(len(argv) - 2):
        if argv[index : index + 3] == ["--ro-bind", str(git_directory), destination]:
            return argv
    try:
        insertion = argv.index("--chdir")
    except ValueError as exc:
        raise RuntimeError("sandbox argv has no --chdir boundary") from exc
    return [
        *argv[:insertion],
        "--ro-bind",
        str(git_directory),
        destination,
        *argv[insertion:],
    ]


def _git_subcommand(argv: Sequence[str]) -> str | None:
    if not argv or Path(argv[0]).name != "git":
        return None
    index = 1
    while index < len(argv):
        value = argv[index]
        if value in {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}:
            index += 2
            continue
        if value.startswith(("--git-dir=", "--work-tree=", "--namespace=")):
            index += 1
            continue
        if value.startswith("-"):
            index += 1
            continue
        return value
    return None


def apply_host_readback_hardening(
    legacy: Any, hardening: Any, *, wrapper_path: str | Path
) -> None:
    """Install the final boundary overlay after the main hardening overlay."""

    wrapper = Path(wrapper_path)
    original_sandbox_command_argv = hardening._sandbox_command_argv
    original_workspace_snapshot = hardening._workspace_snapshot
    original_run_command = hardening._run_command

    def sandbox_command_argv(
        spec: Any,
        *,
        sandbox_binary: Path,
        workspace: Path,
        sandbox_home: Path,
        sandbox_tmp: Path,
        ready_marker: str | None = None,
    ) -> list[str]:
        argv = original_sandbox_command_argv(
            spec,
            sandbox_binary=sandbox_binary,
            workspace=workspace,
            sandbox_home=sandbox_home,
            sandbox_tmp=sandbox_tmp,
            ready_marker=ready_marker,
        )
        return _insert_read_only_git_mount(argv, workspace)

    def workspace_snapshot(
        workspace: Path, changed_files: Sequence[Mapping[str, Any]]
    ) -> str:
        # A command may have changed local filter configuration.  Never reuse the
        # pre-command inventory when constructing host-side Git argv.
        legacy._configured_filter_drivers.cache_clear()
        return original_workspace_snapshot(workspace, changed_files)

    def run_command(*args: Any, **kwargs: Any) -> dict[str, Any]:
        spec = args[0] if args else kwargs.get("spec")
        record = original_run_command(*args, **kwargs)
        if (
            spec is not None
            and record.get("status") == "failed"
            and _git_subcommand(spec.argv) in _GIT_MUTATING_SUBCOMMANDS
        ):
            # The read-only Git metadata mount intentionally rejects the mutation.
            # Preserve this as a policy/infrastructure error rather than blaming
            # the evaluated patch as an ordinary test failure.
            record["status"] = "error"
            record["exit_code"] = None
        return record

    def producer_digest() -> str:
        return _producer_digest(legacy, hardening, wrapper)

    hardening._sandbox_command_argv = sandbox_command_argv
    legacy._sandbox_command_argv = sandbox_command_argv
    hardening._workspace_snapshot = workspace_snapshot
    legacy._workspace_snapshot = workspace_snapshot
    hardening._run_command = run_command
    legacy._run_command = run_command
    hardening._producer_digest = producer_digest
    legacy._producer_digest = producer_digest
