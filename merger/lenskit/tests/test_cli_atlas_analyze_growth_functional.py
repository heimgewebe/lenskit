import json
import os
import subprocess
import sys
from pathlib import Path

def test_cli_atlas_analyze_growth_functional(tmp_path, monkeypatch):
    registry_path = tmp_path / "atlas/registry/atlas_registry.sqlite"
    atlas_base = tmp_path / "atlas"
    atlas_base.mkdir(parents=True)

    from merger.lenskit.atlas.registry import AtlasRegistry

    with AtlasRegistry(registry_path) as reg:
        reg.register_machine("machine-a", "host-a")
        reg.register_root("root-src", "machine-a", "abs_path", "/src")
        reg.register_root("root-tgt", "machine-a", "abs_path", "/tgt")

        snap1 = "snap_src_1"
        snap2 = "snap_tgt_1"

        reg.create_snapshot(snap1, "machine-a", "root-src", "hash1", "complete")
        reg.create_snapshot(snap2, "machine-a", "root-tgt", "hash2", "complete")

        inv_src_path = atlas_base / "inv_src.jsonl"
        with open(inv_src_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"rel_path": "file1.txt", "size_bytes": 100, "mtime": "2024-01-01"}) + "\n")
            f.write(json.dumps({"rel_path": "file2.txt", "size_bytes": 200, "mtime": "2024-01-01"}) + "\n")

        inv_tgt_path = atlas_base / "inv_tgt.jsonl"
        with open(inv_tgt_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"rel_path": "file1.txt", "size_bytes": 100, "mtime": "2024-01-01"}) + "\n")
            f.write(json.dumps({"rel_path": "file2.txt", "size_bytes": 200, "mtime": "2024-01-01"}) + "\n")
            f.write(json.dumps({"rel_path": "file3.txt", "size_bytes": 300, "mtime": "2024-01-01"}) + "\n")
            f.write(json.dumps({"rel_path": "file4.txt", "size_bytes": 400, "mtime": "2024-01-02"}) + "\n")

        reg.update_snapshot_artifacts(snap1, {"inventory": "inv_src.jsonl"})
        reg.update_snapshot_artifacts(snap2, {"inventory": "inv_tgt.jsonl"})

    monkeypatch.chdir(tmp_path)

    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    env = os.environ.copy()
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{repo_root}{os.pathsep}{existing_pp}" if existing_pp else str(repo_root)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "merger.lenskit.cli.main",
            "atlas",
            "analyze",
            "growth",
            "snap_src_1",
            "snap_tgt_1"
        ],
        capture_output=True,
        text=True,
        env=env
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"

    output_json = json.loads(result.stdout.strip())

    assert output_json["source_snapshot"] == "snap_src_1"
    assert output_json["target_snapshot"] == "snap_tgt_1"

    assert output_json["metrics"]["source_size_bytes"] == 300
    assert output_json["metrics"]["target_size_bytes"] == 1000
    assert output_json["metrics"]["size_delta_bytes"] == 700

    assert output_json["metrics"]["source_file_count"] == 2
    assert output_json["metrics"]["target_file_count"] == 4
    assert output_json["metrics"]["file_count_delta"] == 2

    assert output_json["data_basis"]["source_machine"] == "machine-a"
    assert output_json["data_basis"]["source_root"] == "root-src"
    assert output_json["data_basis"]["target_machine"] == "machine-a"
    assert output_json["data_basis"]["target_root"] == "root-tgt"

    assert "Does not track historical trends" in output_json["limitations"][0]
