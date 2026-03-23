import pytest
from pathlib import Path
from merger.lenskit.atlas.registry import AtlasRegistry

@pytest.fixture
def registry(tmp_path):
    db_path = tmp_path / "test_registry.sqlite"
    with AtlasRegistry(db_path) as reg:
        reg.register_machine("m1", "host-a")
        reg.register_root("r1", "m1", "abs_path", "/var/www")
        reg.create_snapshot("s1", "m1", "r1", "hash123", "running")
        yield reg

def test_update_snapshot_artifacts_security_ignored_keys(registry):
    # Attempt to pass a malicious key that is NOT in the allowlist
    # The current implementation iterates over a hardcoded list, so this should be ignored.
    malicious_artifacts = {
        "inventory": "inv.jsonl",
        "status = 'complete', inventory": "injected"
    }

    registry.update_snapshot_artifacts("s1", malicious_artifacts)

    snap = registry.get_snapshot("s1")
    assert snap["inventory_ref"] == "inv.jsonl"
    # Ensure no injection happened (status should still be 'running' if it wasn't accidentally updated)
    assert snap["status"] == "running"

def test_update_snapshot_artifacts_legitimate(registry):
    registry.update_snapshot_artifacts("s1", {"inventory": "inv.jsonl", "disk": "disk.json"})
    snap = registry.get_snapshot("s1")
    assert snap["inventory_ref"] == "inv.jsonl"
    assert snap["disk_ref"] == "disk.json"
