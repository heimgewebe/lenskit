import os
import pytest
from pathlib import Path
from merger.lenskit.adapters.security import SecurityConfig, AccessDeniedError

def test_security_config_allowlist_invariant(tmp_path):
    """
    Unit Test: Verify that SecurityConfig enforces boundaries correctly
    and does not allow root access by default.
    """
    sec = SecurityConfig()
    hub = (tmp_path / "hub").resolve()
    hub.mkdir(parents=True, exist_ok=True)

    # Ensure test target exists to be robust against any resolve/existence checks
    repo_dir = hub / "repo"
    repo_dir.mkdir()

    sec.add_allowlist_root(hub)

    # Invariant 1: The system root (/) must not be in the allowlist
    if hasattr(sec, "allowlist_roots"):
        root_str = str(Path("/").resolve())
        allowed_strings = {str(p.resolve()) for p in sec.allowlist_roots}
        assert root_str not in allowed_strings, "System root found in allowlist"

    # Invariant 2: Path inside hub should be allowed
    sec.validate_path(repo_dir)

    # Invariant 3: Path outside (like /etc) should be denied
    with pytest.raises(AccessDeniedError):
        sec.validate_path(Path("/etc"))

    # Invariant 4: Root itself should be denied for general navigation
    # This enforces the policy that root is not an authorized browsing base.
    with pytest.raises(AccessDeniedError):
        sec.validate_path(Path("/").resolve())

def test_static_source_check_app_py():
    """
    Static Test: Ensure dangerous configuration is gone from app.py.
    Checks for multiple variations to be robust against spacing/quotes.
    """
    app_path = Path("merger/lenskit/service/app.py")
    content = app_path.read_text(encoding="utf-8")

    # Check for the environment variable name
    assert "RLENS_ALLOW_FS_ROOT" not in content

    # Check for the allowlist call with Path("/")
    assert "add_allowlist_root(Path(\"/\"))" not in content
    assert "add_allowlist_root(Path('/'))" not in content

    # Check for the unused constant
    assert "FS_ROOT = Path(\"/\")" not in content

def test_static_source_check_rlens_cli():
    """
    Static Test: Ensure dangerous configuration is gone from CLI.
    """
    cli_path = Path("merger/lenskit/cli/rlens.py")
    content = cli_path.read_text(encoding="utf-8")

    assert "RLENS_ALLOW_FS_ROOT" not in content
    assert "Security Error: RLENS_ALLOW_FS_ROOT=1" not in content

def test_static_source_check_adr():
    """
    Static Test: Ensure ADR reflects the decision to prohibit root browsing.
    """
    adr_path = Path("docs/adr/001-secure-fs-navigation.md")
    content = adr_path.read_text(encoding="utf-8")

    # Should no longer have the opt-in section
    assert "Opt-In Root Access" not in content
    assert "RLENS_ALLOW_FS_ROOT=1" not in content

    # Should have the new restricted section
    assert "Restricted Root Access" in content
    assert "Browsing the system root" in content
