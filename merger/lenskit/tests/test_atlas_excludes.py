from pathlib import Path

from merger.lenskit.adapters.atlas import AtlasScanner


def test_atlas_excludes_match_top_level_and_nested(tmp_path: Path) -> None:
    # Pure path semantics; no filesystem touch required.
    scanner = AtlasScanner(
        tmp_path,
        "dummy_snap",
        exclude_globs=[
            "**/.git/**",
            "**/node_modules/**",
            "**/.venv/**",
            "**/__pycache__/**",
            "**/.cache/**",
        ],
    )

    assert scanner._is_excluded(tmp_path / ".git") is True
    assert scanner._is_excluded(tmp_path / ".git" / "config") is True
    assert scanner._is_excluded(tmp_path / "repo" / ".git" / "config") is True

    assert scanner._is_excluded(tmp_path / "node_modules" / "pkg" / "index.js") is True
    assert scanner._is_excluded(tmp_path / "nested" / "node_modules" / "pkg" / "index.js") is True

    assert scanner._is_excluded(tmp_path / ".venv" / "pyvenv.cfg") is True
    assert scanner._is_excluded(tmp_path / "nested" / ".venv" / "pyvenv.cfg") is True

    assert scanner._is_excluded(tmp_path / "__pycache__" / "mod.cpython-312.pyc") is True
    assert scanner._is_excluded(tmp_path / "pkg" / "__pycache__" / "mod.cpython-312.pyc") is True

    assert scanner._is_excluded(tmp_path / ".cache" / "pip" / "selfcheck.json") is True
    assert scanner._is_excluded(tmp_path / "nested" / ".cache" / "pip" / "selfcheck.json") is True

    assert scanner._is_excluded(tmp_path / "git" / "config") is False
    assert scanner._is_excluded(tmp_path / "repo" / "git" / "config") is False
