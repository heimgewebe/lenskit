import pytest
from pathlib import Path
import os
import tempfile
from merger.lenskit.core.merge import detect_hub_dir

def test_detect_hub_dir_saved_path(monkeypatch):
    with tempfile.TemporaryDirectory() as script_dir, tempfile.TemporaryDirectory() as hub_dir:
        script_path = Path(script_dir) / "repolens.py"
        script_path.touch()

        hub_path_file = Path(script_dir) / ".repolens-hub-path.txt"
        hub_path_file.write_text(hub_dir)

        detected = detect_hub_dir(script_path)
        assert detected == Path(hub_dir)

def test_detect_hub_dir_arg_base(monkeypatch):
    with tempfile.TemporaryDirectory() as script_dir, tempfile.TemporaryDirectory() as hub_dir:
        script_path = Path(script_dir) / "repolens.py"
        script_path.touch()

        detected = detect_hub_dir(script_path, arg_base_dir=hub_dir)
        assert detected == Path(hub_dir)

def test_detect_hub_dir_not_found(monkeypatch):
    with tempfile.TemporaryDirectory() as script_dir:
        script_path = Path(script_dir) / "repolens.py"
        script_path.touch()

        with pytest.raises(FileNotFoundError, match="Hub-Verzeichnis"):
            detect_hub_dir(script_path)

def test_detect_hub_dir_invalid_saved_path(monkeypatch):
    with tempfile.TemporaryDirectory() as script_dir:
        script_path = Path(script_dir) / "repolens.py"
        script_path.touch()

        hub_path_file = Path(script_dir) / ".repolens-hub-path.txt"
        hub_path_file.write_text("/does/not/exist/ever")

        with pytest.raises(FileNotFoundError, match="Hub-Verzeichnis"):
            detect_hub_dir(script_path)

def test_detect_hub_dir_arg_overrides_saved_and_env(monkeypatch):
    with tempfile.TemporaryDirectory() as script_dir, tempfile.TemporaryDirectory() as hub_dir_arg, tempfile.TemporaryDirectory() as hub_dir_env, tempfile.TemporaryDirectory() as hub_dir_saved:
        script_path = Path(script_dir) / "repolens.py"
        script_path.touch()

        hub_path_file = Path(script_dir) / ".repolens-hub-path.txt"
        hub_path_file.write_text(hub_dir_saved)

        monkeypatch.setenv("REPOLENS_BASEDIR", hub_dir_env)

        detected = detect_hub_dir(script_path, arg_base_dir=hub_dir_arg)
        assert detected == Path(hub_dir_arg)

def test_detect_hub_dir_env_overrides_saved(monkeypatch):
    with tempfile.TemporaryDirectory() as script_dir, tempfile.TemporaryDirectory() as hub_dir_env, tempfile.TemporaryDirectory() as hub_dir_saved:
        script_path = Path(script_dir) / "repolens.py"
        script_path.touch()

        hub_path_file = Path(script_dir) / ".repolens-hub-path.txt"
        hub_path_file.write_text(hub_dir_saved)

        monkeypatch.setenv("REPOLENS_BASEDIR", hub_dir_env)

        detected = detect_hub_dir(script_path)
        assert detected == Path(hub_dir_env)
