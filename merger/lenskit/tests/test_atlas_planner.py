from merger.lenskit.service.app import plan_atlas_outputs

def test_plan_atlas_outputs_inventory():
    plan = plan_atlas_outputs("inventory", "atlas-123")
    assert "summary" in plan
    assert plan["summary"] == "atlas-123.summary.md"
    assert "inventory" in plan
    assert plan["inventory"] == "atlas-123.inventory.jsonl"
    assert "dirs" in plan
    assert plan["dirs"] == "atlas-123.dirs.jsonl"
    assert "topology" not in plan
    assert "workspaces" not in plan

def test_plan_atlas_outputs_topology():
    plan = plan_atlas_outputs("topology", "atlas-123")
    assert "summary" in plan
    assert "topology" in plan
    assert plan["topology"] == "atlas-123.topology.json"
    assert "inventory" not in plan

def test_plan_atlas_outputs_content():
    plan = plan_atlas_outputs("content", "atlas-123")
    assert "summary" in plan
    assert "inventory" in plan
    assert "content" in plan
    assert plan["content"] == "atlas-123.content.json"
    assert "workspaces" not in plan

def test_plan_atlas_outputs_workspace():
    plan = plan_atlas_outputs("workspace", "atlas-123")
    assert "summary" in plan
    assert "workspaces" in plan
    assert plan["workspaces"] == "atlas-123.workspaces.json"
    assert "hotspots" in plan
    assert plan["hotspots"] == "atlas-123.hotspots.json"
    assert "inventory" not in plan
