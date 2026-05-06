import pytest
import json
from pathlib import Path

from merger.lenskit.core.federation import init_federation, add_bundle
from merger.lenskit.retrieval.federation_query import execute_federated_query
from merger.lenskit.retrieval.federation_query import _build_cross_repo_links
from merger.lenskit.retrieval import index_db

@pytest.fixture
def federated_setup(tmp_path):
    # Setup paths
    fed_path = tmp_path / "federation.json"
    init_federation("test-fed", fed_path)

    # Bundle 1
    b1_dir = tmp_path / "repo1"
    b1_dir.mkdir()
    b1_dump = b1_dir / "dump.json"
    b1_chunks = b1_dir / "chunks.jsonl"
    b1_db = b1_dir / "chunk_index.index.sqlite"

    # To test true provenance flow without JSON injection hacks:
    # `query_core` generates `derived_range_ref` if `source_file`, `start_byte`, `end_byte` exist.
    # Therefore we supply these fields representing a real index build logic.
    chunk_data_1 = [
        {"chunk_id": "c1", "repo_id": "repo1", "path": "src/main.py", "content": "def main(): print('hello repo1')", "start_line": 1, "end_line": 1, "layer": "core", "artifact_type": "code", "content_sha256": "h1", "source_file": "src/main.py", "start_byte": 0, "end_byte": 100}
    ]
    with b1_chunks.open("w", encoding="utf-8") as f:
        for c in chunk_data_1:
            f.write(json.dumps(c) + "\n")
    b1_dump.write_text(json.dumps({"dummy": "data"}), encoding="utf-8")
    index_db.build_index(b1_dump, b1_chunks, b1_db)

    # Bundle 2
    b2_dir = tmp_path / "repo2"
    b2_dir.mkdir()
    b2_dump = b2_dir / "dump.json"
    b2_chunks = b2_dir / "chunks.jsonl"
    b2_db = b2_dir / "chunk_index.index.sqlite"

    chunk_data_2 = [
        {"chunk_id": "c2", "repo_id": "repo2", "path": "src/main.py", "content": "def main(): print('hello repo2')", "start_line": 1, "end_line": 1, "layer": "core", "artifact_type": "code", "content_sha256": "h2", "source_file": "src/main.py", "start_byte": 0, "end_byte": 100},
        {"chunk_id": "c3", "repo_id": "repo2", "path": "tests/test_main.py", "content": "def test_main(): assert True", "start_line": 1, "end_line": 1, "layer": "test", "artifact_type": "code", "content_sha256": "h3", "source_file": "tests/test_main.py", "start_byte": 0, "end_byte": 100}
    ]
    with b2_chunks.open("w", encoding="utf-8") as f:
        for c in chunk_data_2:
            f.write(json.dumps(c) + "\n")
    b2_dump.write_text(json.dumps({"dummy": "data"}), encoding="utf-8")
    index_db.build_index(b2_dump, b2_chunks, b2_db)

    # Add bundles to federation
    add_bundle(fed_path, "repo1", str(b1_dir))
    add_bundle(fed_path, "repo2", str(b2_dir))

    return fed_path

def test_execute_federated_query(federated_setup):
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10
    )

    assert res["federation_id"] == "test-fed"
    assert res["count"] == 2

    # Minimal provenance preservation via federation_bundle tagging
    repos = {h["federation_bundle"] for h in res["results"]}
    assert repos == {"repo1", "repo2"}

def test_execute_federated_query_with_repo_filter(federated_setup):
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        filters={"repo": "repo1"}
    )

    assert res["count"] == 1
    assert res["results"][0]["federation_bundle"] == "repo1"

def test_execute_federated_query_with_trace(federated_setup):
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        trace=True
    )

    assert "federation_trace" in res
    trace = res["federation_trace"]
    assert trace["queried_bundles_total"] == 2
    assert trace["queried_bundles_effective"] == 2
    assert "bundle_status" in trace
    assert trace["bundle_status"]["repo1"] == "ok"
    assert trace["bundle_status"]["repo2"] == "ok"
    assert "bundle_traces" in trace
    assert "repo1" in trace["bundle_traces"]
    assert "repo2" in trace["bundle_traces"]

def test_execute_federated_query_is_deterministic_on_tie(federated_setup):
    # 'hello' will yield score ties.
    # The ordering should be deterministic tie ordering based on repo_id -> path -> chunk_id.
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10
    )

    # repo1 comes before repo2
    assert res["results"][0]["federation_bundle"] == "repo1"
    assert res["results"][1]["federation_bundle"] == "repo2"

def test_execute_federated_query_marks_missing_index(federated_setup):
    bundle_db_path = federated_setup.parent / "repo2" / "chunk_index.index.sqlite"
    bundle_db_path.unlink()

    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        trace=True
    )

    trace = res["federation_trace"]
    assert trace["bundle_status"]["repo2"] == "index_missing"
    assert trace["queried_bundles_effective"] == 1

def test_execute_federated_query_resolves_relative_paths(federated_setup, monkeypatch):
    # Change current working directory to something else to prove we don't rely on it
    original_cwd = Path.cwd()
    monkeypatch.chdir(original_cwd.parent)

    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        trace=True
    )

    trace = res["federation_trace"]
    assert trace["queried_bundles_effective"] == 2
    assert trace["bundle_status"]["repo1"] == "ok"
    assert trace["bundle_status"]["repo2"] == "ok"

def test_execute_federated_query_find_bundle_index_direct_file(federated_setup):
    import json
    bundle_db_path = federated_setup.parent / "repo2" / "chunk_index.index.sqlite"

    # Update federation.json to point directly to the file
    with federated_setup.open("r", encoding="utf-8") as f:
        data = json.load(f)
    for b in data["bundles"]:
        if b["repo_id"] == "repo2":
            b["bundle_path"] = "repo2/chunk_index.index.sqlite"
    with federated_setup.open("w", encoding="utf-8") as f:
        json.dump(data, f)

    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        trace=True
    )

    trace = res["federation_trace"]
    assert trace["bundle_status"]["repo2"] == "ok"
    assert trace["queried_bundles_effective"] == 2

def test_execute_federated_query_find_bundle_index_generic_fallback(federated_setup):
    # Rename chunk_index.index.sqlite to custom.index.sqlite
    repo2_dir = federated_setup.parent / "repo2"
    old_db = repo2_dir / "chunk_index.index.sqlite"
    new_db = repo2_dir / "custom.index.sqlite"
    old_db.rename(new_db)

    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        trace=True
    )

    trace = res["federation_trace"]
    assert trace["bundle_status"]["repo2"] == "ok"
    assert trace["queried_bundles_effective"] == 2

def test_execute_federated_query_find_bundle_index_ambiguous(federated_setup):
    # Create an ambiguous situation by adding a second index file
    repo2_dir = federated_setup.parent / "repo2"
    ambiguous_db = repo2_dir / "ambiguous.chunk_index.index.sqlite"
    original_db = repo2_dir / "chunk_index.index.sqlite"

    import shutil
    shutil.copy(original_db, ambiguous_db)

    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        trace=True
    )

    trace = res["federation_trace"]
    # Should safely fail and mark as index_missing due to ambiguity
    assert trace["bundle_status"]["repo2"] == "index_missing"
    assert trace["queried_bundles_effective"] == 1

def test_execute_federated_query_filters_repo_locally(federated_setup, monkeypatch):
    from merger.lenskit.retrieval import federation_query

    captured_filters = []
    original_execute_query = federation_query.execute_query

    def mock_execute_query(index_path, *args, **kwargs):
        captured_filters.append(kwargs.get("filters"))
        return original_execute_query(index_path, *args, **kwargs)

    monkeypatch.setattr(federation_query, "execute_query", mock_execute_query)

    execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        filters={"repo": "repo1", "layer": "core"},
        trace=True
    )

    # Ensure execute_query was called at least once
    assert len(captured_filters) > 0
    for f in captured_filters:
        if f is not None:
            # "repo" should be removed before calling execute_query
            assert "repo" not in f
            # other filters like "layer" should be passed down
            assert f.get("layer") == "core"

def test_execute_federated_query_marks_filtered_out_bundle(federated_setup):
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        filters={"repo": "repo1"},
        trace=True
    )

    trace = res["federation_trace"]
    assert trace["bundle_status"]["repo2"] == "filtered_out"
    assert trace["queried_bundles_effective"] == 1

def test_execute_federated_query_marks_unsupported_bundle_uri(federated_setup):
    # Modify federation index manually to add an unsupported URI
    with federated_setup.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data["bundles"].append({"repo_id": "repo3", "bundle_path": "https://example.org/bundles/repo3"})
    with federated_setup.open("w", encoding="utf-8") as f:
        json.dump(data, f)

    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        trace=True
    )

    trace = res["federation_trace"]
    assert trace["bundle_status"]["repo3"] == "bundle_path_unsupported"
    assert trace["queried_bundles_total"] == 3
    assert trace["queried_bundles_effective"] == 2

def test_execute_federated_query_fails_on_invalid_structure(federated_setup):
    with federated_setup.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Invalidate structure by removing a required field (repo_id)
    if data.get("bundles"):
        del data["bundles"][0]["repo_id"]

    with federated_setup.open("w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(ValueError) as excinfo:
        execute_federated_query(
            federation_index_path=federated_setup,
            query_text="hello"
        )
    # The validation gate should fail deterministically on the schema check before logical constraints.
    assert "Schema validation failed" in str(excinfo.value)
    assert "'repo_id' is a required property" in str(excinfo.value)

def test_execute_federated_query_not_found(tmp_path):
    missing_path = tmp_path / "missing_fed.json"

    with pytest.raises(FileNotFoundError):
        execute_federated_query(
            federation_index_path=missing_path,
            query_text="hello"
        )

def test_execute_federated_query_empty_after_filter(federated_setup):
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        filters={"repo": "repo_non_existent"},
        trace=True
    )

    assert res["count"] == 0
    assert res["results"] == []
    trace = res["federation_trace"]
    assert trace["bundle_status"]["repo1"] == "filtered_out"
    assert trace["bundle_status"]["repo2"] == "filtered_out"
    assert trace["queried_bundles_effective"] == 0

def test_cross_repo_context_preserves_primary_evidence(federated_setup):
    # Both repos have a chunk matching 'hello'
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10
    )

    # Check context markers
    hits = res["results"]
    assert len(hits) == 2

    # We expect deterministic sorting: Repo 1 comes first due to tie-breaking rules
    assert hits[0]["federation_bundle"] == "repo1"
    assert hits[0]["cross_repo_context_role"] == "primary_evidence"

    assert hits[1]["federation_bundle"] == "repo2"
    assert hits[1]["cross_repo_context_role"] == "secondary_context"

    # Ensure they are truly cross-repo
    assert hits[0]["federation_bundle"] != hits[1]["federation_bundle"]

def test_provenance_is_preserved(federated_setup):
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10
    )

    hits = res["results"]
    assert len(hits) == 2, "Hits without provenance should be rejected"
    for hit in hits:
        assert hit["federation_bundle"] in ["repo1", "repo2"]
        assert hit["repo_id"] in ["repo1", "repo2"]
        # In this test we use derived_range_ref generation through `source_file` and bytes, mimicking realistic runtime
        assert "derived_range_ref" in hit
        assert hit["derived_range_ref"]["file_path"] in ["src/main.py", "tests/test_main.py"]

def test_conflicts_are_reported_not_merged(federated_setup):
    # Both repos have a chunk named src/main.py
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10
    )

    assert "federation_conflicts" in res
    conflicts = res["federation_conflicts"]

    # We expect one conflict for main.py (same file name, different repos)
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c["type"] == "path"
    assert "main.py" in c["description"]
    assert c["resolution"] == "unresolved"
    assert len(c["involved_results"]) == 2

    # Verify both results are still returned (no merging)
    hits = res["results"]
    assert len(hits) == 2
    for h in hits:
        assert "conflict_refs" in h
        assert c["conflict_id"] in h["conflict_refs"]

def test_stale_bundle_is_marked_in_federation_trace(federated_setup):
    import sqlite3

    # Set fingerprint in federation.json that mismatches the actual index
    # (using last_fingerprint as defined in federation-index.v1.schema.json)
    with federated_setup.open("r", encoding="utf-8") as f:
        data = json.load(f)
    for b in data["bundles"]:
        if b["repo_id"] == "repo1":
            b["last_fingerprint"] = "stale_hash"
    with federated_setup.open("w", encoding="utf-8") as f:
        json.dump(data, f)

    # Write actual canonical hash to the db so staleness detection kicks in
    repo1_db = federated_setup.parent / "repo1" / "chunk_index.index.sqlite"
    conn = sqlite3.connect(repo1_db)
    conn.execute("CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR REPLACE INTO index_meta (key, value) VALUES ('canonical_dump_index_sha256', 'actual_hash')")
    conn.commit()
    conn.close()

    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        trace=True
    )

    trace = res["federation_trace"]
    # Should be marked as stale but still complete successfully
    assert trace["bundle_status"]["repo1"] == "stale"
    assert trace["bundle_status"]["repo2"] == "ok"
    assert trace["queried_bundles_effective"] == 2

def test_execute_federated_query_rejects_falsy_provenance(federated_setup, monkeypatch):
    from merger.lenskit.retrieval import federation_query

    original_execute_query = federation_query.execute_query

    def mock_execute_query_with_falsy_provenance(index_path, *args, **kwargs):
        res = original_execute_query(index_path, *args, **kwargs)
        # Force the provenance fields to exist but be falsy for one of the bundles
        for hit in res.get("results", []):
            hit["derived_range_ref"] = None
            hit["range_ref"] = {}
        return res

    monkeypatch.setattr(federation_query, "execute_query", mock_execute_query_with_falsy_provenance)

    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10
    )

    # All hits have falsy provenance, so they should be filtered out
    assert res["count"] == 0
    assert len(res["results"]) == 0

def test_execute_federated_query_total_candidates_vs_k_slice(federated_setup):
    # Setup creates 2 hits for "hello" across bundles. We set k=1 to force slicing.
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=1
    )

    assert res["count"] == 1
    assert len(res["results"]) == 1
    assert res["total_candidates_found"] == 2

def test_execute_federated_query_handles_query_error(federated_setup, monkeypatch):
    from merger.lenskit.retrieval import federation_query

    original_execute_query = federation_query.execute_query

    def mock_execute_query(index_path, *args, **kwargs):
        # Nur für repo1 einen Fehler simulieren
        if "repo1" in str(index_path):
            raise RuntimeError("Database corruption")
        return original_execute_query(index_path, *args, **kwargs)

    monkeypatch.setattr(federation_query, "execute_query", mock_execute_query)

    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        trace=True
    )

    trace = res["federation_trace"]
    assert trace["bundle_status"]["repo1"] == "query_error"
    assert "Database corruption" in trace["bundle_errors"]["repo1"]
    assert trace["bundle_status"]["repo2"] == "ok"
    assert trace["queried_bundles_effective"] == 1
    # Ein Bundle liefert Ergebnisse
    assert res["count"] > 0

def test_execute_federated_query_trace_behavior(federated_setup):
    from merger.lenskit.retrieval.federation_query import execute_federated_query

    # Prove trace=False correctly omits federation_trace at the source
    res_no_trace = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="foo",
        trace=False
    )
    assert "federation_trace" not in res_no_trace

    # Prove trace=True correctly includes federation_trace
    res_with_trace = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="foo",
        trace=True
    )
    assert "federation_trace" in res_with_trace

def test_cross_repo_links_are_emitted_for_multi_bundle_results(federated_setup):
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
    )

    assert "cross_repo_links" in res
    links = res["cross_repo_links"]
    assert len(links) == 1

    link = links[0]
    assert link["source_repo"] == "repo1"
    assert link["target_repo"] == "repo2"
    assert link["link_type"] == "co_occurrence"
    assert link["confidence"] == "inferred"
    assert len(link["evidence_refs"]) >= 1

def test_cross_repo_links_are_omitted_for_single_bundle_result(federated_setup):
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
        filters={"repo": "repo1"},
    )

    assert "cross_repo_links" not in res

def test_build_cross_repo_links_does_not_mutate_results_input(federated_setup):
    res = execute_federated_query(
        federation_index_path=federated_setup,
        query_text="hello",
        k=10,
    )

    results = res["results"]
    before = json.loads(json.dumps(results))
    _ = _build_cross_repo_links(results)
    assert results == before

def test_cross_repo_links_schema_enforces_minimal_semantics():
    try:
        import jsonschema
    except ImportError:
        pytest.skip("jsonschema not installed")

    schema_path = Path(__file__).parent.parent / "contracts" / "cross-repo-links.v1.schema.json"
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    valid = [
        {
            "source_repo": "repo1",
            "target_repo": "repo2",
            "link_type": "co_occurrence",
            "confidence": "inferred",
            "evidence_refs": ["repo1:c1", "repo2:c2"],
        }
    ]
    jsonschema.validate(instance=valid, schema=schema)

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance={"not": "an_array"}, schema=schema)

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            instance=[
                {
                    "source_repo": "repo1",
                    "target_repo": "repo2",
                    "link_type": "depends_on",
                    "confidence": "inferred",
                    "evidence_refs": ["repo1:c1"],
                }
            ],
            schema=schema,
        )

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            instance=[
                {
                    "source_repo": "repo1",
                    "target_repo": "repo2",
                    "link_type": "co_occurrence",
                    "confidence": "explicit",
                    "evidence_refs": ["repo1:c1"],
                }
            ],
            schema=schema,
        )

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            instance=[
                {
                    "source_repo": "repo1",
                    "target_repo": "repo2",
                    "link_type": "co_occurrence",
                    "confidence": "inferred",
                    "evidence_refs": [],
                }
            ],
            schema=schema,
        )
