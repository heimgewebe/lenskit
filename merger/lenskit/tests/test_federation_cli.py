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

    import sqlite3
    import json

    db_path = bundle_path / "chunk_index.index.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(content, chunk_id UNINDEXED);")
    conn.execute("CREATE TABLE chunks (chunk_id TEXT PRIMARY KEY, repo_id TEXT, path TEXT, start_line INTEGER, end_line INTEGER, start_byte INTEGER, end_byte INTEGER, content_sha256 TEXT, layer TEXT, artifact_type TEXT, content_range_ref TEXT);")
    conn.execute("INSERT INTO chunks_fts VALUES ('hello repo1', 'c1');")
    conn.execute("INSERT INTO chunks VALUES ('c1', 'repo1', 'src/main.py', 1, 1, 0, 10, 'h1', 'core', 'code', NULL);")
    conn.commit()
    conn.close()

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

def test_federation_query_cli_dispatch(tmp_path: Path, monkeypatch, capsys):
    out_path = tmp_path / "fed.json"
    init_federation("my-fed", out_path)

    from merger.lenskit.cli import main

    # main.main returns an integer code, it doesn't sys.exit directly here.
    ret = main.main(["federation", "query", "--index", str(out_path), "-q", "hello"])
    assert ret == 0

    captured = capsys.readouterr()
    import json
    parsed = json.loads(captured.out)
    assert parsed["count"] == 0
    assert parsed["results"] == []
