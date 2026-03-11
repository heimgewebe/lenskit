import pytest
import sqlite3
import json
from pathlib import Path
from merger.lenskit.atlas.registry import AtlasRegistry

@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test_registry.sqlite"

@pytest.fixture
def registry(temp_db_path):
    with AtlasRegistry(temp_db_path) as reg:
        yield reg

def test_registry_initialization(temp_db_path, registry):
    assert temp_db_path.exists()
    conn = sqlite3.connect(temp_db_path)
    cur = conn.cursor()

    # Check tables exist
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert "machines" in tables
    assert "roots" in tables
    assert "snapshots" in tables
    conn.close()

def test_machine_registry(registry):
    # Register new machine
    registry.register_machine("m1", "host-a", ["local", "dev"])

    m = registry.get_machine("m1")
    assert m is not None
    assert m["machine_id"] == "m1"
    assert m["hostname"] == "host-a"
    assert "local" in m["labels"]
    assert m["last_seen_at"] is not None

    # Update existing machine
    registry.register_machine("m1", "host-b", ["prod"])
    m2 = registry.get_machine("m1")
    assert m2["hostname"] == "host-b"
    assert "prod" in m2["labels"]

    # List machines
    registry.register_machine("m2", "host-c")
    machines = registry.list_machines()
    assert len(machines) == 2

def test_root_registry(registry):
    registry.register_machine("m1", "host-a")

    registry.register_root("r1", "m1", "abs_path", "/var/www", "www-root")

    r = registry.get_root("r1")
    assert r is not None
    assert r["root_id"] == "r1"
    assert r["machine_id"] == "m1"
    assert r["root_kind"] == "abs_path"
    assert r["root_value"] == "/var/www"
    assert r["label"] == "www-root"

    # Update existing root
    registry.register_root("r1", "m1", "preset", "default", "new-label")
    r2 = registry.get_root("r1")
    assert r2["root_kind"] == "preset"
    assert r2["root_value"] == "default"
    assert r2["label"] == "new-label"

    # List roots
    registry.register_root("r2", "m1", "abs_path", "/tmp")
    roots = registry.list_roots()
    assert len(roots) == 2

def test_snapshot_registry(registry):
    registry.register_machine("m1", "host-a")
    registry.register_root("r1", "m1", "abs_path", "/var/www")

    registry.create_snapshot("s1", "m1", "r1", "hash123", "running")

    s = registry.get_snapshot("s1")
    assert s is not None
    assert s["snapshot_id"] == "s1"
    assert s["machine_id"] == "m1"
    assert s["root_id"] == "r1"
    assert s["scan_config_hash"] == "hash123"
    assert s["status"] == "running"
    assert s["created_at"] is not None
    assert s["inventory_ref"] is None

    registry.update_snapshot_status("s1", "complete")
    s2 = registry.get_snapshot("s1")
    assert s2["status"] == "complete"

    registry.update_snapshot_artifacts("s1", {"inventory": "inv.jsonl", "topology": "topo.json"})
    s3 = registry.get_snapshot("s1")
    assert s3["inventory_ref"] == "inv.jsonl"
    assert s3["topology_ref"] == "topo.json"
    assert s3["dirs_ref"] is None

    # List snapshots
    # Ensure they have identical created_at to test secondary sorting on ID
    cur = registry.conn.cursor()
    cur.execute("UPDATE snapshots SET created_at = '2026-03-10T00:00:00Z' WHERE snapshot_id = 's1'")
    registry.conn.commit()

    registry.create_snapshot("s2", "m1", "r1", "hash456", "running")
    cur.execute("UPDATE snapshots SET created_at = '2026-03-10T00:00:00Z' WHERE snapshot_id = 's2'")
    registry.conn.commit()

    snapshots = registry.list_snapshots()
    assert len(snapshots) == 2

    # Check ordering by created_at DESC, snapshot_id DESC
    # Since both have the exact same created_at, 's2' must strictly appear before 's1'
    assert snapshots[0]["snapshot_id"] == "s2"
    assert snapshots[1]["snapshot_id"] == "s1"


def test_delta_registry(registry):
    registry.register_machine("m1", "host-a")
    registry.register_root("r1", "m1", "abs_path", "/var/www")

    registry.create_snapshot("s1", "m1", "r1", "hash1", "complete")
    registry.create_snapshot("s2", "m1", "r1", "hash2", "complete")

    registry.register_delta("delta1", "s1", "s2", "delta_ref.json")

    delta = registry.get_delta("delta1")
    assert delta is not None
    assert delta["delta_id"] == "delta1"
    assert delta["from_snapshot_id"] == "s1"
    assert delta["to_snapshot_id"] == "s2"
    assert delta["delta_ref"] == "delta_ref.json"
    assert "created_at" in delta

    registry.create_snapshot("s3", "m1", "r1", "hash3", "complete")
    registry.register_delta("delta2", "s2", "s3", "delta_ref2.json")

    deltas = registry.list_deltas()
    assert len(deltas) == 2
