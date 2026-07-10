#!/usr/bin/env python3
"""Fail when raw CodeQL SARIF files contain any result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _result_summary(result: dict[str, Any]) -> str:
    rule = result.get("ruleId") or "unknown-rule"
    locations = result.get("locations") or []
    if not locations:
        return rule
    physical = locations[0].get("physicalLocation") or {}
    path = (physical.get("artifactLocation") or {}).get("uri") or "unknown-path"
    line = (physical.get("region") or {}).get("startLine") or "?"
    return f"{rule} at {path}:{line}"


def collect_results(directory: Path) -> tuple[list[Path], list[str]]:
    if not directory.is_dir():
        raise ValueError(f"SARIF output directory not found: {directory}")

    sarif_files = sorted(directory.rglob("*.sarif"))
    if not sarif_files:
        raise ValueError(f"No SARIF files found beneath: {directory}")

    findings: list[str] = []
    for sarif_path in sarif_files:
        try:
            document = json.loads(sarif_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid SARIF file: {sarif_path}") from exc
        for run in document.get("runs") or []:
            for result in run.get("results") or []:
                findings.append(_result_summary(result))
    return sarif_files, findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()

    try:
        sarif_files, findings = collect_results(args.directory)
    except ValueError as exc:
        print(f"CodeQL SARIF gate error: {exc}")
        return 2

    print(f"Inspected {len(sarif_files)} raw SARIF file(s).")
    if findings:
        print(f"CodeQL raw SARIF contains {len(findings)} finding(s):")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print("CodeQL raw SARIF contains no findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
