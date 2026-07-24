from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path

import pytest

from merger.repoground.core import clock, merge


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "report_renderer"
REPO_ROOT = FIXTURE_ROOT / "repo"
GOLDEN_ROOT = FIXTURE_ROOT / "golden"
FROZEN_TIME = datetime.datetime(2026, 7, 24, 12, 0, tzinfo=datetime.timezone.utc)


_FILE_SPECS = (
    ("README.md", "doc", ["ai-context"]),
    ("src/main.py", "source", ["entrypoint"]),
    ("docs/guide.md", "doc", ["runbook"]),
    (".github/workflows/ci.yml", "config", ["ci"]),
)


def _files() -> list[merge.FileInfo]:
    result = []
    for rel_path, category, tags in _FILE_SPECS:
        path = REPO_ROOT / rel_path
        payload = path.read_bytes()
        result.append(
            merge.FileInfo(
                root_label="report-fixture",
                abs_path=path,
                rel_path=Path(rel_path),
                size=len(payload),
                is_text=True,
                md5=hashlib.md5(payload, usedforsecurity=False).hexdigest(),
                category=category,
                tags=list(tags),
                ext=path.suffix,
                content=None,
                inclusion_reason="normal",
            )
        )
    return result


def _scenario_kwargs(name: str) -> dict[str, object]:
    common: dict[str, object] = {
        "files": _files(),
        "max_file_bytes": 0,
        "sources": [REPO_ROOT],
        "debug": False,
    }
    if name == "full_extras":
        return common | {
            "level": "max",
            "plan_only": False,
            "extras": merge.ExtrasConfig(
                organism_index=True,
                delta_reports=True,
                heatmap=True,
            ),
            "delta_meta": {
                "base_import": "2026-07-23T12:00:00Z",
                "current_timestamp": "2026-07-24T12:00:00Z",
                "summary": {
                    "files_added": 1,
                    "files_removed": 0,
                    "files_changed": 2,
                },
            },
            "artifact_refs": {
                "index_json_basename": "fixture.index.json",
                "augment_sidecar_basename": "fixture.augment.json",
            },
            "meta_density": "full",
        }
    if name == "plan_filtered":
        return common | {
            "level": "summary",
            "plan_only": True,
            "path_filter": "docs/",
            "meta_density": "auto",
        }
    if name == "machine_redacted":
        return common | {
            "level": "machine-lean",
            "plan_only": False,
            "code_only": True,
            "meta_density": "min",
            "redact_secrets": True,
        }
    raise AssertionError(f"unknown scenario: {name}")


def _render(name: str) -> list[str]:
    with clock.frozen(FROZEN_TIME):
        return list(merge.iter_report_blocks(**_scenario_kwargs(name)))


def _block_manifest(blocks: list[str]) -> dict[str, object]:
    return {
        "block_count": len(blocks),
        "joined_sha256": hashlib.sha256("".join(blocks).encode()).hexdigest(),
        "blocks": [
            {
                "index": index,
                "bytes": len(block.encode()),
                "sha256": hashlib.sha256(block.encode()).hexdigest(),
            }
            for index, block in enumerate(blocks)
        ],
    }


@pytest.mark.parametrize("name", ["full_extras", "plan_filtered", "machine_redacted"])
def test_report_renderer_matches_byte_and_block_goldens(name: str) -> None:
    blocks = _render(name)

    assert "".join(blocks) == json.loads(
        (GOLDEN_ROOT / f"{name}.text.json").read_text(encoding="utf-8")
    )
    assert _block_manifest(blocks) == json.loads(
        (GOLDEN_ROOT / f"{name}.blocks.json").read_text(encoding="utf-8")
    )


def test_report_renderer_stays_lazy_before_content(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fail_if_read_early(file_info: merge.FileInfo, _max_bytes: int):
        calls.append(file_info.rel_path.as_posix())
        raise AssertionError("content was read before the content section")

    monkeypatch.setattr(merge, "read_smart_content", fail_if_read_early)
    with clock.frozen(FROZEN_TIME):
        iterator = merge.iter_report_blocks(**_scenario_kwargs("full_extras"))
        first = next(iterator)
        second = next(iterator)

    assert first.startswith("<!-- READING_POLICY")
    assert second.startswith("## Plan")
    assert calls == []


def test_redacted_golden_contains_no_fixture_secret() -> None:
    report = "".join(_render("machine_redacted"))

    assert "fixture-secret-value-1234567890" not in report
    assert "[REDACTED" in report
