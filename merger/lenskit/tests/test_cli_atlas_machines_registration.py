import pytest
import argparse
import socket
import os
from pathlib import Path

from merger.lenskit.cli.cmd_atlas import run_atlas_scan
from merger.lenskit.atlas.registry import AtlasRegistry

def test_atlas_scan_explicit_machine_and_hostname(tmp_path: Path, monkeypatch, capsys):
    # Change current working directory to tmp_path to isolate registry creation
    monkeypatch.chdir(tmp_path)

    # Set up arguments for run_atlas_scan
    scan_root = tmp_path / "scan_target"
    scan_root.mkdir()
    (scan_root / "test_file.txt").write_text("hello")

    args = argparse.Namespace(
        path=str(scan_root),
        exclude=None,
        no_default_excludes=False,
        max_file_size=None,
        no_max_file_size=False,
        depth=100,
        limit=200000,
        mode="inventory",
        incremental=False,
        machine_id="test-machine-id-123",
        hostname="test-hostname-123"
    )

    # Run the scan
    exit_code = run_atlas_scan(args)
    assert exit_code == 0

    # Verify the registry
    registry_path = Path("atlas/registry/atlas_registry.sqlite").resolve()
    assert registry_path.exists()

    with AtlasRegistry(registry_path) as registry:
        machine = registry.get_machine("test-machine-id-123")
        assert machine is not None
        assert machine["machine_id"] == "test-machine-id-123"
        assert machine["hostname"] == "test-hostname-123"

def test_atlas_scan_default_machine_and_hostname(tmp_path: Path, monkeypatch, capsys):
    # Change current working directory to tmp_path to isolate registry creation
    monkeypatch.chdir(tmp_path)

    # clear env var
    monkeypatch.delenv("ATLAS_MACHINE_ID", raising=False)

    scan_root = tmp_path / "scan_target"
    scan_root.mkdir()

    args = argparse.Namespace(
        path=str(scan_root),
        exclude=None,
        no_default_excludes=False,
        max_file_size=None,
        no_max_file_size=False,
        depth=100,
        limit=200000,
        mode="inventory",
        incremental=False,
        machine_id=None,
        hostname=None
    )

    # Run the scan
    exit_code = run_atlas_scan(args)
    assert exit_code == 0

    expected_hostname = socket.gethostname().strip().lower()

    registry_path = Path("atlas/registry/atlas_registry.sqlite").resolve()
    with AtlasRegistry(registry_path) as registry:
        machine = registry.get_machine(expected_hostname)
        assert machine is not None
        assert machine["machine_id"] == expected_hostname
        assert machine["hostname"] == expected_hostname

def test_atlas_scan_machine_registration_conflict(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    scan_root = tmp_path / "scan_target"
    scan_root.mkdir()

    # Preregister m1 with host-a
    registry_path = Path("atlas/registry/atlas_registry.sqlite").resolve()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with AtlasRegistry(registry_path) as registry:
        registry.register_machine("m1", "host-a")

    args = argparse.Namespace(
        path=str(scan_root),
        exclude=None,
        no_default_excludes=False,
        max_file_size=None,
        no_max_file_size=False,
        depth=100,
        limit=200000,
        mode="inventory",
        incremental=False,
        machine_id="m1",
        hostname="host-b"
    )

    exit_code = run_atlas_scan(args)
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "already registered with a different hostname" in captured.err

def test_atlas_scan_machine_registration_case_insensitivity(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    scan_root = tmp_path / "scan_target"
    scan_root.mkdir()

    registry_path = Path("atlas/registry/atlas_registry.sqlite").resolve()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with AtlasRegistry(registry_path) as registry:
        registry.register_machine("m1", "host-a")

    args = argparse.Namespace(
        path=str(scan_root),
        exclude=None,
        no_default_excludes=False,
        max_file_size=None,
        no_max_file_size=False,
        depth=100,
        limit=200000,
        mode="inventory",
        incremental=False,
        machine_id="M1",
        hostname="HOST-A"
    )

    # Should succeed because it normalizes to m1 and host-a, which match the existing record
    exit_code = run_atlas_scan(args)
    assert exit_code == 0
