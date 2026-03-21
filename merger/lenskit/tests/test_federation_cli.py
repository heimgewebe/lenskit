import json
import pytest
from pathlib import Path
from merger.lenskit.cli.main import main as lenskit_main
from merger.lenskit.core.federation import init_federation, add_bundle

def test_federation_add_cli_dispatch(tmp_path: Path, capsys):
    out_path = tmp_path / "fed.json"
    init_federation("my-fed", out_path)

    bundle_path = tmp_path / "b1"
    bundle_path.mkdir()

    exit_code = lenskit_main(["federation", "add", "--index", str(out_path), "--repo", "r1", "--bundle", str(bundle_path)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "Successfully added bundle 'r1'" in captured.out

def test_federation_inspect_cli_dispatch(tmp_path: Path, capsys):
    out_path = tmp_path / "fed.json"
    init_federation("my-fed", out_path)

    exit_code = lenskit_main(["federation", "inspect", "--index", str(out_path)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "my-fed" in captured.out
    assert "bundle_count" in captured.out

def test_federation_validate_cli_dispatch(tmp_path: Path, capsys):
    out_path = tmp_path / "fed.json"
    init_federation("my-fed", out_path)

    exit_code = lenskit_main(["federation", "validate", "--index", str(out_path)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "is valid" in captured.out

def test_rlens_federation_add_dispatch(tmp_path: Path, monkeypatch, capsys):
    out_path = tmp_path / "fed.json"
    init_federation("my-fed", out_path)

    bundle_path = tmp_path / "b1"
    bundle_path.mkdir()

    monkeypatch.setattr(
        "sys.argv",
        ["rlens", "federation", "add", "--index", str(out_path), "--repo", "r1", "--bundle", str(bundle_path)]
    )

    from merger.lenskit.cli import rlens

    with pytest.raises(SystemExit) as exc_info:
        rlens.main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Successfully added bundle 'r1'" in captured.out

def test_rlens_federation_inspect_dispatch(tmp_path: Path, monkeypatch, capsys):
    out_path = tmp_path / "fed.json"
    init_federation("my-fed", out_path)

    monkeypatch.setattr(
        "sys.argv",
        ["rlens", "federation", "inspect", "--index", str(out_path)]
    )

    from merger.lenskit.cli import rlens

    with pytest.raises(SystemExit) as exc_info:
        rlens.main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "my-fed" in captured.out

def test_rlens_federation_validate_dispatch(tmp_path: Path, monkeypatch, capsys):
    out_path = tmp_path / "fed.json"
    init_federation("my-fed", out_path)

    monkeypatch.setattr(
        "sys.argv",
        ["rlens", "federation", "validate", "--index", str(out_path)]
    )

    from merger.lenskit.cli import rlens

    with pytest.raises(SystemExit) as exc_info:
        rlens.main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "is valid" in captured.out

def test_rlens_federation_query_dispatch(tmp_path: Path, monkeypatch, capsys):
    out_path = tmp_path / "fed.json"
    init_federation("my-fed", out_path)

    bundle_path = tmp_path / "b1"
    bundle_path.mkdir()

    from merger.lenskit.retrieval import index_db

    b1_dump = bundle_path / "dump.json"
    b1_chunks = bundle_path / "chunks.jsonl"
    db_path = bundle_path / "chunk_index.index.sqlite"

    chunk_data = [
        {"chunk_id": "c1", "repo_id": "repo1", "path": "src/main.py", "content": "hello repo1", "start_line": 1, "end_line": 1, "layer": "core", "artifact_type": "code", "content_sha256": "h1", "source_file": "src/main.py", "start_byte": 0, "end_byte": 100}
    ]
    with b1_chunks.open("w", encoding="utf-8") as f:
        for c in chunk_data:
            f.write(json.dumps(c) + "\n")
    b1_dump.write_text(json.dumps({"dummy": "data"}), encoding="utf-8")
    index_db.build_index(b1_dump, b1_chunks, db_path)

    add_bundle(out_path, "repo1", str(bundle_path))

    monkeypatch.setattr(
        "sys.argv",
        ["rlens", "federation", "query", "--index", str(out_path), "-q", "hello"]
    )

    from merger.lenskit.cli import rlens

    with pytest.raises(SystemExit) as excinfo:
        rlens.main()

    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["count"] == 1
    assert parsed["results"][0]["federation_bundle"] == "repo1"

def test_federation_query_cli_dispatch(tmp_path: Path, capsys):
    out_path = tmp_path / "fed.json"
    init_federation("my-fed", out_path)

    from merger.lenskit.cli import main

    # main.main returns an integer code, it doesn't sys.exit directly here.
    ret = main.main(["federation", "query", "--index", str(out_path), "-q", "hello"])
    assert ret == 0

    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())
    # An empty federation implies a successful, empty query case returning count == 0.
    assert parsed["count"] == 0
    assert parsed["results"] == []

def test_federation_query_cli_trace_projection(tmp_path: Path, monkeypatch, capsys):
    # Isolate execution to tmp_path to verify file creation safely
    monkeypatch.chdir(tmp_path)

    out_path = tmp_path / "fed.json"
    init_federation("trace-fed", out_path)

    bundle_path = tmp_path / "b1"
    bundle_path.mkdir()

    from merger.lenskit.retrieval import index_db

    b1_dump = bundle_path / "dump.json"
    b1_chunks = bundle_path / "chunks.jsonl"
    db_path = bundle_path / "chunk_index.index.sqlite"

    chunk_data = [
        {"chunk_id": "c1", "repo_id": "repo1", "path": "src/main.py", "content": "hello repo1", "start_line": 1, "end_line": 1, "layer": "core", "artifact_type": "code", "content_sha256": "h1", "source_file": "src/main.py", "start_byte": 0, "end_byte": 100},
        {"chunk_id": "c2", "repo_id": "repo1", "path": "src/other.py", "content": "hello repo1 again", "start_line": 1, "end_line": 1, "layer": "core", "artifact_type": "code", "content_sha256": "h2", "source_file": "src/other.py", "start_byte": 0, "end_byte": 100}
    ]
    with b1_chunks.open("w", encoding="utf-8") as f:
        for c in chunk_data:
            f.write(json.dumps(c) + "\n")
    b1_dump.write_text(json.dumps({"dummy": "data"}), encoding="utf-8")
    index_db.build_index(b1_dump, b1_chunks, db_path)

    add_bundle(out_path, "repo1", str(bundle_path))

    from merger.lenskit.cli import main

    # Execute with k=1 to force slicing, so we can verify total_results semantics
    # 'hello' matches both chunks in b1_chunks, but the sqlite query_core passes `fetch_k = max(k, 50)` if semantic reranking is used.
    # Actually `execute_query` fetches up to `k` locally. If we pass `k=1`, local bundles only return 1 hit each!
    # To fix this, `execute_federated_query` must request a larger `k` locally, or we accept it's `total_candidates_found_across_returned_bundles`.
    # Wait, `execute_federated_query` calls `execute_query(k=k)`. So local slice is applied before global slice!
    # Therefore, if local bundles return 1 hit each, `all_results` has 1 hit.
    # Ah, in this test setup `b1` has 2 chunks matching 'hello'. `execute_query(k=1)` will only return 1 hit from `b1`!
    # Wait! If we pass `-k 1`, `execute_query` fetches 1 hit. `total_candidates_found` will be 1.
    # To test global slicing, we need `all_results` to be larger than global `k`.
    # But `execute_federated_query` passes the global `k` to local `execute_query`. So each bundle returns up to `k`.
    # If `k=1`, local returns 1. If we have 2 bundles, `all_results` is 2. Global slice is 1. `total_candidates_found` is 2.
    # Ah! The test setup only created `b1`! Let's add `b2` to the test!

    bundle_path2 = tmp_path / "b2"
    bundle_path2.mkdir()
    b2_dump = bundle_path2 / "dump.json"
    b2_chunks = bundle_path2 / "chunks.jsonl"
    b2_db = bundle_path2 / "chunk_index.index.sqlite"

    chunk_data2 = [
        {"chunk_id": "c3", "repo_id": "repo2", "path": "src/main.py", "content": "hello repo2", "start_line": 1, "end_line": 1, "layer": "core", "artifact_type": "code", "content_sha256": "h3", "source_file": "src/main.py", "start_byte": 0, "end_byte": 100}
    ]
    with b2_chunks.open("w", encoding="utf-8") as f:
        for c in chunk_data2:
            f.write(json.dumps(c) + "\n")
    b2_dump.write_text(json.dumps({"dummy": "data"}), encoding="utf-8")
    index_db.build_index(b2_dump, b2_chunks, b2_db)
    add_bundle(out_path, "repo2", str(bundle_path2))

    ret = main.main(["federation", "query", "--index", str(out_path), "-q", "hello", "-k", "1", "--trace"])
    assert ret == 0

    trace_file = tmp_path / "federation_trace.json"
    assert trace_file.exists(), "federation_trace.json was not created in CWD"

    with trace_file.open("r", encoding="utf-8") as f:
        trace_data = json.load(f)

    assert "query" in trace_data
    assert "timestamp" in trace_data
    assert "total_results" in trace_data
    assert "bundles" in trace_data

    # We had 2 hits, but k=1. total_results must be 2.
    assert trace_data["total_results"] == 2

    # Check bundle projection
    assert len(trace_data["bundles"]) == 2

    # Optional schema validation
    try:
        import jsonschema
        schema_path = Path(__file__).parent.parent / "contracts" / "federation-trace.v1.schema.json"
        if schema_path.exists():
            with schema_path.open("r", encoding="utf-8") as sf:
                schema = json.load(sf)
            jsonschema.validate(instance=trace_data, schema=schema)
    except ImportError:
        pass
