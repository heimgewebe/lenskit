import os
import pytest
from pathlib import Path

def test_init_service_behavior_no_longer_allows_root(monkeypatch, tmp_path):
    """
    Behavioral Test: Ensure init_service does NOT add Path("/") to the security allowlist.
    This test is skipped if dependencies are missing.
    """
    # Check for dependencies
    pytest.importorskip("fastapi")
    pytest.importorskip("pydantic")

    # If we are here, we can try to import the service
    # We still might need to mock some internal service parts that have deep deps
    # but let's try to keep it as real as possible for the security adapter.
    from merger.lenskit.service.app import init_service
    from merger.lenskit.adapters.security import get_security_config

    # Set the environment variable that PREVIOUSLY enabled the vulnerability
    monkeypatch.setenv("RLENS_ALLOW_FS_ROOT", "1")

    hub = tmp_path / "hub"
    hub.mkdir()

    sec = get_security_config()

    # Snapshot before
    # We use strings for comparison to avoid resolve() mismatches in different envs
    before_roots = {str(p.resolve()) for p in sec.allowlist_roots}

    # Initialize service
    init_service(hub, token="test-token")

    # Snapshot after
    after_roots = {str(p.resolve()) for p in sec.allowlist_roots}

    # Assert Path("/") is NOT in the new roots
    root_str = str(Path("/").resolve())
    assert root_str not in after_roots, f"Vulnerability detected: {root_str} was added to allowlist"

    # Also check that no root in after_roots is exactly "/"
    for p_str in after_roots:
        assert p_str != "/" and p_str != root_str

def test_static_source_check_app_py():
    """
    Static Test: Ensure dangerous configuration is gone from app.py
    """
    app_path = Path("merger/lenskit/service/app.py")
    content = app_path.read_text(encoding="utf-8")

    assert "RLENS_ALLOW_FS_ROOT" not in content
    assert 'add_allowlist_root(Path("/"))' not in content
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
    assert "strictly prohibited" in content
