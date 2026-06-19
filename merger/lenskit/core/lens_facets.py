from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable

KIND = "lenskit.lens_facet_report"
VERSION = "1.0"

# Shared lens-family negative-semantics baseline. Identical to the Primary Lens
# Audit baseline (docs/architecture/lens-model.md section 15): a facet is derived
# navigation and establishes none of these.
DOES_NOT_ESTABLISH = (
    "truth",
    "correctness",
    "completeness",
    "runtime_behavior",
    "test_sufficiency",
    "regression_absence",
    "semantic_importance",
    "review_priority",
    "change_impact",
)

# Controlled v1 facet vocabulary. Additive navigation axes only. Deliberately
# small: each facet is derived from a single controlled path/suffix rule with
# clear positive and negative examples. Candidates such as artifact_surface,
# diagnostic, claim_boundary, security and uncertainty are intentionally
# deferred (see docs/proofs/facet-model-v1-proof.md).
FACET_IDS = ("contract", "test", "retrieval")

# Controlled derivation-type vocabulary. Describes HOW an assignment was
# produced, not its confidence/probability/quality, and carries no implicit
# ordering. The v1 producer only ever emits "direct"; "derived" and "heuristic"
# stay reserved for later, structurally derived rules.
DERIVATION_TYPES = ("direct", "derived", "heuristic")

# Controlled source-rule vocabulary. Exactly one rule per facet in v1, so a
# (path, facet) pair can never be produced by two competing rules; rule
# collisions are therefore structurally impossible in this slice.
SOURCE_RULES = (
    "contract_schema_suffix",
    "test_module_marker",
    "retrieval_surface_path",
)

# Precise test-MODULE markers. Intentionally narrower than the broad "guards"
# Primary Lens (which also absorbs validation, CI and guard surfaces): the
# "test" facet marks a file that is itself a test module.
_TEST_FILENAME_SUFFIXES = ("_test.py", ".test.ts", ".spec.ts")

# Controlled path segment for the retrieval subsystem surface
# (e.g. merger/lenskit/retrieval/, docs/retrieval/).
_RETRIEVAL_SEGMENT = "retrieval"


def _normalize_path(path: str | Path) -> str:
    """Normalize a repo-relative path to a stable POSIX form.

    This mirrors merger/lenskit/core/lens_audit.py::_normalize_path. That helper
    is private to lens_audit; rather than promote a foreign private symbol to a
    public dependency we replicate the exact rules here and assert behavioural
    consistency in the tests.
    """
    raw = str(path)
    if not raw.strip():
        raise ValueError("lens facet path must not be empty")
    if "\\" in raw:
        raise ValueError("lens facet path must use POSIX separators")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise ValueError("lens facet path must be repo-relative")
    posix = candidate.as_posix()
    if posix in {"", "."}:
        raise ValueError("lens facet path must identify a repo path")
    if ".." in candidate.parts:
        raise ValueError("lens facet path must not contain parent traversal")
    return posix


def _is_contract_schema(posix: str) -> bool:
    """contract: the path is a versioned JSON Schema contract surface."""
    return posix.endswith(".schema.json")


def _is_test_module(posix: str) -> bool:
    """test: the path is itself a test module by controlled filename marker."""
    name = Path(posix).name
    if name.startswith("test_") and name.endswith(".py"):
        return True
    return name.endswith(_TEST_FILENAME_SUFFIXES)


def _is_retrieval_surface(posix: str) -> bool:
    """retrieval: the path lives under a controlled `retrieval` directory."""
    return _RETRIEVAL_SEGMENT in Path(posix).parts


def _facet_item(posix: str, facet: str, source_rule: str) -> dict[str, Any]:
    return {
        "path": posix,
        "facet": facet,
        "source_rule": source_rule,
        "derivation_type": "direct",
        "does_not_establish": list(DOES_NOT_ESTABLISH),
    }


def infer_facets(path: str | Path) -> list[dict[str, Any]]:
    """Return the deterministic facet assignments for a single repo path.

    The result is a list of (path, facet) assignment dicts and may be empty: a
    path that matches no controlled rule simply carries no facet. There is no
    synthetic ``unknown``/``other`` facet. A path may carry several distinct
    facets (cardinality 0..n). This function performs no I/O, reads no file
    content, and does not consult the environment, git or the network.
    """
    posix = _normalize_path(path)
    items: list[dict[str, Any]] = []

    if _is_contract_schema(posix):
        items.append(_facet_item(posix, "contract", "contract_schema_suffix"))
    if _is_test_module(posix):
        items.append(_facet_item(posix, "test", "test_module_marker"))
    if _is_retrieval_surface(posix):
        items.append(_facet_item(posix, "retrieval", "retrieval_surface_path"))

    return items


def produce_facet_report(paths: Iterable[str | Path]) -> dict[str, Any]:
    """Aggregate deterministic facet assignments over many repo paths.

    Assignments are identified by ``(path, facet)``: duplicate inputs and
    repeated runs produce identical output. Items are stably sorted by
    ``(path, facet)``; the order carries no semantic priority.
    """
    seen: set[tuple[str, str]] = set()
    items: list[dict[str, Any]] = []
    for path in paths:
        for item in infer_facets(path):
            key = (item["path"], item["facet"])
            if key in seen:
                continue
            seen.add(key)
            items.append(item)

    items.sort(key=lambda item: (item["path"], item["facet"]))

    facet_counts: Counter[str] = Counter(item["facet"] for item in items)
    target_count = len({item["path"] for item in items})

    return {
        "kind": KIND,
        "version": VERSION,
        "items": items,
        "summary": {
            "item_count": len(items),
            "target_count": target_count,
            "facet_counts": {
                facet: facet_counts[facet] for facet in sorted(facet_counts)
            },
        },
        "does_not_establish": list(DOES_NOT_ESTABLISH),
    }
