
from pathlib import Path

def test_fs_roots_includes_system(service_client):
    res = service_client.client.get("/api/fs/roots", headers=service_client.headers)
    assert res.status_code == 200
    data = res.json()
    roots = data["roots"]
    ids = [r["id"] for r in roots]
    assert "hub" in ids
    assert "system" in ids

    # Verify system path is resolved home
    sys_root = next(r for r in roots if r["id"] == "system")
    assert sys_root["path"] == str(Path.home().resolve())
    # Guaranteed by contract (docs/service-api.md)
    assert "token" in sys_root

def test_create_atlas_system_root(service_client):
    # Test creation with system root
    # Also test that defaults are respected/enforced (implicit)

    payload = {
        "root_kind": "preset",
        "root_value": "system",
        "max_depth": 20, # Should be capped to 6
        "max_entries": 300000 # Should be capped to 200000
    }
    res = service_client.client.post("/api/atlas", json=payload, headers=service_client.headers)
    assert res.status_code == 200
    data = res.json()
    assert data["root_scanned"] == str(Path.home().resolve())
    assert data["paths"]["json"]

    # Verify effective params (New check)
    assert "effective" in data
    eff = data["effective"]
    assert eff["max_depth"] == 6
    assert eff["max_entries"] == 200000
    # Verify hard excludes are present
    assert "**/.ssh/**" in eff["exclude_globs"]
    assert "**/.password-store/**" in eff["exclude_globs"]

def test_export_webmaschine_includes_roots(service_client):
    # First create an atlas to ensure export has something to copy
    # (Though it handles missing atlas gracefully)

    res = service_client.client.post("/api/export/webmaschine", headers=service_client.headers)
    assert res.status_code == 200
    export_path = Path(res.json()["path"])

    assert export_path.exists()
    assert (export_path / "README.md").exists()

    # Check machine.json
    machine_json = export_path / "machine.json"
    assert machine_json.exists()

    import json
    with open(machine_json) as f:
        data = json.load(f)
        assert "roots" in data
        assert str(Path.home().resolve()) in data["roots"]
        assert data["hub"] == str(service_client.hub_path)
