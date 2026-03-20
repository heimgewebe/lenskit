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
