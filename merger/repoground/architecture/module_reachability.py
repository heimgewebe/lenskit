"""Conservative reachability evidence for production Python modules.

Static import analysis alone cannot decide whether a module is used: RepoGround
reaches modules through ``python -m`` entry points, CLI dispatch, lazy imports,
systemd units and shell wrappers. This module therefore collects *evidence of
use* from several surfaces and classifies every production module as either
``reachable`` (at least one piece of evidence) or ``unproven`` (none found).

``unproven`` is deliberately not ``dead``. The measurement is fail-closed in the
direction that matters for deletion: it can under-claim reachability, never
under-claim it in a way that would license removing live code.
"""

from __future__ import annotations

import ast
import functools
import os
import re
from pathlib import Path
from typing import Any, Iterable

from merger.repoground.architecture.path_classification import path_projection

_SKIP_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}

#: Text surfaces that can invoke a module without importing it in Python.
_RUNTIME_SUFFIXES = {
    ".cfg",
    ".ini",
    ".json",
    ".service",
    ".sh",
    ".timer",
    ".toml",
    ".yaml",
    ".yml",
}
_DOCUMENTATION_SUFFIXES = {".md", ".rst", ".txt"}

#: Directories that can actually invoke code. ``config/`` and ``docs/`` are
#: excluded on purpose: they hold policies, baselines and measurement artifacts
#: that merely *name* modules, and counting those as evidence would let a
#: recorded path masquerade as a live consumer.
_RUNTIME_DIRECTORIES = (
    ".github/",
    ".wgx/",
    "ops/",
    "scripts/",
    "tools/",
)

#: Evidence kinds that show use by code or by an operational surface.
NON_DOCUMENTATION_EVIDENCE = (
    "static_import_product",
    "static_import_test",
    "static_import_script",
    "package_of_referenced_module",
    "package_data_reference",
    "module_main_block",
    "dynamic_string_reference",
    "runtime_surface_reference",
)


def _iter_files(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    for root, directories, filenames in os.walk(repo_root):
        directories[:] = sorted(
            directory for directory in directories if directory not in _SKIP_DIRECTORIES
        )
        for filename in sorted(filenames):
            paths.append(Path(root) / filename)
    return paths


def _module_name(relative_path: str) -> str:
    dotted = relative_path[: -len(".py")].replace("/", ".")
    if dotted.endswith(".__init__"):
        return dotted[: -len(".__init__")]
    return dotted


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _resolve_relative(module_name: str, is_package: bool, node: ast.ImportFrom) -> str:
    """Resolve a relative import against the importing module's package."""

    parts = module_name.split(".")
    if not is_package:
        parts = parts[:-1]
    ascend = node.level - 1
    if ascend:
        parts = parts[: len(parts) - ascend] if ascend < len(parts) else []
    if node.module:
        parts = parts + node.module.split(".")
    return ".".join(parts)


def _imported_names(tree: ast.AST, module_name: str, is_package: bool) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = (
                _resolve_relative(module_name, is_package, node)
                if node.level
                else (node.module or "")
            )
            if not base:
                continue
            names.add(base)
            # ``from pkg import module`` also binds ``pkg.module``.
            names.update(f"{base}.{alias.name}" for alias in node.names)
    return names


def _string_literals(tree: ast.AST) -> set[str]:
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def _parse(text: str | None, path: Path) -> ast.AST | None:
    if text is None:
        return None
    try:
        return ast.parse(text, filename=str(path))
    except SyntaxError:
        return None


def _has_main_block(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
            continue
        operands = [node.test.left, *node.test.comparators]
        has_name = any(
            isinstance(item, ast.Name) and item.id == "__name__" for item in operands
        )
        has_literal = any(
            isinstance(item, ast.Constant) and item.value == "__main__"
            for item in operands
        )
        if has_name and has_literal:
            return True
    return False


def _is_runtime_surface(relative_path: str, suffix: str) -> bool:
    """Decide whether a non-Python file can invoke a module."""

    in_runtime_directory = relative_path.startswith(_RUNTIME_DIRECTORIES)
    at_repository_root = "/" not in relative_path
    if not (in_runtime_directory or at_repository_root):
        return False
    return suffix in _RUNTIME_SUFFIXES or (not suffix and in_runtime_directory)


@functools.lru_cache(maxsize=2048)
def _token_pattern(needle: str) -> re.Pattern[str]:
    """Match ``needle`` only as a whole dotted name or path."""

    return re.compile(rf"(?<![\w./-]){re.escape(needle)}(?![\w./-])")


class _Corpus:
    """Concatenated text of one surface, searched by module name and path.

    Matching is token-exact: ``merger`` must not be credited for a mention of
    ``merger.repoground.core``. Over-claiming reachability would turn an unused
    module into a silent pass, so partial matches are rejected.
    """

    def __init__(self) -> None:
        self._chunks: list[str] = []
        self._joined: str | None = None

    def add(self, text: str) -> None:
        self._chunks.append(text)
        self._joined = None

    def contains(self, *needles: str) -> bool:
        if self._joined is None:
            self._joined = "\n".join(self._chunks)
        return any(
            # The cheap substring test keeps the regex off the whole corpus for
            # the overwhelming majority of module names.
            needle in self._joined and _token_pattern(needle).search(self._joined)
            for needle in needles
        )


def measure_module_reachability(
    repo_root: Path,
    package_roots: Iterable[str] = ("merger",),
) -> dict[str, Any]:
    """Collect reachability evidence for every production module."""

    roots = tuple(package_roots)
    modules: dict[str, dict[str, Any]] = {}
    imports_by_projection: dict[str, set[str]] = {
        "product": set(),
        "test": set(),
        "script": set(),
        "fixture": set(),
    }
    dynamic_strings: set[str] = set()
    data_files: list[str] = []
    runtime_corpus = _Corpus()
    documentation_corpus = _Corpus()
    unparsed: list[str] = []
    unparsed_non_product: list[str] = []

    for path in _iter_files(repo_root):
        relative = path.relative_to(repo_root).as_posix()
        suffix = path.suffix.lower()

        if suffix == ".py":
            projection = path_projection(relative)
            text = _read_text(path)
            tree = _parse(text, path)
            if tree is None:
                # An unreadable product or script source could hide a module or
                # its imports, so it fails; deliberately invalid test fixtures
                # only under-claim evidence, which stays on the strict side.
                target = unparsed if projection in {"product", "script"} else unparsed_non_product
                target.append(relative)
                continue
            module_name = _module_name(relative)
            is_package = path.name == "__init__.py"
            imports_by_projection.setdefault(projection, set()).update(
                _imported_names(tree, module_name, is_package)
            )
            dynamic_strings.update(_string_literals(tree))
            if projection == "product" and relative.startswith(
                tuple(f"{root}/" for root in roots)
            ):
                modules[module_name] = {
                    "path": relative,
                    "is_package": is_package,
                    "module_main_block": _has_main_block(tree),
                }
            continue

        data_files.append(relative)

        if _is_runtime_surface(relative, suffix):
            text = _read_text(path)
            if text is not None:
                runtime_corpus.add(text)
        elif suffix in _DOCUMENTATION_SUFFIXES:
            text = _read_text(path)
            if text is not None:
                documentation_corpus.add(text)

    all_imports = set().union(*imports_by_projection.values())
    records = [
        _module_record(
            module_name,
            details,
            imports_by_projection=imports_by_projection,
            all_imports=all_imports,
            dynamic_strings=dynamic_strings,
            data_files=data_files,
            runtime_corpus=runtime_corpus,
            documentation_corpus=documentation_corpus,
        )
        for module_name, details in sorted(modules.items())
    ]

    unproven = [record["module"] for record in records if record["status"] == "unproven"]
    documentation_only = [
        record["module"]
        for record in records
        if record["status"] == "reachable" and not record["has_non_documentation_evidence"]
    ]
    return {
        "kind": "repoground.module_reachability_measurement",
        "version": "1.0",
        "package_roots": list(roots),
        "module_count": len(records),
        "unproven": unproven,
        "documentation_only": documentation_only,
        "unparsed_files": sorted(unparsed),
        "unparsed_non_product_files": sorted(unparsed_non_product),
        "modules": records,
        "does_not_establish": [
            "that an unproven module is dead",
            "that a reachable module is executed at runtime",
            "completeness of dynamic loader discovery",
            "that evidence surfaces are themselves used",
        ],
    }


def _referenced_data_file(
    data_file: str,
    package_directory: str,
    dynamic_strings: set[str],
) -> bool:
    """Report whether Python source names this packaged data file."""

    relative_inside_package = data_file[len(package_directory) :]
    return any(
        value == data_file
        or value == relative_inside_package
        or value.endswith(f"/{relative_inside_package}")
        for value in dynamic_strings
    )


def _module_record(
    module_name: str,
    details: dict[str, Any],
    *,
    imports_by_projection: dict[str, set[str]],
    all_imports: set[str],
    dynamic_strings: set[str],
    data_files: list[str],
    runtime_corpus: _Corpus,
    documentation_corpus: _Corpus,
) -> dict[str, Any]:
    relative_path = details["path"]
    prefix = f"{module_name}."
    evidence: list[str] = []

    for projection, kind in (
        ("product", "static_import_product"),
        ("test", "static_import_test"),
        ("script", "static_import_script"),
    ):
        if module_name in imports_by_projection.get(projection, set()):
            evidence.append(kind)

    if details["is_package"] and not evidence:
        # A package is reached whenever anything below it is imported.
        if any(name.startswith(prefix) for name in all_imports):
            evidence.append("package_of_referenced_module")

    if details["is_package"] and not evidence:
        # A package directory also ships the non-Python contract and schema
        # files that production code loads by path.
        package_directory = relative_path[: -len("__init__.py")]
        if any(
            data_file.startswith(package_directory)
            and _referenced_data_file(data_file, package_directory, dynamic_strings)
            for data_file in data_files
        ):
            evidence.append("package_data_reference")

    if details["module_main_block"]:
        evidence.append("module_main_block")

    if any(
        value == module_name or value == relative_path or value.startswith(prefix)
        for value in dynamic_strings
    ):
        evidence.append("dynamic_string_reference")

    if runtime_corpus.contains(module_name, relative_path):
        evidence.append("runtime_surface_reference")

    if documentation_corpus.contains(module_name, relative_path):
        evidence.append("documented_invocation")

    return {
        "module": module_name,
        "path": relative_path,
        "status": "reachable" if evidence else "unproven",
        "evidence": evidence,
        "has_non_documentation_evidence": any(
            kind in NON_DOCUMENTATION_EVIDENCE for kind in evidence
        ),
    }


def evaluate_reachability_policy(
    measurement: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    """Reject newly unproven modules and undeclared documentation-only modules."""

    findings: list[dict[str, Any]] = []
    allowed_unproven = set(policy.get("allowed_unproven") or [])
    allowed_documentation_only = set(policy.get("allowed_documentation_only") or [])

    for module in measurement["unproven"]:
        if module not in allowed_unproven:
            findings.append({"code": "module_reachability_unproven", "module": module})
    for module in sorted(allowed_unproven - set(measurement["unproven"])):
        findings.append({"code": "module_reachability_allowlist_stale", "module": module})

    if policy.get("require_non_documentation_evidence", True):
        for module in measurement["documentation_only"]:
            if module not in allowed_documentation_only:
                findings.append(
                    {"code": "module_reachability_documentation_only", "module": module}
                )
        for module in sorted(
            allowed_documentation_only - set(measurement["documentation_only"])
        ):
            findings.append(
                {"code": "module_reachability_documentation_allowlist_stale", "module": module}
            )

    if measurement["unparsed_files"]:
        findings.append(
            {
                "code": "module_reachability_unparsed_sources",
                "files": measurement["unparsed_files"],
            }
        )
    return findings
