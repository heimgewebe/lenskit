from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import os
import re


class SecurityViolationError(Exception):
    """Base class for security and path validation errors."""
    pass


class InvalidPathError(SecurityViolationError):
    """Raised when a path is malformed or invalid (400)."""
    pass


class AccessDeniedError(SecurityViolationError):
    """Raised when access to a path is denied (403)."""
    pass


@dataclass
class SecurityConfig:
    # Absolute, normalized roots only. Anything else is rejected at registration.
    allowlist_roots: List[Path] = field(default_factory=list)
    token: str | None = None
    # Root policy: "default" (backward-compatible) or "restricted" (tailnet-safe)
    root_policy: str = "default"

    # Forbidden paths in restricted mode (exact absolute paths or prefixes)
    RESTRICTED_FORBIDDEN_PATHS: tuple = (
        "/", "/home", "/etc", "/var", "/proc", "/sys", "/dev", "/run", "/tmp"
    )

    # Forbidden component names in restricted mode (checked in path parts)
    RESTRICTED_FORBIDDEN_COMPONENTS: tuple = (
        ".ssh", ".gnupg", ".env"
    )

    # Forbidden file suffixes in restricted mode
    RESTRICTED_FORBIDDEN_SUFFIXES: tuple = (
        ".pem", ".key"
    )

    def set_token(self, token: Optional[str]):
        self.token = token

    def set_root_policy(self, policy: str) -> None:
        """Set root policy: 'default' or 'restricted'."""
        valid = ("default", "restricted")
        if policy not in valid:
            raise ValueError(f"Invalid root_policy '{policy}'; expected one of {valid}")
        self.root_policy = policy

    def _check_restricted_root(self, root: Path) -> None:
        """
        Validate a root path against the restricted policy's forbidden list.
        Called only when root_policy == 'restricted'.
        Raises ValueError if the root is forbidden.
        """
        resolved = str(root.resolve())

        # Check exact forbidden paths first (e.g., '/', '/etc')
        if resolved in self.RESTRICTED_FORBIDDEN_PATHS:
            raise ValueError(
                f"Root '{root}' is forbidden in restricted mode (exact match)"
            )

        # Check forbidden prefixes (e.g., /etc/xxx)
        # NOTE: '/' and '/tmp' are exact-match only, not prefix, because
        # '/tmp' is commonly used as a base for temporary directories.
        for forbidden in self.RESTRICTED_FORBIDDEN_PATHS:
            if forbidden in ("/", "/tmp"):
                continue  # exact-match only
            prefix = forbidden.rstrip("/") + "/"
            if resolved.startswith(prefix):
                raise ValueError(
                    f"Root '{root}' is forbidden in restricted mode "
                    f"(under forbidden path '{forbidden}')"
                )

        # Check forbidden component names in path parts
        parts = Path(resolved).parts
        for component in self.RESTRICTED_FORBIDDEN_COMPONENTS:
            if component in parts:
                raise ValueError(
                    f"Root '{root}' contains forbidden component "
                    f"'{component}' in restricted mode"
                )

        # Check forbidden file suffixes
        for suffix in self.RESTRICTED_FORBIDDEN_SUFFIXES:
            if resolved.endswith(suffix):
                raise ValueError(
                    f"Root '{root}' has forbidden suffix '{suffix}' "
                    f"in restricted mode"
                )

        # Check $HOME specifically (resolved home directory)
        try:
            home = str(Path.home().resolve())
            if resolved == home:
                raise ValueError(
                    f"Root '{root}' is the home directory, "
                    f"forbidden in restricted mode"
                )
        except Exception:
            pass

    def add_allowlist_root(self, path: Path) -> None:
        """
        Register a trusted root directory for filesystem access.
        This must NOT accept tainted/relative inputs, otherwise it can widen the jail.
        In restricted mode, validates against forbidden paths.
        """
        s = str(path)
        if not s.strip():
            raise ValueError("Invalid root (empty)")
        if "\x00" in s:
            raise ValueError("Invalid root (NUL byte)")

        try:
            root = path.expanduser().resolve()
        except Exception:
            raise ValueError("Invalid root resolution")

        if not root.is_absolute():
            raise ValueError("Invalid root (not absolute)")

        # Restricted mode: validate against forbidden paths
        if self.root_policy == "restricted":
            self._check_restricted_root(root)

        if root not in self.allowlist_roots:
            self.allowlist_roots.append(root)

    def validate_path(self, path: Path) -> Path:
        """
        Central trust boundary for filesystem paths.
        Two-stage gate:
          1) String-only containment pre-check (no filesystem touch) against allowlist_roots
          2) resolve() + post-check using Path.relative_to for canonical enforcement
        """
        raw = str(path)
        if not raw.strip():
            raise InvalidPathError("Invalid path (empty)")
        if "\0" in raw:
            raise InvalidPathError("Invalid path (NUL byte)")

        if not self.allowlist_roots:
            raise AccessDeniedError(
                "No allowed roots configured (SecurityConfig not initialized)",
            )

        # --- Stage 1: pre-check without resolve() ---
        expanded = os.path.expanduser(raw)
        normalized = os.path.normpath(expanded)

        if not os.path.isabs(normalized):
            raise InvalidPathError("Invalid path (not absolute)")

        allowed_by_prefix = False
        for root in self.allowlist_roots:
            root_norm = os.path.normpath(str(root))
            try:
                if os.path.commonpath([root_norm, normalized]) == root_norm:
                    allowed_by_prefix = True
                    break
            except Exception:
                continue

        if not allowed_by_prefix:
            raise AccessDeniedError("Access denied: Path is not allowed (prefix check)")

        # --- Stage 2: canonicalize + enforce with Path semantics ---
        try:
            resolved = Path(normalized).resolve()
        except Exception:
            raise InvalidPathError("Invalid path resolution")

        for root in self.allowlist_roots:
            try:
                resolved_root = root.resolve()
                resolved.relative_to(resolved_root)
                return resolved
            except ValueError:
                continue

        raise AccessDeniedError("Access denied: Path is not allowed (canonical check)")


_security_config = SecurityConfig()


def get_security_config() -> SecurityConfig:
    return _security_config


def validate_hub_path(path_str: str) -> Path:
    """Validate a user-supplied hub path against the allowlist."""
    if "\0" in path_str:
        raise InvalidPathError("Invalid path (NUL byte)")

    p = Path(path_str)
    resolved = get_security_config().validate_path(p)

    if not resolved.exists():
        raise InvalidPathError("Hub does not exist")
    if not resolved.is_dir():
        raise InvalidPathError("Hub is not a directory")
    return resolved


def validate_source_dir(path: Path) -> Path:
    resolved = get_security_config().validate_path(path)
    if not resolved.exists() or not resolved.is_dir():
        raise InvalidPathError("Invalid repo path")
    return resolved


def validate_repo_name(name: str) -> str:
    _REPO_RE = re.compile(r"^[A-Za-z0-9._-]+$")
    n = (name or "").strip()
    if not n:
        raise InvalidPathError("Invalid repo name: empty")
    if n == "." or n == "..":
        raise InvalidPathError(f"Invalid repo name: {n}")
    if "/" in n or "\\" in n or ".." in n:
        raise InvalidPathError("Invalid repo name: contains slash, backslash, or double-dot")
    if not _REPO_RE.match(n):
        raise InvalidPathError(f"Invalid repo name: {n}")
    return n


def resolve_any_path(root: Path, requested: Optional[str]) -> Path:
    if not requested or requested.strip() == "":
        return root.resolve()
    if os.path.isabs(requested):
        return get_security_config().validate_path(Path(requested))
    joined = root / requested
    return get_security_config().validate_path(joined)