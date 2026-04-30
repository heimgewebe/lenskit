import json
from merger.lenskit.core.merge import build_derived_artifacts
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
    derived_paths = build_derived_artifacts(
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


def test_graph_in_bundle_manifest_positive(tmp_path, monkeypatch):
    """
    Tests that write_reports_v2 correctly bubbles the generated graph_index.json
    up to the final bundle.manifest.json with correct contract schemas.
    """
    from merger.lenskit.core.merge import write_reports_v2, scan_repo, ExtrasConfig
    from merger.lenskit.tests._test_constants import make_generator_info

    repo_dir = tmp_path / "repo1"
    repo_dir.mkdir()
    (repo_dir / "main.py").write_text("import util\ndef main(): pass")

    hub = tmp_path / "hub"
    hub.mkdir()
    merges_dir = hub / "merges"
    merges_dir.mkdir()

    docs_dir = hub / "docs" / "retrieval"
    docs_dir.mkdir(parents=True)
    (docs_dir / "queries.md").write_text("1. **\"test\"**\n   *Expected:* `main.py`\n")

    repo_summary = scan_repo(repo_dir)
    extras = ExtrasConfig.from_csv("architecture")[0]

    import merger.lenskit.core.merge as merge_mod
    original_make_output_filename = merge_mod.make_output_filename

    captured_base_path = []

    def mock_make_output_filename(*args, **kwargs):
        path = original_make_output_filename(*args, **kwargs)
        if not captured_base_path:
            captured_base_path.append(path.with_suffix(""))
            base = path.with_suffix("")

            # Inject prerequisite files mid-flight so build_derived_artifacts finds them
            arch_graph = {"nodes": [{"node_id": "file:main.py", "path": "main.py"}], "edges": []}
            base.with_suffix(".architecture_graph.json").write_text(json.dumps(arch_graph))

            entrypoints = {"entrypoints": [{"path": "main.py"}]}
            base.with_suffix(".entrypoints.json").write_text(json.dumps(entrypoints))
        return path

    monkeypatch.setattr(merge_mod, "make_output_filename", mock_make_output_filename)

    artifacts = write_reports_v2(
        merges_dir=merges_dir,
        hub=hub,
        repo_summaries=[repo_summary],
        detail="full",
        mode="unified",
        max_bytes=100000,
        plan_only=False,
        code_only=False,
        split_size=0,
        debug=True,
        extras=extras,
        output_mode="dual",
        generator_info=make_generator_info()
    )

    manifest_path = artifacts.bundle_manifest
    assert manifest_path and manifest_path.exists(), "Bundle manifest not generated"

    data = json.loads(manifest_path.read_text())

    graph_artifacts = [a for a in data.get("artifacts", []) if a.get("role") == ArtifactRole.GRAPH_INDEX_JSON.value]
    assert len(graph_artifacts) == 1, "Graph index missing from final bundle manifest"

    manifest_entry = graph_artifacts[0]
    assert manifest_entry["path"].endswith(".graph_index.json")
    assert manifest_entry["contract"]["id"] == "architecture.graph_index"
    assert manifest_entry["contract"]["version"] == "v1"
    assert manifest_entry["interpretation"]["mode"] == "contract"

    # Phase 3.5: producer must annotate graph_index_json as a derived retrieval
    # index, never as canonical content.
    assert manifest_entry["authority"] == "retrieval_index"
    assert manifest_entry["canonicality"] == "derived"
    assert manifest_entry["regenerable"] is True
    assert manifest_entry["staleness_sensitive"] is True

    # Phase 3.5: when build_derived_artifacts produces a retrieval_eval.json
    # alongside the graph index, it must also carry diagnostic authority.
    eval_artifacts = [a for a in data.get("artifacts", []) if a.get("role") == ArtifactRole.RETRIEVAL_EVAL_JSON.value]
    if eval_artifacts:
        eval_entry = eval_artifacts[0]
        assert eval_entry["authority"] == "diagnostic_signal"
        assert eval_entry["canonicality"] == "diagnostic"
        assert eval_entry["regenerable"] is True
        assert eval_entry["staleness_sensitive"] is True


def test_graph_bundle_integration_fallback(tmp_path):
    """
    Test that graph_index.json is NOT generated and the pipeline succeeds
    when prerequisite artifacts are missing, ensuring .derived_index.json is clean.
    """
    hub_path = tmp_path / "hub"
    hub_path.mkdir()

    docs_dir = hub_path / "docs" / "retrieval"
    docs_dir.mkdir(parents=True)
    (docs_dir / "queries.md").write_text(
        '1. **"test query"**\n'
        '   *Category:* smoke\n'
        '   *Expected:* `main.py`\n',
        encoding="utf-8",
    )

    base_path = tmp_path / "dummy_base"

    # We DO NOT create the prerequisite .architecture_graph.json and .entrypoints.json here

    dump_index_path = base_path.with_suffix(".dump_index.json")
    dump_index_path.write_text(json.dumps({}))

    chunk_path = base_path.with_suffix(".chunk_index.jsonl")
    chunk_path.write_text("")

    def base_name_func(part_suffix=""):
        return base_path

    # Call the isolated integration function
    derived_paths = build_derived_artifacts(
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

    # Assert NOT registered in .derived_index.json
    derived_manifest_path = base_path.with_suffix(".derived_index.json")
    assert derived_manifest_path in derived_paths
    assert derived_manifest_path.exists()

    manifest_data = json.loads(derived_manifest_path.read_text())
    artifacts_map = manifest_data.get("artifacts", {})

    assert ArtifactRole.GRAPH_INDEX_JSON.value not in artifacts_map, "Role should not be in manifest"
