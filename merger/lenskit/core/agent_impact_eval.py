"""Deterministic usefulness evaluator for agent impact context candidates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

KIND = "repobrief.agent_impact_usefulness_eval"
VERSION = "1.0"

DOES_NOT_ESTABLISH = (
    "agent_quality_improvement",
    "answer_correctness",
    "repository_understanding",
    "complete_blast_radius",
    "test_sufficiency",
    "review_completeness",
    "merge_readiness",
    "general_retrieval_quality",
    "default_promotion",
)


def _paths_from_context(context: Mapping[str, Any]) -> list[str]:
    paths: list[str] = []
    target = context.get("target")
    if isinstance(target, Mapping) and isinstance(target.get("paths"), list):
        paths.extend(
            item for item in target["paths"] if isinstance(item, str)
        )

    for section in (
        "target_symbols",
        "related_tests",
        "supporting_context",
        "entrypoints",
    ):
        values = context.get(section)
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, Mapping) and isinstance(item.get("path"), str):
                paths.append(item["path"])

    relations = context.get("relations")
    if isinstance(relations, list):
        for relation in relations:
            if not isinstance(relation, Mapping):
                continue
            for side in ("target", "peer"):
                endpoint = relation.get(side)
                if isinstance(endpoint, Mapping) and isinstance(
                    endpoint.get("path"),
                    str,
                ):
                    paths.append(endpoint["path"])
    return list(dict.fromkeys(paths))


def _recall(expected: list[str], observed: list[str]) -> float:
    if not expected:
        return 1.0
    observed_set = set(observed)
    return sum(path in observed_set for path in expected) / len(expected)


def _threshold(goldset: Mapping[str, Any]) -> float:
    value = goldset.get("minimum_target_recall_advantage", 0.2)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(
            "minimum_target_recall_advantage must be a number"
        )
    threshold = float(value)
    if threshold < 0.0 or threshold > 1.0:
        raise ValueError(
            "minimum_target_recall_advantage must be between 0 and 1"
        )
    return threshold


def evaluate_agent_impact_goldset(
    goldset: Any,
    observations: Any,
) -> dict[str, Any]:
    """Compare baseline navigation with impact contexts for a fixed goldset."""

    if not isinstance(goldset, Mapping):
        raise TypeError("goldset must be a mapping")
    if not isinstance(observations, Mapping):
        raise TypeError("observations must be a mapping")
    raw_cases = goldset.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("goldset.cases must be a non-empty list")
    minimum_advantage = _threshold(goldset)

    cases: list[dict[str, Any]] = []
    baseline_sum = 0.0
    impact_sum = 0.0
    missing_visibility_hits = 0

    for raw_case in raw_cases:
        if not isinstance(raw_case, Mapping):
            raise TypeError("goldset cases must be mappings")
        case_id = raw_case.get("id")
        expected = raw_case.get("expected_paths")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("goldset case id must be a non-empty string")
        if not isinstance(expected, list) or not all(
            isinstance(path, str) and path for path in expected
        ):
            raise ValueError(f"{case_id}.expected_paths must be strings")

        observation = observations.get(case_id)
        if not isinstance(observation, Mapping):
            observation = {}
        baseline_paths = observation.get("baseline_paths")
        if not isinstance(baseline_paths, list):
            baseline_paths = []
        baseline_paths = [
            path for path in baseline_paths if isinstance(path, str) and path
        ]
        context = observation.get("impact_context")
        if not isinstance(context, Mapping):
            context = {}
        impact_paths = _paths_from_context(context)

        baseline_recall = _recall(expected, baseline_paths)
        impact_recall = _recall(expected, impact_paths)
        baseline_sum += baseline_recall
        impact_sum += impact_recall

        gaps = context.get("gaps")
        statuses = context.get("source_statuses")
        missing_visible = bool(
            (isinstance(gaps, list) and gaps)
            or (
                isinstance(statuses, list)
                and any(
                    isinstance(item, Mapping)
                    and item.get("status") not in {"available", None}
                    for item in statuses
                )
            )
        )
        if missing_visible:
            missing_visibility_hits += 1

        cases.append(
            {
                "id": case_id,
                "expected_paths": list(expected),
                "baseline_paths": baseline_paths,
                "impact_paths": impact_paths,
                "baseline_recall": baseline_recall,
                "impact_recall": impact_recall,
                "recall_advantage": impact_recall - baseline_recall,
                "baseline_context_path_count": len(baseline_paths),
                "impact_context_path_count": len(impact_paths),
                "missing_evidence_visible": missing_visible,
            }
        )

    count = len(cases)
    baseline_recall = baseline_sum / count
    impact_recall = impact_sum / count
    advantage = impact_recall - baseline_recall
    no_case_regression = all(
        item["impact_recall"] >= item["baseline_recall"] for item in cases
    )
    established = advantage >= minimum_advantage and no_case_regression
    return {
        "kind": KIND,
        "version": VERSION,
        "goldset_id": goldset.get("id"),
        "case_count": count,
        "cases": cases,
        "metrics": {
            "baseline_target_recall": baseline_recall,
            "impact_target_recall": impact_recall,
            "target_recall_advantage": advantage,
            "minimum_target_recall_advantage": minimum_advantage,
            "no_case_regression": no_case_regression,
            "missing_evidence_visibility_rate": (
                missing_visibility_hits / count
            ),
        },
        "decision": {
            "navigation_utility_established_for_goldset": established,
            "default_promoted": False,
            "reason": (
                "fixed_goldset_threshold_met_without_case_regression"
                if established
                else "fixed_goldset_threshold_or_non_regression_not_met"
            ),
        },
        "does_not_establish": list(DOES_NOT_ESTABLISH),
    }


__all__ = ["evaluate_agent_impact_goldset"]
