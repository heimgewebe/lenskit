import os
import sys
from unittest.mock import MagicMock
from pathlib import Path

# --- Improved Mocking Strategy for CI without FastAPI/Pydantic ---
# We mock these BEFORE any merger.lenskit imports to avoid collection-time errors.
# We use real classes where possible to avoid typing-related SyntaxErrors.

class MockBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
    @classmethod
    def model_rebuild(cls, **kwargs): pass
    @classmethod
    def update_forward_refs(cls, **kwargs): pass

def mock_dependencies():
    # Only mock if not already present
    try:
        import fastapi
        import pydantic
    except ImportError:
        # Mock FastAPI
        m_fastapi = MagicMock()
        sys.modules["fastapi"] = m_fastapi
        sys.modules["fastapi.staticfiles"] = MagicMock()
        sys.modules["fastapi.responses"] = MagicMock()
        sys.modules["fastapi.middleware.cors"] = MagicMock()

        # Mock Pydantic
        m_pydantic = MagicMock()
        m_pydantic.BaseModel = MockBaseModel
        # Use a real function for Field to avoid issues
        m_pydantic.Field = lambda *args, **kwargs: MagicMock()
        sys.modules["pydantic"] = m_pydantic

        # Mock Starlette (often used with FastAPI)
        sys.modules["starlette"] = MagicMock()
        sys.modules["starlette.concurrency"] = MagicMock()

        # Mock other service-internal modules that might trigger more imports
        # BUT we MUST NOT mock merger.lenskit.adapters.security
        # We also mock JobStore/Runner etc because they have many deps.
        sys.modules["merger.lenskit.service.jobstore"] = MagicMock()
        sys.modules["merger.lenskit.service.runner"] = MagicMock()
        sys.modules["merger.lenskit.service.logging_provider"] = MagicMock()
        sys.modules["merger.lenskit.service.auth"] = MagicMock()
        sys.modules["merger.lenskit.adapters.atlas"] = MagicMock()
        sys.modules["merger.lenskit.adapters.metarepo"] = MagicMock()
        sys.modules["merger.lenskit.adapters.sources"] = MagicMock()
        sys.modules["merger.lenskit.adapters.diagnostics"] = MagicMock()
        sys.modules["merger.lenskit.core.merge"] = MagicMock()

mock_dependencies()

import pytest
# Add repo root to sys.path
sys.path.insert(0, os.getcwd())

# Now we can import the items under test
from merger.lenskit.service.app import init_service
from merger.lenskit.adapters.security import get_security_config

def test_init_service_behavior_no_longer_allows_root(monkeypatch, tmp_path):
    """
    Behavioral Test: Ensure init_service does NOT add Path("/") to the security allowlist.
    """
    # Set the environment variable that PREVIOUSLY enabled the vulnerability
    monkeypatch.setenv("RLENS_ALLOW_FS_ROOT", "1")

    hub = tmp_path / "hub"
    hub.mkdir()

    sec = get_security_config()
    if not hasattr(sec, "allowlist_roots"):
        pytest.skip("SecurityConfig has no allowlist_roots attribute in this build")

    # Snapshot before
    before_roots = {str(p.resolve()) for p in sec.allowlist_roots}

    # Initialize service
    init_service(hub, token="test-token")

    # Snapshot after
    after_roots = {str(p.resolve()) for p in sec.allowlist_roots}

    # Delta calculation
    added_roots = after_roots - before_roots

    # Assert Path("/") is NOT in the roots (absolute and delta)
    root_str = str(Path("/").resolve())
    assert root_str not in after_roots, f"Vulnerability detected: {root_str} is in allowlist"
    assert root_str not in added_roots, f"Vulnerability detected: {root_str} was added to allowlist"

def test_static_source_check_app_py():
    """
    Static Test: Ensure dangerous configuration is gone from app.py
    """
    app_path = Path("merger/lenskit/service/app.py")
    content = app_path.read_text(encoding="utf-8")

    # Use variations to be robust against spacing
    assert "RLENS_ALLOW_FS_ROOT" not in content
    assert 'add_allowlist_root(Path("/"))' not in content
    assert "add_allowlist_root(Path('/'))" not in content
    assert 'FS_ROOT = Path("/").resolve()' not in content

def test_static_source_check_rlens_cli():
    """
    Static Test: Ensure dangerous configuration is gone from CLI
    """
    cli_path = Path("merger/lenskit/cli/rlens.py")
    content = cli_path.read_text(encoding="utf-8")

    assert "RLENS_ALLOW_FS_ROOT" not in content
    assert "Security Error: RLENS_ALLOW_FS_ROOT=1" not in content

def test_static_source_check_adr():
    """
    Static Test: Ensure ADR reflects the decision to prohibit root access
    """
    adr_path = Path("docs/adr/001-secure-fs-navigation.md")
    content = adr_path.read_text(encoding="utf-8")

    # Should no longer have the opt-in section as described before
    assert "Opt-In Root Access" not in content
    assert "RLENS_ALLOW_FS_ROOT=1" not in content

    # Should have the new restricted section
    assert "Restricted Root Access" in content
