import pytest
from unittest.mock import MagicMock
from pathlib import Path
from merger.lenskit.adapters.security import SecurityConfig

def test_add_allowlist_root_empty():
    config = SecurityConfig()
    with pytest.raises(ValueError, match=r"Invalid root \(empty\)"):
        config.add_allowlist_root(Path("  "))

def test_add_allowlist_root_nul_byte():
    config = SecurityConfig()
    with pytest.raises(ValueError, match=r"Invalid root \(NUL byte\)"):
        config.add_allowlist_root(Path("/some/path\x00"))

def test_add_allowlist_root_resolution_error():
    config = SecurityConfig()
    mock_path = MagicMock(spec=Path)
    mock_path.__str__.return_value = "/some/path"
    mock_path.expanduser.side_effect = Exception("Resolution failed")

    with pytest.raises(ValueError, match="Invalid root resolution"):
        config.add_allowlist_root(mock_path)

def test_add_allowlist_root_not_absolute():
    config = SecurityConfig()
    mock_path = MagicMock(spec=Path)
    mock_path.__str__.return_value = "/some/path"

    mock_resolved = MagicMock(spec=Path)
    mock_resolved.is_absolute.return_value = False

    mock_path.expanduser.return_value = mock_path
    mock_path.resolve.return_value = mock_resolved

    with pytest.raises(ValueError, match=r"Invalid root \(not absolute\)"):
        config.add_allowlist_root(mock_path)

def test_add_allowlist_root_success():
    config = SecurityConfig()
    # Use a path that is guaranteed to be absolute and resolvable
    # In sandbox it might be /home/jules
    root = Path("/tmp").resolve()
    config.add_allowlist_root(root)
    assert root in config.allowlist_roots

def test_add_allowlist_root_duplicate():
    config = SecurityConfig()
    root = Path("/tmp").resolve()
    config.add_allowlist_root(root)
    config.add_allowlist_root(root)
    assert len(config.allowlist_roots) == 1
