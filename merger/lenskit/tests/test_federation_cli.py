import json
import pytest
from pathlib import Path
from merger.lenskit.cli.main import main as lenskit_main
from merger.lenskit.core.federation import init_federation

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
