import json
import pytest
from pathlib import Path
from merger.lenskit.cli.stale_check import check_stale_index, _compute_file_sha256

def test_stale_check_warns_on_mismatch(tmp_path, capsys):
    # Setup paths
    base_name = "test_run"
    index_path = tmp_path / f"{base_name}.chunk_index.index.sqlite"
    dump_path = tmp_path / f"{base_name}.dump_index.json"
    derived_path = tmp_path / f"{base_name}.derived_index.json"

    # Create dummy files
    index_path.write_text("dummy index", encoding="utf-8")

    # Dump has content that will generate hash A
    dump_path.write_text("dummy dump version 2", encoding="utf-8")
    actual_hash = _compute_file_sha256(dump_path)

    # Derived manifest records an OLD hash (simulating staleness)
    derived_data = {"canonical_dump_sha256": "old_hash_xyz"}
    derived_path.write_text(json.dumps(derived_data), encoding="utf-8")

    check_stale_index(index_path)

    captured = capsys.readouterr()
    assert "Warning: The index" in captured.err
    assert "stale" in captured.err

def test_stale_check_silent_on_match(tmp_path, capsys):
    base_name = "test_run"
    index_path = tmp_path / f"{base_name}.chunk_index.index.sqlite"
    dump_path = tmp_path / f"{base_name}.dump_index.json"
    derived_path = tmp_path / f"{base_name}.derived_index.json"

    index_path.write_text("dummy index", encoding="utf-8")

    # Dump has content
    dump_path.write_text("dummy dump version 1", encoding="utf-8")
    actual_hash = _compute_file_sha256(dump_path)

    # Derived manifest records the CORRECT hash
    derived_data = {"canonical_dump_sha256": actual_hash}
    derived_path.write_text(json.dumps(derived_data), encoding="utf-8")

    check_stale_index(index_path)

    captured = capsys.readouterr()
    assert captured.err == ""

def test_stale_check_fallback_discovery(tmp_path, capsys):
    # Create an index with an unrelated name
    index_path = tmp_path / "x.index.sqlite"
    index_path.write_text("dummy", encoding="utf-8")

    # Create EXACTLY one derived and one dump index
    derived_path = tmp_path / "foo.derived_index.json"
    dump_path = tmp_path / "foo.dump_index.json"

    dump_path.write_text("dummy dump version 2", encoding="utf-8")

    # Derived manifest records an OLD hash (simulating staleness)
    derived_data = {"canonical_dump_sha256": "old_hash_xyz"}
    derived_path.write_text(json.dumps(derived_data), encoding="utf-8")

    check_stale_index(index_path)

    captured = capsys.readouterr()
    assert "Warning: The index" in captured.err
    assert "stale" in captured.err

def test_stale_check_fallback_multiple_aborts(tmp_path, capsys):
    # Create an index with an unrelated name
    index_path = tmp_path / "x.index.sqlite"
    index_path.write_text("dummy", encoding="utf-8")

    # Create TWO derived indices, making fallback ambiguous
    derived_path1 = tmp_path / "foo.derived_index.json"
    derived_path2 = tmp_path / "bar.derived_index.json"
    dump_path = tmp_path / "foo.dump_index.json"

    dump_path.write_text("dummy", encoding="utf-8")
    derived_data = {"canonical_dump_sha256": "old_hash_xyz"}
    derived_path1.write_text(json.dumps(derived_data), encoding="utf-8")
    derived_path2.write_text(json.dumps(derived_data), encoding="utf-8")

    check_stale_index(index_path)

    # Because there are 2 derived indices, it aborts silently
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""

def test_stale_check_silent_on_missing_files(tmp_path, capsys):
    base_name = "test_run"
    index_path = tmp_path / f"{base_name}.chunk_index.index.sqlite"

    # Derived and Dump manifests are missing!
    index_path.write_text("dummy index", encoding="utf-8")

    check_stale_index(index_path)

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""

def test_stale_check_silent_on_wrong_extension(tmp_path, capsys):
    # Not an index.sqlite file
    wrong_path = tmp_path / "something_else.txt"
    wrong_path.write_text("txt", encoding="utf-8")

    check_stale_index(wrong_path)

    captured = capsys.readouterr()
    assert captured.err == ""
