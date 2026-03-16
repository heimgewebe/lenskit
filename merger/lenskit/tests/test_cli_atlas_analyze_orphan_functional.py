import json
import pytest
import datetime
from pathlib import Path
from merger.lenskit.cli.cmd_atlas import run_atlas_analyze
import argparse

def test_analyze_orphans_functional(tmp_path: Path, monkeypatch, capsys):
    # Setup mock registry and data
    registry_path = tmp_path / "atlas/registry/atlas_registry.sqlite"
    registry_path.parent.mkdir(parents=True)

    # Create an empty sqlite db
    import sqlite3
    conn = sqlite3.connect(registry_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS snapshots (
        snapshot_id TEXT PRIMARY KEY,
        machine_id TEXT NOT NULL,
        root_id TEXT NOT NULL,
        scan_config_hash TEXT,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL,
        inventory_ref TEXT,
        dirs_ref TEXT,
        stats_ref TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS roots (
        root_id TEXT PRIMARY KEY,
        machine_id TEXT NOT NULL,
        root_kind TEXT NOT NULL,
        root_value TEXT NOT NULL,
        filesystem TEXT,
        mountpoint TEXT,
        label TEXT
    )''')

    root_val = tmp_path / "test_root"
    root_val.mkdir()

    # Add files to live root
    (root_val / "file1.txt").write_text("live and in snapshot")
    (root_val / "file2_orphan.txt").write_text("live only")

    conn.execute("INSERT INTO roots (root_id, machine_id, root_kind, root_value) VALUES (?, ?, ?, ?)",
                 ("root_1", "mach_1", "abs_path", str(root_val)))

    conn.execute("INSERT INTO snapshots (snapshot_id, machine_id, root_id, created_at, status, inventory_ref) VALUES (?, ?, ?, ?, ?, ?)",
                 ("snap_1", "mach_1", "root_1", "2024-01-01T00:00:00Z", "complete", "snap_1_inv.jsonl"))
    conn.commit()
    conn.close()

    inv_file = tmp_path / "atlas" / "snap_1_inv.jsonl"
    inv_file.parent.mkdir(exist_ok=True)

    # Snapshot contains file1.txt and file3_dead.txt
    with inv_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"rel_path": "file1.txt"}) + "\n")
        f.write(json.dumps({"rel_path": "file3_dead.txt"}) + "\n")

    def mock_resolve_base(p):
        return tmp_path / "atlas"

    def mock_resolve_ref(base, ref):
        return base / ref

    monkeypatch.setattr("merger.lenskit.cli.cmd_atlas.Path.resolve", lambda s: registry_path if "atlas_registry" in str(s) else s)
    import merger.lenskit.atlas.paths as atlas_paths
    monkeypatch.setattr(atlas_paths, "resolve_atlas_base_dir", mock_resolve_base)
    monkeypatch.setattr(atlas_paths, "resolve_artifact_ref", mock_resolve_ref)

    args = argparse.Namespace(analyze_command="orphans", snapshot_id="snap_1")
    exit_code = run_atlas_analyze(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    report = json.loads(captured.out)

    assert report["snapshot_id"] == "snap_1"
    assert report["orphan_count"] == 1
    assert report["dead_file_count"] == 1
    assert "file2_orphan.txt" in report["orphans"]
    assert "file3_dead.txt" in report["dead_files"]
