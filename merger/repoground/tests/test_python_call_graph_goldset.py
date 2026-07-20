import json
from pathlib import Path

import pytest

from merger.repoground.architecture.call_graph_quality_eval import (
    PythonCallGraphGoldsetError,
    evaluate_python_call_graph_fixture,
    evaluate_python_call_graph_goldset,
    load_python_call_graph_goldset,
    main,
    stable_report_projection,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDSET_PATH = REPO_ROOT / "docs/retrieval/python_call_graph_goldset.v1.json"
FIXTURE_ROOT = (
    REPO_ROOT / "merger/repoground/tests/fixtures/python_call_graph_goldset"
)


def _load() -> dict:
    return load_python_call_graph_goldset(GOLDSET_PATH)


def test_goldset_covers_registered_categories_and_existing_fixture_paths():
    goldset = _load()
    categories = {case["category"] for case in goldset["cases"]}

    assert categories == set(goldset["required_categories"])
    assert len(goldset["cases"]) == 13
    assert len(goldset["agent_tasks"]) == 3
    assert goldset["language_scope"] == ["python"]
    assert "German identifier and UTF-8 literal" in goldset["unicode_scope"]

    referenced_paths = {case["path"] for case in goldset["cases"]}
    referenced_paths.update(
        path
        for task in goldset["agent_tasks"]
        for path in task["baseline_paths"]
    )
    for relative_path in sorted(referenced_paths):
        assert (FIXTURE_ROOT / relative_path).is_file(), relative_path


def test_quality_benchmark_meets_gate_without_promoting_default():
    report = evaluate_python_call_graph_goldset(GOLDSET_PATH)
    metrics = report["metrics"]
    navigation = metrics["navigation_utility"]

    assert report["coverage"] == {
        "case_count": 13,
        "category_count": 13,
        "call_record_count": 16,
        "skipped_files_count": 0,
        "skipped_errors": [],
    }
    assert metrics["s1_precision"] == 1.0
    assert metrics["target_recall"] == 1.0
    assert metrics["true_positive_count"] == 9
    assert metrics["false_positive_count"] == 0
    assert metrics["false_negative_count"] == 0
    assert metrics["false_positive_classes"] == {}
    assert metrics["unresolved_count"] == 4
    assert metrics["unresolved_share"] == 0.307692
    assert metrics["serialized_call_bytes"] > 0
    assert metrics["build_time_ms"] >= 0
    assert metrics["baseline_tool_calls"] == 9
    assert metrics["graph_tool_calls"] == 3
    assert metrics["tool_call_reduction"] == 0.666667

    assert navigation["baseline_target_recall"] == 1.0
    assert navigation["impact_target_recall"] == 1.0
    assert navigation["no_case_regression"] is True
    assert navigation["baseline_mean_context_path_count"] == pytest.approx(11 / 3)
    assert navigation["impact_mean_context_path_count"] == pytest.approx(5 / 3)
    assert navigation["context_path_reduction_ratio"] == pytest.approx(6 / 11)
    assert all(item["outcome"] == "pass" for item in report["agent_task_outcomes"])

    assert report["decision"]["thresholds_met"] is True
    assert report["decision"]["eligible_for_review"] is True
    assert report["decision"]["default_promoted"] is False
    assert report["decision"]["decision_authority"] == "Bureau"
    assert "default_promotion" in report["does_not_establish"]


def test_report_is_deterministic_except_measured_wall_time():
    first = evaluate_python_call_graph_goldset(GOLDSET_PATH)
    second = evaluate_python_call_graph_goldset(GOLDSET_PATH)

    assert stable_report_projection(first) == stable_report_projection(second)
    assert first["evidence"] == second["evidence"]


def test_wrong_s1_target_counts_as_false_positive_and_false_negative():
    goldset = json.loads(json.dumps(_load()))
    goldset["cases"][0]["expected_target_id"] = (
        "py:callkit:consumer.py:function:not_helper"
    )

    report = evaluate_python_call_graph_fixture(FIXTURE_ROOT, goldset)
    case = next(item for item in report["cases"] if item["id"] == "direct-local-helper")

    assert case["outcome"] == "wrong_target"
    assert case["counts_as_false_positive"] is True
    assert case["counts_as_false_negative"] is True
    assert report["metrics"]["false_positive_count"] == 1
    assert report["metrics"]["false_negative_count"] == 1
    assert report["metrics"]["s1_precision"] == 0.888889
    assert report["metrics"]["target_recall"] == 0.888889
    assert report["decision"]["thresholds_met"] is False
    assert report["decision"]["default_promoted"] is False


def test_goldset_rejects_duplicate_case_ids(tmp_path):
    payload = json.loads(GOLDSET_PATH.read_text(encoding="utf-8"))
    payload["cases"][1]["id"] = payload["cases"][0]["id"]
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PythonCallGraphGoldsetError, match="duplicate case id"):
        load_python_call_graph_goldset(path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("minimum_s1_precision", True, "must be numeric"),
        ("minimum_target_recall", 1.1, "between 0 and 1"),
        ("minimum_context_path_reduction", -0.1, "between 0 and 1"),
        ("no_case_regression", False, "must be true"),
    ],
)
def test_goldset_rejects_invalid_promotion_thresholds(
    tmp_path, field, value, message
):
    payload = json.loads(GOLDSET_PATH.read_text(encoding="utf-8"))
    payload["thresholds"][field] = value
    path = tmp_path / "invalid-threshold.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PythonCallGraphGoldsetError, match=message):
        load_python_call_graph_goldset(path)


def test_cli_writes_reviewable_report(tmp_path):
    output = tmp_path / "report.json"

    assert main(["--goldset", str(GOLDSET_PATH), "--out", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["kind"] == "lenskit.python_call_graph_quality_benchmark"
    assert report["decision"]["thresholds_met"] is True
    assert report["decision"]["default_promoted"] is False
