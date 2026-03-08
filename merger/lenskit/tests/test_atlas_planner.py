import json
from pathlib import Path
from merger.lenskit.atlas.planner import plan_atlas_outputs, write_mode_placeholders

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

def test_write_mode_placeholders(tmp_path: Path):
    planned_outputs = {
        "topology": "out.topology.json",
        "content": "out.content.json",
        "workspaces": "out.workspaces.json",
        "hotspots": "out.hotspots.json"
    }

    result_stats = {
        "stats": {
            "top_dirs": [
                {"path": "/src", "bytes": 1000},
                {"path": "/docs", "bytes": 500}
            ]
        }
    }

    write_mode_placeholders(planned_outputs, result_stats, tmp_path)

    topology_file = tmp_path / "out.topology.json"
    assert topology_file.exists()
    assert json.loads(topology_file.read_text(encoding="utf-8")) == {"mode": "topology", "status": "placeholder"}

    content_file = tmp_path / "out.content.json"
    assert content_file.exists()
    assert json.loads(content_file.read_text(encoding="utf-8")) == {"mode": "content", "status": "placeholder"}

    workspaces_file = tmp_path / "out.workspaces.json"
    assert workspaces_file.exists()
    assert json.loads(workspaces_file.read_text(encoding="utf-8")) == {"mode": "workspace", "status": "placeholder"}

    hotspots_file = tmp_path / "out.hotspots.json"
    assert hotspots_file.exists()
    hotspots_data = json.loads(hotspots_file.read_text(encoding="utf-8"))
    assert "top_dirs" in hotspots_data
    assert len(hotspots_data["top_dirs"]) == 2
    assert hotspots_data["top_dirs"][0]["path"] == "/src"

    # Verify formatting (indent=2)
    raw_content = hotspots_file.read_text(encoding="utf-8")
    assert "\n  \"top_dirs\": [\n" in raw_content or "\n  \"top_dirs\": [" in raw_content
