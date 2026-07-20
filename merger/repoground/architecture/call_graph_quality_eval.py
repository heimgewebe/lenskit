"""Evaluate the fixed Python call-graph quality and navigation goldset."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from merger.repoground.core.agent_impact_eval import evaluate_agent_impact_goldset

from .call_graph import extract_python_calls


GOLDSET_KIND = "lenskit.python_call_graph_quality_goldset"
GOLDSET_VERSION = "1.0"
VALID_STATUSES = frozenset({"resolved", "candidate", "ambiguous", "unresolved"})
VALID_EVIDENCE_LEVELS = frozenset({"S0", "S1"})
VALID_RELATION_TYPES = frozenset({"calls", "constructs"})
REPO_ROOT = Path(__file__).resolve().parents[3]


class PythonCallGraphGoldsetError(ValueError):
    """The Python call-graph quality goldset is structurally invalid."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _require_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PythonCallGraphGoldsetError(f"{label} must be a non-empty string")
    return value


def _validate_thresholds(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise PythonCallGraphGoldsetError("thresholds must be an object")
    required = {
        "minimum_s1_precision",
        "minimum_target_recall",
        "minimum_context_path_reduction",
        "no_case_regression",
    }
    missing = required - set(raw)
    if missing:
        raise PythonCallGraphGoldsetError(
            f"thresholds missing {', '.join(sorted(missing))}"
        )
    thresholds = dict(raw)
    for key in (
        "minimum_s1_precision",
        "minimum_target_recall",
        "minimum_context_path_reduction",
    ):
        value = thresholds[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PythonCallGraphGoldsetError(f"{key} must be numeric")
        if not 0.0 <= float(value) <= 1.0:
            raise PythonCallGraphGoldsetError(f"{key} must be between 0 and 1")
        thresholds[key] = float(value)
    if thresholds["no_case_regression"] is not True:
        raise PythonCallGraphGoldsetError("no_case_regression must be true")
    return thresholds


def _validate_categories(payload: Mapping[str, Any]) -> set[str]:
    categories = payload.get("required_categories")
    if not isinstance(categories, list) or not categories:
        raise PythonCallGraphGoldsetError(
            "required_categories must be a non-empty list"
        )
    if any(not isinstance(category, str) or not category for category in categories):
        raise PythonCallGraphGoldsetError(
            "required_categories must contain non-empty strings"
        )
    if len(set(categories)) != len(categories):
        raise PythonCallGraphGoldsetError("required_categories must be unique")
    return set(categories)


def _validate_cases(payload: Mapping[str, Any]) -> set[str]:
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise PythonCallGraphGoldsetError("cases must be a non-empty list")
    case_ids: set[str] = set()
    observed_categories: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping):
            raise PythonCallGraphGoldsetError("case must be an object")
        case_id = _require_non_empty_string(case.get("id"), "case id")
        if case_id in case_ids:
            raise PythonCallGraphGoldsetError(f"duplicate case id: {case_id}")
        case_ids.add(case_id)
        category = _require_non_empty_string(
            case.get("category"), f"{case_id}.category"
        )
        observed_categories.add(category)
        _require_non_empty_string(case.get("path"), f"{case_id}.path")
        _require_non_empty_string(
            case.get("callee_expression"), f"{case_id}.callee_expression"
        )
        if "caller_qualified_name" not in case:
            raise PythonCallGraphGoldsetError(
                f"{case_id}.caller_qualified_name must be explicit"
            )
        caller = case["caller_qualified_name"]
        if caller is not None and (not isinstance(caller, str) or not caller):
            raise PythonCallGraphGoldsetError(
                f"{case_id}.caller_qualified_name must be null or non-empty"
            )
        status = case.get("expected_status")
        if status not in VALID_STATUSES:
            raise PythonCallGraphGoldsetError(
                f"{case_id}.expected_status is invalid"
            )
        evidence = case.get("expected_evidence_level")
        if evidence not in VALID_EVIDENCE_LEVELS:
            raise PythonCallGraphGoldsetError(
                f"{case_id}.expected_evidence_level is invalid"
            )
        relation = case.get("expected_relation_type")
        if relation not in VALID_RELATION_TYPES:
            raise PythonCallGraphGoldsetError(
                f"{case_id}.expected_relation_type is invalid"
            )
        _require_non_empty_string(
            case.get("expected_reason"), f"{case_id}.expected_reason"
        )
        target_id = case.get("expected_target_id")
        if status == "resolved":
            _require_non_empty_string(target_id, f"{case_id}.expected_target_id")
            if evidence != "S1":
                raise PythonCallGraphGoldsetError(
                    f"{case_id}: resolved cases must expect S1"
                )
        elif target_id is not None:
            raise PythonCallGraphGoldsetError(
                f"{case_id}: non-resolved cases must not expect a target"
            )
    missing = _validate_categories(payload) - observed_categories
    if missing:
        raise PythonCallGraphGoldsetError(
            "goldset missing required categories: "
            + ", ".join(sorted(missing))
        )
    return case_ids


def _validate_agent_tasks(payload: Mapping[str, Any], case_ids: set[str]) -> None:
    tasks = payload.get("agent_tasks")
    if not isinstance(tasks, list) or not tasks:
        raise PythonCallGraphGoldsetError("agent_tasks must be a non-empty list")
    task_ids: set[str] = set()
    for task in tasks:
        if not isinstance(task, Mapping):
            raise PythonCallGraphGoldsetError("agent task must be an object")
        task_id = _require_non_empty_string(task.get("id"), "agent task id")
        if task_id in task_ids:
            raise PythonCallGraphGoldsetError(
                f"duplicate agent task id: {task_id}"
            )
        task_ids.add(task_id)
        selected = task.get("case_ids")
        if not isinstance(selected, list) or not selected:
            raise PythonCallGraphGoldsetError(
                f"{task_id}.case_ids must be a non-empty list"
            )
        if any(not isinstance(case_id, str) or not case_id for case_id in selected):
            raise PythonCallGraphGoldsetError(
                f"{task_id}.case_ids must contain non-empty strings"
            )
        if len(set(selected)) != len(selected):
            raise PythonCallGraphGoldsetError(
                f"{task_id}.case_ids must be unique"
            )
        unknown = set(selected) - case_ids
        if unknown:
            raise PythonCallGraphGoldsetError(
                f"{task_id} references unknown cases: "
                + ", ".join(sorted(unknown))
            )
        paths = task.get("baseline_paths")
        if not isinstance(paths, list) or not paths:
            raise PythonCallGraphGoldsetError(
                f"{task_id}.baseline_paths must be a non-empty list"
            )
        if any(not isinstance(path, str) or not path for path in paths):
            raise PythonCallGraphGoldsetError(
                f"{task_id}.baseline_paths must contain non-empty strings"
            )
        if len(set(paths)) != len(paths):
            raise PythonCallGraphGoldsetError(
                f"{task_id}.baseline_paths must be unique"
            )
        tool_calls = task.get("baseline_tool_calls")
        if (
            isinstance(tool_calls, bool)
            or not isinstance(tool_calls, int)
            or tool_calls < 1
        ):
            raise PythonCallGraphGoldsetError(
                f"{task_id}.baseline_tool_calls must be a positive integer"
            )


def load_python_call_graph_goldset(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PythonCallGraphGoldsetError(
            f"cannot load Python call-graph goldset: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise PythonCallGraphGoldsetError("goldset must be a JSON object")
    if payload.get("kind") != GOLDSET_KIND:
        raise PythonCallGraphGoldsetError("unexpected goldset kind")
    if payload.get("version") != GOLDSET_VERSION:
        raise PythonCallGraphGoldsetError("unsupported goldset version")
    _require_non_empty_string(payload.get("fixture_root"), "fixture_root")
    thresholds = _validate_thresholds(payload.get("thresholds"))
    case_ids = _validate_cases(payload)
    _validate_agent_tasks(payload, case_ids)
    boundaries = payload.get("does_not_establish")
    if not isinstance(boundaries, list) or not boundaries:
        raise PythonCallGraphGoldsetError(
            "does_not_establish must be a non-empty list"
        )
    if any(not isinstance(item, str) or not item for item in boundaries):
        raise PythonCallGraphGoldsetError(
            "does_not_establish must contain non-empty strings"
        )
    result = dict(payload)
    result["thresholds"] = thresholds
    return result


def _target_path(target_id: str | None) -> str | None:
    if not target_id or not target_id.startswith("py:"):
        return None
    for marker in (":async_function:", ":function:", ":class:"):
        prefix, separator, _ = target_id.partition(marker)
        if separator:
            return prefix.removeprefix("py:").replace(":", "/")
    return None


def _fixture_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    files = (candidate for candidate in root.rglob("*") if candidate.is_file())
    for path in sorted(files):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _case_match(call: Mapping[str, Any], case: Mapping[str, Any]) -> bool:
    return (
        call.get("path") == case["path"]
        and call.get("callee_expression") == case["callee_expression"]
        and call.get("caller_qualified_name") == case["caller_qualified_name"]
    )


def _evaluate_case(
    calls: Sequence[Mapping[str, Any]], case: Mapping[str, Any]
) -> dict[str, Any]:
    matches = [call for call in calls if _case_match(call, case)]
    if len(matches) != 1:
        return {
            "id": case["id"],
            "category": case["category"],
            "path": case["path"],
            "callee_expression": case["callee_expression"],
            "caller_qualified_name": case["caller_qualified_name"],
            "selector_match_count": len(matches),
            "expected_status": case["expected_status"],
            "actual_status": None,
            "expected_target_id": case.get("expected_target_id"),
            "actual_target_ids": [],
            "counts_as_true_positive": False,
            "counts_as_false_positive": False,
            "counts_as_false_negative": case["expected_status"] == "resolved",
            "outcome": "selector_error",
            "passed": False,
        }

    call = matches[0]
    expected_target = case.get("expected_target_id")
    target_ids = list(call.get("resolved_target_ids", []))
    target_match = (
        target_ids == [expected_target]
        if expected_target is not None
        else target_ids == []
    )
    fields_match = (
        call.get("resolution_status") == case["expected_status"]
        and call.get("resolution_reason") == case["expected_reason"]
        and call.get("evidence_level") == case["expected_evidence_level"]
        and call.get("relation_type") == case["expected_relation_type"]
    )
    expected_s1 = case["expected_status"] == "resolved"
    actual_s1 = (
        call.get("resolution_status") == "resolved"
        and call.get("evidence_level") == "S1"
    )
    correct_s1 = expected_s1 and actual_s1 and target_match
    false_positive = actual_s1 and not correct_s1
    false_negative = expected_s1 and not correct_s1
    if correct_s1:
        outcome = "true_positive"
    elif expected_s1 and actual_s1:
        outcome = "wrong_target"
    elif false_positive:
        outcome = "false_positive"
    elif false_negative:
        outcome = "false_negative"
    else:
        outcome = "non_s1_expected"

    return {
        "id": case["id"],
        "category": case["category"],
        "path": case["path"],
        "callee_expression": case["callee_expression"],
        "caller_qualified_name": case["caller_qualified_name"],
        "selector_match_count": 1,
        "expected_status": case["expected_status"],
        "actual_status": call.get("resolution_status"),
        "expected_reason": case["expected_reason"],
        "actual_reason": call.get("resolution_reason"),
        "expected_evidence_level": case["expected_evidence_level"],
        "actual_evidence_level": call.get("evidence_level"),
        "expected_relation_type": case["expected_relation_type"],
        "actual_relation_type": call.get("relation_type"),
        "expected_target_id": expected_target,
        "actual_target_ids": target_ids,
        "source_range_ref": call.get("range_ref"),
        "counts_as_true_positive": correct_s1,
        "counts_as_false_positive": false_positive,
        "counts_as_false_negative": false_negative,
        "outcome": outcome,
        "passed": fields_match and target_match,
    }


def _impact_paths(
    task: Mapping[str, Any],
    case_results: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    paths: set[str] = set()
    for case_id in task["case_ids"]:
        case = case_results[case_id]
        paths.add(str(case["path"]))
        target_path = _target_path(case.get("expected_target_id"))
        if target_path:
            paths.add(target_path)
    return sorted(paths)


def _evaluate_navigation_tasks(
    goldset: Mapping[str, Any],
    case_results: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]]:
    by_id = {case["id"]: case for case in case_results}
    tasks = list(goldset["agent_tasks"])
    navigation_goldset = {
        "id": "python-call-graph-navigation-tasks-v1",
        "minimum_target_recall_advantage": 1.0,
        "minimum_context_path_reduction_at_equal_or_better_recall": goldset[
            "thresholds"
        ]["minimum_context_path_reduction"],
        "cases": [
            {
                "id": task["id"],
                "expected_paths": _impact_paths(task, by_id),
            }
            for task in tasks
        ],
    }
    observations = {
        task["id"]: {
            "baseline_paths": list(task["baseline_paths"]),
            "impact_context": {
                "target": {"paths": _impact_paths(task, by_id)},
                "gaps": [],
                "source_statuses": [],
            },
        }
        for task in tasks
    }
    utility = evaluate_agent_impact_goldset(navigation_goldset, observations)
    utility_by_id = {item["id"]: item for item in utility["cases"]}
    outcomes: list[dict[str, Any]] = []
    for task in tasks:
        item = utility_by_id[task["id"]]
        selected_cases_pass = all(
            by_id[case_id]["passed"] for case_id in task["case_ids"]
        )
        passed = (
            selected_cases_pass
            and item["impact_recall"] >= item["baseline_recall"]
            and item["context_path_reduction_ratio"]
            >= goldset["thresholds"]["minimum_context_path_reduction"]
        )
        outcomes.append(
            {
                **item,
                "execution_mode": "deterministic_fixed_navigation_task",
                "case_ids": list(task["case_ids"]),
                "baseline_tool_calls": int(task["baseline_tool_calls"]),
                "graph_tool_calls": 1,
                "outcome": "pass" if passed else "fail",
            }
        )
    tool_counts = {
        "baseline": sum(item["baseline_tool_calls"] for item in outcomes),
        "graph": sum(item["graph_tool_calls"] for item in outcomes),
    }
    return utility, outcomes, tool_counts


def evaluate_python_call_graph_fixture(
    fixture_root: Path,
    goldset: Mapping[str, Any],
) -> dict[str, Any]:
    fixture_root = fixture_root.resolve()
    started = time.perf_counter_ns()
    calls, skipped_files_count, skipped_errors = extract_python_calls(fixture_root)
    build_time_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)

    case_results = [_evaluate_case(calls, case) for case in goldset["cases"]]
    true_positives = sum(case["counts_as_true_positive"] for case in case_results)
    false_positives = sum(case["counts_as_false_positive"] for case in case_results)
    false_negatives = sum(case["counts_as_false_negative"] for case in case_results)
    unresolved_count = sum(case["actual_status"] != "resolved" for case in case_results)
    false_positive_classes = Counter(
        str(case.get("actual_reason") or "unknown")
        for case in case_results
        if case["counts_as_false_positive"]
    )
    call_bytes = _canonical_bytes(calls)
    navigation, agent_outcomes, tool_counts = _evaluate_navigation_tasks(
        goldset, case_results
    )
    all_cases_passed = all(case["passed"] for case in case_results)
    all_tasks_passed = all(item["outcome"] == "pass" for item in agent_outcomes)
    metrics = {
        "s1_precision": _ratio(
            true_positives, true_positives + false_positives
        ),
        "target_recall": _ratio(
            true_positives, true_positives + false_negatives
        ),
        "true_positive_count": true_positives,
        "false_positive_count": false_positives,
        "false_negative_count": false_negatives,
        "false_positive_classes": dict(sorted(false_positive_classes.items())),
        "unresolved_count": unresolved_count,
        "unresolved_share": _ratio(unresolved_count, len(case_results)),
        "serialized_call_bytes": len(call_bytes),
        "build_time_ms": build_time_ms,
        "baseline_tool_calls": tool_counts["baseline"],
        "graph_tool_calls": tool_counts["graph"],
        "tool_call_reduction": _ratio(
            tool_counts["baseline"] - tool_counts["graph"],
            tool_counts["baseline"],
        ),
        "navigation_utility": navigation["metrics"],
    }
    thresholds = goldset["thresholds"]
    threshold_checks = {
        "minimum_s1_precision": (
            metrics["s1_precision"] >= thresholds["minimum_s1_precision"]
        ),
        "minimum_target_recall": (
            metrics["target_recall"] >= thresholds["minimum_target_recall"]
        ),
        "minimum_context_path_reduction": (
            navigation["metrics"]["context_path_reduction_ratio"]
            >= thresholds["minimum_context_path_reduction"]
        ),
        "no_case_regression": (
            all_cases_passed
            and all_tasks_passed
            and navigation["metrics"]["no_case_regression"]
        ),
    }
    eligible = all(threshold_checks.values())
    return {
        "kind": "lenskit.python_call_graph_quality_benchmark",
        "version": "1.0",
        "scope": "fixed_python_goldset_and_deterministic_navigation_tasks",
        "evidence": {
            "goldset_sha256": _sha256(_canonical_bytes(goldset)),
            "fixture_sha256": _fixture_sha256(fixture_root),
            "call_records_sha256": _sha256(call_bytes),
        },
        "coverage": {
            "case_count": len(case_results),
            "category_count": len({case["category"] for case in case_results}),
            "call_record_count": len(calls),
            "skipped_files_count": skipped_files_count,
            "skipped_errors": skipped_errors,
        },
        "thresholds": dict(thresholds),
        "metrics": metrics,
        "cases": case_results,
        "agent_task_outcomes": agent_outcomes,
        "decision": {
            "threshold_checks": threshold_checks,
            "thresholds_met": eligible,
            "eligible_for_review": eligible,
            "default_promoted": False,
            "decision_authority": "Bureau",
            "reason": (
                "quality thresholds met; a separate reviewed Bureau decision "
                "is required"
                if eligible
                else "quality thresholds failed; default promotion remains prohibited"
            ),
        },
        "does_not_establish": list(goldset["does_not_establish"]),
    }


def evaluate_python_call_graph_goldset(
    goldset_path: Path,
    *,
    repository_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    goldset = load_python_call_graph_goldset(goldset_path)
    fixture_root = Path(goldset["fixture_root"])
    if not fixture_root.is_absolute():
        fixture_root = repository_root / fixture_root
    return evaluate_python_call_graph_fixture(fixture_root, goldset)


def stable_report_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return the deterministic report surface, excluding measured wall time."""

    projection = json.loads(json.dumps(report))
    projection["metrics"].pop("build_time_ms", None)
    return projection


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--goldset",
        type=Path,
        default=REPO_ROOT / "docs/retrieval/python_call_graph_goldset.v1.json",
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--out", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = evaluate_python_call_graph_goldset(
        args.goldset, repository_root=args.repo_root
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["decision"]["thresholds_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
