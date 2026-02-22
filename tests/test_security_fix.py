import os
import sys
from unittest.mock import MagicMock, patch

# Mock heavy dependencies BEFORE any imports from merger.lenskit
class MockBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
    @classmethod
    def model_rebuild(cls, **kwargs): pass
    @classmethod
    def update_forward_refs(cls, **kwargs): pass

mock_pydantic = MagicMock()
mock_pydantic.BaseModel = MockBaseModel
mock_pydantic.Field = MagicMock(return_value=None)
sys.modules["pydantic"] = mock_pydantic

mock_fastapi = MagicMock()
sys.modules["fastapi"] = mock_fastapi
sys.modules["fastapi.staticfiles"] = MagicMock()
sys.modules["fastapi.responses"] = MagicMock()
sys.modules["fastapi.middleware.cors"] = MagicMock()
sys.modules["starlette.concurrency"] = MagicMock()

import pytest
from pathlib import Path

# Add repo root to sys.path
sys.path.insert(0, os.getcwd())

# Mock other service components to avoid further dependency issues
sys.modules["merger.lenskit.service.jobstore"] = MagicMock()
sys.modules["merger.lenskit.service.runner"] = MagicMock()
sys.modules["merger.lenskit.service.logging_provider"] = MagicMock()
sys.modules["merger.lenskit.service.auth"] = MagicMock()
# adapters that might have deps
sys.modules["merger.lenskit.adapters.atlas"] = MagicMock()
sys.modules["merger.lenskit.adapters.metarepo"] = MagicMock()
sys.modules["merger.lenskit.adapters.sources"] = MagicMock()
sys.modules["merger.lenskit.adapters.diagnostics"] = MagicMock()
sys.modules["merger.lenskit.core.merge"] = MagicMock()

from merger.lenskit.service.app import init_service
from merger.lenskit.adapters.security import get_security_config

def test_init_service_no_longer_allowlists_root(monkeypatch):
    """
    Behavioral Test: Ensure init_service does NOT add Path("/") to the security allowlist,
    even if the legacy RLENS_ALLOW_FS_ROOT environment variable is set.
    """
    # Set the environment variable that PREVIOUSLY enabled the vulnerability
    monkeypatch.setenv("RLENS_ALLOW_FS_ROOT", "1")

    hub = Path("/tmp/hub").resolve()
    if not hub.exists():
        hub.mkdir(parents=True, exist_ok=True)

    sec = get_security_config()
    # Reset allowlist for a clean test
    sec.allowlist_roots = []

    # Initialize service
    init_service(hub, token="test-token")

    # Verify Path("/") is NOT in allowlist_roots
    allowed_paths = [str(p) for p in sec.allowlist_roots]
    assert "/" not in allowed_paths
    assert Path("/").resolve() not in sec.allowlist_roots

    # Clean up
    sec.allowlist_roots = []

def test_static_source_check():
    """
    Static Test: Ensure the dangerous configuration strings are completely gone
    from the service code.
    """
    app_path = Path("merger/lenskit/service/app.py")
    content = app_path.read_text()
    assert "RLENS_ALLOW_FS_ROOT" not in content
    assert 'add_allowlist_root(Path("/"))' not in content
    assert 'FS_ROOT = Path("/").resolve()' not in content

def test_cli_static_source_check():
    """
    Static Test: Ensure the dangerous configuration is also gone from the CLI.
    """
    cli_path = Path("merger/lenskit/cli/rlens.py")
    content = cli_path.read_text()
    assert "RLENS_ALLOW_FS_ROOT" not in content
    assert "Security Error: RLENS_ALLOW_FS_ROOT=1" not in content
