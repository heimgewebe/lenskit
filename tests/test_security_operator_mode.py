import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from merger.lenskit.adapters.security import SecurityConfig, AccessDeniedError

# --- Mocking for init_service Behavioral Test ---
class MockBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items(): setattr(self, k, v)
    @classmethod
    def model_rebuild(cls, **kwargs): pass
    @classmethod
    def update_forward_refs(cls, **kwargs): pass

def setup_mocks():
    # Only mock if dependencies are missing (e.g. in minimal CI)
    try:
        import fastapi
        import pydantic
    except ImportError:
        m_fastapi = MagicMock()
        sys.modules["fastapi"] = m_fastapi
        sys.modules["fastapi.staticfiles"] = MagicMock()
        sys.modules["fastapi.responses"] = MagicMock()
        sys.modules["fastapi.middleware.cors"] = MagicMock()
        m_pydantic = MagicMock()
        m_pydantic.BaseModel = MockBaseModel
        m_pydantic.Field = lambda *args, **kwargs: MagicMock()
        sys.modules["pydantic"] = m_pydantic
        sys.modules["starlette"] = MagicMock()
        sys.modules["starlette.concurrency"] = MagicMock()

    # Always mock heavy service components for these targeted tests
    # BUT DO NOT mock merger.lenskit.adapters.security
    sys.modules["merger.lenskit.service.jobstore"] = MagicMock()
    sys.modules["merger.lenskit.service.runner"] = MagicMock()
    sys.modules["merger.lenskit.service.logging_provider"] = MagicMock()
    sys.modules["merger.lenskit.service.auth"] = MagicMock()
    sys.modules["merger.lenskit.adapters.atlas"] = MagicMock()
    sys.modules["merger.lenskit.adapters.metarepo"] = MagicMock()
    sys.modules["merger.lenskit.adapters.sources"] = MagicMock()
    sys.modules["merger.lenskit.adapters.diagnostics"] = MagicMock()
    sys.modules["merger.lenskit.core.merge"] = MagicMock()

setup_mocks()
# Ensure repo root is in path
sys.path.insert(0, os.getcwd())

from merger.lenskit.service.app import init_service
from merger.lenskit.adapters.security import get_security_config

def test_security_config_allowlist_invariant(tmp_path):
    """
    Unit Test: Verify that SecurityConfig enforces boundaries correctly.
    """
    sec = SecurityConfig()
    hub = (tmp_path / "hub").resolve()
    hub.mkdir(parents=True, exist_ok=True)
    repo_dir = hub / "repo"
    repo_dir.mkdir()

    sec.add_allowlist_root(hub)

    # Path inside hub should be allowed
    sec.validate_path(repo_dir)

    # Path outside should be denied
    with pytest.raises(AccessDeniedError):
        sec.validate_path(Path("/etc"))

def test_init_service_default_no_root(monkeypatch, tmp_path):
    """
    Behavioral: By default, root is NOT allowlisted.
    """
    hub = tmp_path / "hub"
    hub.mkdir()
    sec = get_security_config()
    sec.allowlist_roots = [] # Reset

    init_service(hub, host="127.0.0.1")

    root_path = Path("/").resolve()
    assert root_path not in sec.allowlist_roots

def test_init_service_operator_mode_refused_on_non_loopback(monkeypatch, tmp_path):
    """
    Behavioral: Root is refused if host is NOT loopback.
    """
    monkeypatch.setenv("RLENS_ALLOW_FS_ROOT", "1")
    monkeypatch.setenv("RLENS_OPERATOR_MODE", "1")
    monkeypatch.setenv("RLENS_TOKEN", "secret")

    hub = tmp_path / "hub"
    hub.mkdir()
    sec = get_security_config()
    sec.allowlist_roots = [] # Reset

    init_service(hub, host="192.168.1.1") # Non-loopback

    root_path = Path("/").resolve()
    assert root_path not in sec.allowlist_roots

def test_init_service_operator_mode_refused_if_operator_flag_missing(monkeypatch, tmp_path):
    """
    Behavioral: Root is refused if RLENS_OPERATOR_MODE=1 is missing.
    """
    monkeypatch.setenv("RLENS_ALLOW_FS_ROOT", "1")
    # Missing RLENS_OPERATOR_MODE
    monkeypatch.setenv("RLENS_TOKEN", "secret")

    hub = tmp_path / "hub"
    hub.mkdir()
    sec = get_security_config()
    sec.allowlist_roots = [] # Reset

    init_service(hub, host="127.0.0.1")

    root_path = Path("/").resolve()
    assert root_path not in sec.allowlist_roots

def test_init_service_operator_mode_success(monkeypatch, tmp_path):
    """
    Behavioral: Root IS allowlisted if ALL conditions are met.
    """
    monkeypatch.setenv("RLENS_ALLOW_FS_ROOT", "1")
    monkeypatch.setenv("RLENS_OPERATOR_MODE", "1")
    monkeypatch.setenv("RLENS_TOKEN", "secret")

    hub = tmp_path / "hub"
    hub.mkdir()
    sec = get_security_config()
    sec.allowlist_roots = [] # Reset

    init_service(hub, host="127.0.0.1")

    root_path = Path("/").resolve()
    assert root_path in sec.allowlist_roots

def test_static_source_check_app_py():
    app_path = Path("merger/lenskit/service/app.py")
    content = app_path.read_text(encoding="utf-8")

    # Logic should be gated by is_loopback and operator_enabled
    assert "is_loopback = _is_loopback_host(host)" in content
    assert "operator_enabled = os.getenv(\"RLENS_OPERATOR_MODE\", \"0\") == \"1\"" in content
    assert "logger.warning(\"Operator Mode: Allowlisting system root '/' for navigation\")" in content

def test_static_source_check_rlens_cli():
    cli_path = Path("merger/lenskit/cli/rlens.py")
    content = cli_path.read_text(encoding="utf-8")

    # CLI should enforce the constraints
    assert "RLENS_OPERATOR_MODE" in content
    assert "Security Error: RLENS_ALLOW_FS_ROOT=1 requires loopback host" in content

def test_static_source_check_adr():
    adr_path = Path("docs/adr/001-secure-fs-navigation.md")
    content = adr_path.read_text(encoding="utf-8")

    assert "Gated Root Access (Operator Mode)" in content
    assert "RLENS_OPERATOR_MODE=1" in content
    assert "loopback interface" in content
