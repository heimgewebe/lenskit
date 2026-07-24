from __future__ import annotations

from pathlib import Path

import pytest

from merger.repoground.core import bundle_sidecars
from merger.repoground.core.artifact_io import is_sha256_digest


@pytest.mark.parametrize(
    "writer",
    [
        bundle_sidecars.write_python_symbol_index_json,
        bundle_sidecars.write_python_call_graph_json,
    ],
)
@pytest.mark.parametrize("invalid_digest", ["ERROR", "", "A" * 64, "g" * 64])
def test_navigation_sidecars_reject_invalid_dump_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    writer,
    invalid_digest: str,
) -> None:
    dump_index = tmp_path / "demo.dump_index.json"
    dump_index.write_text("{}\n", encoding="utf-8")
    manifest = tmp_path / "demo.bundle.manifest.json"
    monkeypatch.setattr(bundle_sidecars, "compute_file_sha256", lambda _path: invalid_digest)

    result = writer(
        base_manifest_path=manifest,
        repo_summaries=[{"root": str(tmp_path)}],
        final_dump_index=dump_index,
        run_id="run-1",
    )

    assert result is None
    assert not list(tmp_path.glob("demo.python_*_index.json"))
    assert not list(tmp_path.glob("demo.python_call_graph.json"))


def test_sha256_digest_contract_is_exact() -> None:
    assert is_sha256_digest("0" * 64) is True
    assert is_sha256_digest("a" * 64) is True
    assert is_sha256_digest("A" * 64) is False
    assert is_sha256_digest("0" * 63) is False
    assert is_sha256_digest("g" * 64) is False
    assert is_sha256_digest(None) is False
