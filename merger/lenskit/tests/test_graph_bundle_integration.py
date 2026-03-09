import json
from merger.lenskit.core.merge import build_retrieval_derived_artifacts
from merger.lenskit.core.constants import ArtifactRole

def test_graph_bundle_integration_positive(tmp_path):
    """
    Test that graph_index.json is generated and registered in .derived_index.json
    when the prerequisite artifacts (architecture graph and entrypoints) exist.
    """
    hub_path = tmp_path / "hub"
    hub_path.mkdir()

    # Create a dummy queries.md to prevent eval_core from falling back to the global repo file
    docs_dir = hub_path / "docs" / "retrieval"
    docs_dir.mkdir(parents=True)
    (docs_dir / "queries.md").write_text(
        '1. **"test query"**\n'
        '   *Category:* smoke\n'
        '   *Expected:* `main.py`\n',
        encoding="utf-8",
    )

    # Setup dummy prereq files on disk
    base_path = tmp_path / "dummy_base"

    arch_graph = {
        "nodes": [{"node_id": "file:main.py", "path": "main.py"}],
        "edges": []
    }
    base_path.with_suffix(".architecture_graph.json").write_text(json.dumps(arch_graph))

    entrypoints = {
        "entrypoints": [{"path": "main.py"}]
    }
    base_path.with_suffix(".entrypoints.json").write_text(json.dumps(entrypoints))

    dump_index_path = base_path.with_suffix(".dump_index.json")
    dump_index_path.write_text(json.dumps({}))

    chunk_path = base_path.with_suffix(".chunk_index.jsonl")
    chunk_path.write_text("")

    # A simple base_name_func that just appends the suffix to our base path
    def base_name_func(part_suffix=""):
        return base_path

    # Call the isolated integration function
    derived_paths = build_retrieval_derived_artifacts(
        dump_index_path=dump_index_path,
        chunk_path=chunk_path,
        base_name_func=base_name_func,
        run_id="test_run",
        hub_path=hub_path,
        generator_info={"version": "test", "config_sha256": "0"*64},
        repo_names=["repo1"],
        debug=False
    )

    # Assert physical files exist and are returned
    graph_index_path = base_path.with_suffix(".graph_index.json")
    assert graph_index_path in derived_paths
    assert graph_index_path.exists(), "Graph index artifact was not generated"

    # Assert JSON validity
    graph_data = json.loads(graph_index_path.read_text())
    assert "kind" in graph_data
    assert graph_data["kind"] == "lenskit.architecture.graph_index"
    assert "distances" in graph_data
    assert "file:main.py" in graph_data["distances"]

    # Assert registration in .derived_index.json
    derived_manifest_path = base_path.with_suffix(".derived_index.json")
    assert derived_manifest_path in derived_paths
    assert derived_manifest_path.exists(), "Derived manifest missing"

    manifest_data = json.loads(derived_manifest_path.read_text())
    artifacts_map = manifest_data.get("artifacts", {})

    assert ArtifactRole.GRAPH_INDEX_JSON.value in artifacts_map
    assert artifacts_map[ArtifactRole.GRAPH_INDEX_JSON.value]["path"] == graph_index_path.name


def test_graph_bundle_integration_fallback(tmp_path):
    """
    Test that graph_index.json is NOT generated and the pipeline succeeds
    when prerequisite artifacts are missing, ensuring .derived_index.json is clean.
    """
    hub_path = tmp_path / "hub"
    hub_path.mkdir()

    base_path = tmp_path / "dummy_base"

    # We DO NOT create the prerequisite .architecture_graph.json and .entrypoints.json here

    dump_index_path = base_path.with_suffix(".dump_index.json")
    dump_index_path.write_text(json.dumps({}))

    chunk_path = base_path.with_suffix(".chunk_index.jsonl")
    chunk_path.write_text("")

    def base_name_func(part_suffix=""):
        return base_path

    # Call the isolated integration function
    derived_paths = build_retrieval_derived_artifacts(
        dump_index_path=dump_index_path,
        chunk_path=chunk_path,
        base_name_func=base_name_func,
        run_id="test_run",
        hub_path=hub_path,
        generator_info={"version": "test", "config_sha256": "0"*64},
        repo_names=["repo1"],
        debug=False
    )

    # Assert files DO NOT exist and are NOT returned
    graph_index_path = base_path.with_suffix(".graph_index.json")
    assert graph_index_path not in derived_paths
    assert not graph_index_path.exists(), "Graph index artifact should NOT be generated when prereqs are missing"

    # Assert NOT registered in derived.manifest.json
    derived_manifest_path = base_path.with_suffix(".derived_index.json")
    assert derived_manifest_path in derived_paths
    assert derived_manifest_path.exists()

    manifest_data = json.loads(derived_manifest_path.read_text())
    artifacts_map = manifest_data.get("artifacts", {})

    assert ArtifactRole.GRAPH_INDEX_JSON.value not in artifacts_map, "Role should not be in manifest"
