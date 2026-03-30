import pytest
from pathlib import Path
from merger.lenskit.cli.cmd_atlas import _resolve_snapshot_ref

class MockRegistry:
    def __init__(self, roots, complete_snapshots):
        self._roots = roots
        self._complete_snapshots = complete_snapshots

    def list_roots(self):
        return self._roots

    def list_complete_snapshots(self, root_id):
        return [s for s in self._complete_snapshots if s["root_id"] == root_id]

@pytest.fixture
def mock_registry():
    roots = [
        {"root_id": "r1", "machine_id": "m1", "root_value": "/path1", "root_label": "docs"},
        {"root_id": "r2", "machine_id": "m2", "root_value": "/path2", "root_label": "docs"},
        {"root_id": "r3", "machine_id": "m1", "root_value": "/path3", "root_label": "images"},
        {"root_id": "r4", "machine_id": "m3", "root_value": "/path4", "root_label": "multi"},
        {"root_id": "r5", "machine_id": "m3", "root_value": "/path5", "root_label": "multi"},
        {"root_id": "r6", "machine_id": "m4", "root_value": "/path6", "root_label": "nodata"},
        {"root_id": "r7", "machine_id": "m5", "root_value": "/path/with:colon", "root_label": "weird"},
    ]
    snapshots = [
        {"snapshot_id": "s1", "root_id": "r1", "created_at": "2023-01-01T00:00:00Z"},
        {"snapshot_id": "s2", "root_id": "r1", "created_at": "2023-01-02T00:00:00Z"},
        {"snapshot_id": "s3", "root_id": "r2", "created_at": "2023-01-01T00:00:00Z"},
        {"snapshot_id": "s4", "root_id": "r3", "created_at": "2023-01-01T00:00:00Z"},
        {"snapshot_id": "s7", "root_id": "r7", "created_at": "2023-01-01T00:00:00Z"},
    ]
    return MockRegistry(roots, snapshots)

def test_resolve_by_label_success(mock_registry):
    # Should find r1, and then the latest snapshot (s2)
    snap_id = _resolve_snapshot_ref("m1:label:docs", mock_registry)
    assert snap_id == "s2"

    # Should find r2, and snapshot s3
    snap_id = _resolve_snapshot_ref("m2:label:docs", mock_registry)
    assert snap_id == "s3"

def test_resolve_by_label_not_found(mock_registry):
    with pytest.raises(ValueError, match="No root found for machine 'm1' with label 'missing'"):
        _resolve_snapshot_ref("m1:label:missing", mock_registry)

def test_resolve_by_label_ambiguous(mock_registry):
    with pytest.raises(ValueError, match="Multiple roots found for machine 'm3' with label 'multi'; use machine:path or snapshot_id for explicit disambiguation"):
        _resolve_snapshot_ref("m3:label:multi", mock_registry)

def test_resolve_by_label_no_snapshots(mock_registry):
    with pytest.raises(ValueError, match="No complete snapshot found for machine 'm4' and label 'nodata'"):
        _resolve_snapshot_ref("m4:label:nodata", mock_registry)

def test_resolve_by_path_fallback(mock_registry):
    # Tests the existing machine:path functionality is unmodified
    snap_id = _resolve_snapshot_ref("m1:/path3", mock_registry)
    assert snap_id == "s4"

def test_resolve_snapshot_id_directly(mock_registry):
    # Should just return the exact string if no colon is present
    snap_id = _resolve_snapshot_ref("s123", mock_registry)
    assert snap_id == "s123"

def test_resolve_path_with_colon(mock_registry):
    # Ensure a path with a colon works in the old machine:path branch
    snap_id = _resolve_snapshot_ref("m5:/path/with:colon", mock_registry)
    assert snap_id == "s7"
