import os
import tempfile
import json
from pathlib import Path
from merger.lenskit.atlas.paths import resolve_atlas_base_dir, resolve_snapshot_dir, resolve_artifact_ref
from merger.lenskit.atlas.registry import AtlasRegistry
from merger.lenskit.atlas.diff import compute_snapshot_delta

def test_canonical_paths():
    """Test that resolving the base dir is independent of CWD if registry is given."""
    registry_path = Path("/tmp/fixed_atlas/registry/atlas_registry.sqlite")

    # Store old cwd
    old_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as temp_cwd:
            os.chdir(temp_cwd)
            # The base directory should be calculated from the absolute registry path
            atlas_base = resolve_atlas_base_dir(registry_path)
            assert atlas_base == Path("/tmp/fixed_atlas").resolve()

            # Artifact resolving
            rel_ref = "machines/m1/roots/r1/snapshots/s1/inventory.jsonl"
            resolved_ref = resolve_artifact_ref(atlas_base, rel_ref)
            assert resolved_ref == Path("/tmp/fixed_atlas/machines/m1/roots/r1/snapshots/s1/inventory.jsonl").resolve()

            # Snapshot resolving
            snap_dir = resolve_snapshot_dir(atlas_base, "m1", "r1", "s1")
            assert snap_dir == Path("/tmp/fixed_atlas/machines/m1/roots/r1/snapshots/s1").resolve()

    finally:
        os.chdir(old_cwd)

def test_diff_cwd_independence():
    """Test that computing a diff uses canonical paths and ignores the process CWD."""
    old_cwd = os.getcwd()

    with tempfile.TemporaryDirectory() as real_base, tempfile.TemporaryDirectory() as some_cwd:
        real_base_path = Path(real_base)
        registry_path = real_base_path / "registry" / "atlas_registry.sqlite"
        registry_path.parent.mkdir(parents=True)

        # We start in the real base to set things up
        os.chdir(real_base)

        # Setup registry and some dummy snapshot data
        registry = AtlasRegistry(registry_path)
        machine_id = "test_machine"
        root_id = "test_root"

        registry.register_machine(machine_id, "testhost")
        registry.register_root(root_id, machine_id, "abs_path", "/fake")

        # Snapshot 1
        snap1_id = "snap1"
        registry.create_snapshot(snap1_id, machine_id, root_id, "hash1", "complete")
        snap1_dir = real_base_path / "machines" / machine_id / "roots" / root_id / "snapshots" / snap1_id
        snap1_dir.mkdir(parents=True)
        inv1 = snap1_dir / "inventory.jsonl"
        with open(inv1, "w") as f:
            f.write(json.dumps({"rel_path": "file1.txt", "size_bytes": 10, "mtime": "2023-01-01T00:00:00Z", "is_symlink": False}) + "\n")

        # Use relative paths in the registry to simulate actual behavior
        inv1_rel = str(inv1.relative_to(real_base_path))
        registry.update_snapshot_artifacts(snap1_id, {"inventory": inv1_rel})

        # Snapshot 2
        snap2_id = "snap2"
        registry.create_snapshot(snap2_id, machine_id, root_id, "hash2", "complete")
        snap2_dir = real_base_path / "machines" / machine_id / "roots" / root_id / "snapshots" / snap2_id
        snap2_dir.mkdir(parents=True)
        inv2 = snap2_dir / "inventory.jsonl"
        with open(inv2, "w") as f:
            f.write(json.dumps({"rel_path": "file1.txt", "size_bytes": 20, "mtime": "2023-01-02T00:00:00Z", "is_symlink": False}) + "\n")
            f.write(json.dumps({"rel_path": "file2.txt", "size_bytes": 15, "mtime": "2023-01-02T00:00:00Z", "is_symlink": False}) + "\n")

        inv2_rel = str(inv2.relative_to(real_base_path))
        registry.update_snapshot_artifacts(snap2_id, {"inventory": inv2_rel})

        # Now switch to a completely different working directory
        os.chdir(some_cwd)

        # Run diff
        delta = compute_snapshot_delta(registry, snap1_id, snap2_id)

        # Delta should have been written to the canonical snap2_dir, NOT under some_cwd
        assert delta["summary"]["new_count"] == 1
        assert delta["summary"]["changed_count"] == 1
        assert delta["summary"]["removed_count"] == 0

        delta_path = snap2_dir / f"{delta['delta_id']}.json"
        assert delta_path.exists(), f"Delta file was not written to canonical directory: {delta_path}"

        # And it should NOT exist under CWD
        wrong_path = Path(some_cwd) / "atlas"
        assert not wrong_path.exists(), f"Delta logic created an 'atlas' folder in CWD: {wrong_path}"

        registry.close()
        os.chdir(old_cwd)
