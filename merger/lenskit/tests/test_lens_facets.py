import json
from pathlib import Path

import pytest

from merger.lenskit.core.lens_audit import _normalize_path as _audit_normalize_path
from merger.lenskit.core.lens_facets import (
    DERIVATION_TYPES,
    DOES_NOT_ESTABLISH,
    FACET_IDS,
    KIND,
    SOURCE_RULES,
    VERSION,
    _normalize_path,
    infer_facets,
    produce_facet_report,
)
from merger.lenskit.core.lenses import LENS_IDS, infer_lens


def _schema() -> dict:
    schema_path = (
        Path(__file__).parent.parent / "contracts" / "lens-facet.v1.schema.json"
    )
    return json.loads(schema_path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Rule goldset: representative paths with business expectations. This table is
# intentionally written by hand (not derived from the producer) so it expresses
# what each facet should mean, why other facets do NOT apply, and which rule is
# expected.
# --------------------------------------------------------------------------- #
# (path, {facet: source_rule})
_GOLDSET = [
    # contract: only versioned JSON Schema contracts.
    ("merger/lenskit/contracts/lens-facet.v1.schema.json", {"contract": "contract_schema_suffix"}),
    ("merger/lenskit/contracts/primary-lens-audit.v1.schema.json", {"contract": "contract_schema_suffix"}),
    ("merger/lenskit/contracts/export-safety-report.v1.schema.json", {"contract": "contract_schema_suffix"}),
    # test: the file is itself a test module.
    ("merger/lenskit/tests/test_lens_facets.py", {"test": "test_module_marker"}),
    ("merger/lenskit/tests/test_primary_lens_audit.py", {"test": "test_module_marker"}),
    ("merger/lenskit/frontends/webui/tests/app.test.ts", {"test": "test_module_marker"}),
    ("merger/lenskit/frontends/webui/tests/app.spec.ts", {"test": "test_module_marker"}),
    ("src/foo_test.py", {"test": "test_module_marker"}),
    # retrieval: lives under a controlled `retrieval` directory.
    ("merger/lenskit/retrieval/review_eval.py", {"retrieval": "retrieval_surface_path"}),
    ("docs/retrieval/review_queries.v1.json", {"retrieval": "retrieval_surface_path"}),
    # multi-facet: a single path can carry several additive facets.
    (
        "merger/lenskit/retrieval/test_review_eval.py",
        {"test": "test_module_marker", "retrieval": "retrieval_surface_path"},
    ),
    (
        "merger/lenskit/retrieval/retrieval-state.v1.schema.json",
        {"contract": "contract_schema_suffix", "retrieval": "retrieval_surface_path"},
    ),
    # negative: matches no controlled rule -> no facet.
    ("merger/lenskit/core/lenses.py", {}),
    ("docs/architecture/lens-model.md", {}),
    ("src/contracts/user.proto", {}),  # a contract concept, but not a .schema.json
    ("merger/lenskit/tests/bundle_fixtures.py", {}),  # in tests/, but not a test module
]


# --------------------------------------------------------------------------- #
# Contract tests (schema validation; jsonschema is optional in CI/runtime).
# --------------------------------------------------------------------------- #
def test_schema_validates_minimal_report():
    jsonschema = pytest.importorskip("jsonschema")
    report = {
        "kind": KIND,
        "version": VERSION,
        "items": [
            {
                "path": "merger/lenskit/contracts/lens-facet.v1.schema.json",
                "facet": "contract",
                "source_rule": "contract_schema_suffix",
                "derivation_type": "direct",
                "does_not_establish": list(DOES_NOT_ESTABLISH),
            }
        ],
        "summary": {
            "item_count": 1,
            "target_count": 1,
            "facet_counts": {"contract": 1},
        },
        "does_not_establish": list(DOES_NOT_ESTABLISH),
    }
    jsonschema.validate(instance=report, schema=_schema())


def test_schema_validates_empty_report():
    jsonschema = pytest.importorskip("jsonschema")
    report = produce_facet_report([])
    assert report["items"] == []
    assert report["summary"] == {"item_count": 0, "target_count": 0, "facet_counts": {}}
    jsonschema.validate(instance=report, schema=_schema())


def test_schema_validates_generated_report():
    jsonschema = pytest.importorskip("jsonschema")
    report = produce_facet_report([path for path, _ in _GOLDSET])
    jsonschema.validate(instance=report, schema=_schema())


def test_schema_validates_multi_facet_path():
    jsonschema = pytest.importorskip("jsonschema")
    report = produce_facet_report(["merger/lenskit/retrieval/test_review_eval.py"])
    facets = {item["facet"] for item in report["items"]}
    assert facets == {"test", "retrieval"}
    jsonschema.validate(instance=report, schema=_schema())


def _valid_item() -> dict:
    return {
        "path": "merger/lenskit/contracts/lens-facet.v1.schema.json",
        "facet": "contract",
        "source_rule": "contract_schema_suffix",
        "derivation_type": "direct",
        "does_not_establish": list(DOES_NOT_ESTABLISH),
    }


def _report_with_item(item: dict) -> dict:
    return {
        "kind": KIND,
        "version": VERSION,
        "items": [item],
        "summary": {"item_count": 1, "target_count": 1, "facet_counts": {item["facet"]: 1}},
        "does_not_establish": list(DOES_NOT_ESTABLISH),
    }


def test_schema_rejects_unknown_facet():
    jsonschema = pytest.importorskip("jsonschema")
    item = _valid_item()
    item["facet"] = "security"
    report = _report_with_item(item)
    report["summary"]["facet_counts"] = {"contract": 1}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=report, schema=_schema())


def test_schema_rejects_unknown_derivation_type():
    jsonschema = pytest.importorskip("jsonschema")
    item = _valid_item()
    item["derivation_type"] = "confidence"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_report_with_item(item), schema=_schema())


def test_schema_rejects_missing_source_rule():
    jsonschema = pytest.importorskip("jsonschema")
    item = _valid_item()
    del item["source_rule"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_report_with_item(item), schema=_schema())


def test_schema_rejects_facet_rule_mismatch():
    jsonschema = pytest.importorskip("jsonschema")
    item = _valid_item()
    item["source_rule"] = "test_module_marker"  # wrong rule for facet=contract
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_report_with_item(item), schema=_schema())


def test_schema_rejects_missing_does_not_establish():
    jsonschema = pytest.importorskip("jsonschema")
    item = _valid_item()
    del item["does_not_establish"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_report_with_item(item), schema=_schema())


def test_schema_rejects_incomplete_does_not_establish():
    jsonschema = pytest.importorskip("jsonschema")
    item = _valid_item()
    item["does_not_establish"] = ["truth", "correctness"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_report_with_item(item), schema=_schema())


def test_schema_rejects_additional_item_field():
    jsonschema = pytest.importorskip("jsonschema")
    item = _valid_item()
    item["review_priority"] = "high"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_report_with_item(item), schema=_schema())


def test_schema_rejects_wrong_kind():
    jsonschema = pytest.importorskip("jsonschema")
    report = _report_with_item(_valid_item())
    report["kind"] = "lenskit.primary_lens_audit"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=report, schema=_schema())


def test_schema_rejects_wrong_version():
    jsonschema = pytest.importorskip("jsonschema")
    report = _report_with_item(_valid_item())
    report["version"] = "2.0"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=report, schema=_schema())


def test_schema_rejects_invalid_summary_key():
    jsonschema = pytest.importorskip("jsonschema")
    report = _report_with_item(_valid_item())
    report["summary"]["facet_counts"] = {"banana": 1}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=report, schema=_schema())


@pytest.mark.parametrize(
    "bad_path",
    [
        "/abs/path/foo.schema.json",
        ".",
        "   ",
        "../merger/lenskit/contracts/x.schema.json",
        "merger/../lenskit/contracts/x.schema.json",
        r"merger\lenskit\contracts\x.schema.json",
    ],
)
def test_schema_rejects_invalid_item_paths(bad_path):
    jsonschema = pytest.importorskip("jsonschema")
    item = _valid_item()
    item["path"] = bad_path
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_report_with_item(item), schema=_schema())


# --------------------------------------------------------------------------- #
# Path normalization tests.
# --------------------------------------------------------------------------- #
def test_accepts_valid_repo_relative_path():
    report = produce_facet_report(["merger/lenskit/contracts/x.schema.json"])
    assert report["items"][0]["path"] == "merger/lenskit/contracts/x.schema.json"


def test_rejects_empty_paths():
    for bad in ("", "   "):
        with pytest.raises(ValueError, match="path"):
            produce_facet_report([bad])


def test_rejects_dot_path():
    with pytest.raises(ValueError, match="path"):
        produce_facet_report(["."])


def test_rejects_absolute_path():
    with pytest.raises(ValueError, match="repo-relative"):
        produce_facet_report(["/tmp/x.schema.json"])


def test_rejects_backslash_path():
    with pytest.raises(ValueError, match="POSIX"):
        produce_facet_report([r"merger\lenskit\x.schema.json"])


def test_rejects_parent_traversal_path():
    with pytest.raises(ValueError, match="parent traversal"):
        produce_facet_report(["../x.schema.json"])
    with pytest.raises(ValueError, match="parent traversal"):
        produce_facet_report(["merger/../x.schema.json"])


def test_accepts_str_and_path_objects():
    str_report = produce_facet_report(["merger/lenskit/retrieval/review_eval.py"])
    path_report = produce_facet_report([Path("merger/lenskit/retrieval/review_eval.py")])
    assert str_report == path_report


def test_normalization_matches_lens_audit():
    """The locally mirrored normalizer must behave like lens_audit's."""
    good = [
        "merger/lenskit/core/lenses.py",
        "docs/architecture/lens-model.md",
        "merger/lenskit/retrieval/review_eval.py",
    ]
    for path in good:
        assert _normalize_path(path) == _audit_normalize_path(path)
    bad = ["", "   ", ".", "/abs/x.py", r"a\b.py", "../x.py", "a/../b.py"]
    for path in bad:
        facet_err = None
        audit_err = None
        try:
            _normalize_path(path)
        except ValueError as exc:  # noqa: PERF203 - explicit per-case capture
            facet_err = type(exc)
        try:
            _audit_normalize_path(path)
        except ValueError as exc:
            audit_err = type(exc)
        assert facet_err is ValueError and audit_err is ValueError


# --------------------------------------------------------------------------- #
# Semantic tests: rule goldset, positives, negatives, multi-facet.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path,expected", _GOLDSET)
def test_goldset_facets_and_rules(path, expected):
    items = infer_facets(path)
    got = {item["facet"]: item["source_rule"] for item in items}
    assert got == expected
    for item in items:
        assert item["path"] == path
        assert item["derivation_type"] == "direct"
        assert item["does_not_establish"] == list(DOES_NOT_ESTABLISH)


def test_each_v1_facet_has_a_positive_example():
    produced = {
        facet
        for path, _ in _GOLDSET
        for facet in (item["facet"] for item in infer_facets(path))
    }
    assert produced == set(FACET_IDS)


def test_path_without_facet_is_valid_and_empty():
    assert infer_facets("merger/lenskit/core/lenses.py") == []
    report = produce_facet_report(["merger/lenskit/core/lenses.py"])
    assert report["items"] == []
    assert report["summary"]["target_count"] == 0


def test_multi_facet_path_yields_distinct_facets():
    items = infer_facets("merger/lenskit/retrieval/test_review_eval.py")
    facets = [item["facet"] for item in items]
    assert sorted(facets) == ["retrieval", "test"]
    assert len(facets) == len(set(facets))  # no duplicate facet on one path


def test_contract_facet_is_narrower_than_data_models_lens():
    # A .proto is a data_models primary lens but is NOT a v1 contract facet.
    assert infer_lens(Path("src/contracts/user.proto")) == "data_models"
    assert infer_facets("src/contracts/user.proto") == []


def test_facets_do_not_restate_primary_lens():
    report = produce_facet_report([path for path, _ in _GOLDSET])
    payload = json.dumps(report, sort_keys=True)
    # Quoted token form so a path that merely contains "primary_lens"
    # (e.g. test_primary_lens_audit.py) does not trip the field check.
    assert '"primary_lens"' not in payload
    assert '"matched_rule"' not in payload


def test_only_controlled_vocabulary_is_emitted():
    report = produce_facet_report([path for path, _ in _GOLDSET])
    for item in report["items"]:
        assert item["facet"] in FACET_IDS
        assert item["source_rule"] in SOURCE_RULES
        assert item["derivation_type"] in DERIVATION_TYPES


def test_no_excluded_or_authority_fields():
    report = produce_facet_report([path for path, _ in _GOLDSET])
    payload = json.dumps(report, sort_keys=True)
    forbidden_facets = ('"security"', '"claim_boundary"', '"artifact_surface"', '"diagnostic"', '"uncertainty"', '"unknown"', '"other"', '"unclassified"')
    for fragment in forbidden_facets:
        assert fragment not in payload
    forbidden_claims = (
        '"verdict"', '"approved"', '"requires_fix"', '"confidence"',
        '"confidence_class"', '"safe": true', '"critical": true',
        '"impact": true', '"covered": true', '"reviewed": true',
    )
    for fragment in forbidden_claims:
        assert fragment not in payload


def test_v1_producer_only_emits_direct():
    report = produce_facet_report([path for path, _ in _GOLDSET])
    assert {item["derivation_type"] for item in report["items"]} == {"direct"}


def test_primary_lens_surface_is_unchanged():
    assert LENS_IDS == [
        "entrypoints",
        "core",
        "interfaces",
        "data_models",
        "pipelines",
        "ui",
        "guards",
    ]
    # infer_lens still classifies independently of any facet logic.
    assert infer_lens(Path("merger/lenskit/core/lenses.py")) == "core"
    assert infer_lens(Path("merger/lenskit/contracts/x.schema.json")) == "data_models"


# --------------------------------------------------------------------------- #
# Summary tests.
# --------------------------------------------------------------------------- #
def test_summary_counts_are_mechanical():
    report = produce_facet_report(
        [
            "merger/lenskit/contracts/a.schema.json",
            "merger/lenskit/contracts/b.schema.json",
            "merger/lenskit/retrieval/test_x.py",  # test + retrieval (2 facets, 1 path)
            "merger/lenskit/core/lenses.py",  # no facet
        ]
    )
    assert report["summary"]["item_count"] == 4
    assert report["summary"]["target_count"] == 3
    assert report["summary"]["facet_counts"] == {
        "contract": 2,
        "retrieval": 1,
        "test": 1,
    }
    assert list(report["summary"]["facet_counts"]) == sorted(
        report["summary"]["facet_counts"]
    )


# --------------------------------------------------------------------------- #
# Determinism tests.
# --------------------------------------------------------------------------- #
_DET_PATHS = [
    "merger/lenskit/retrieval/test_review_eval.py",
    "merger/lenskit/contracts/a.schema.json",
    "docs/retrieval/queries.json",
    "merger/lenskit/tests/test_x.py",
    "merger/lenskit/core/lenses.py",
]


def test_input_order_does_not_change_output():
    a = produce_facet_report(_DET_PATHS)
    b = produce_facet_report(list(reversed(_DET_PATHS)))
    assert a == b


def test_duplicate_paths_are_deduplicated():
    a = produce_facet_report(_DET_PATHS)
    b = produce_facet_report(_DET_PATHS + _DET_PATHS)
    assert a == b


def test_repeated_runs_are_identical():
    assert produce_facet_report(_DET_PATHS) == produce_facet_report(_DET_PATHS)


def test_items_are_sorted_by_path_then_facet():
    report = produce_facet_report(_DET_PATHS)
    keys = [(item["path"], item["facet"]) for item in report["items"]]
    assert keys == sorted(keys)


def test_no_duplicate_path_facet_pairs():
    report = produce_facet_report(_DET_PATHS + _DET_PATHS)
    keys = [(item["path"], item["facet"]) for item in report["items"]]
    assert len(keys) == len(set(keys))


def test_inputs_are_not_mutated():
    paths = list(_DET_PATHS)
    produce_facet_report(paths)
    assert paths == _DET_PATHS


def test_report_top_level_shape():
    report = produce_facet_report(_DET_PATHS)
    assert report["kind"] == KIND
    assert report["version"] == VERSION
    assert report["does_not_establish"] == list(DOES_NOT_ESTABLISH)
    assert set(report["summary"]) == {"item_count", "target_count", "facet_counts"}
