import json
from pathlib import Path

from merger.lenskit.core.repobrief_live_freshness import evaluate_live_freshness


def _manifest(
    tmp_path: Path,
    *,
    repo_root: Path | None,
    commit: str = "a" * 40,
    dirty: bool | None = False,
    provenance_status: str = "present",
) -> Path:
    record = {
        "name": repo_root.name if repo_root is not None else "demo",
        "repo_root": str(repo_root) if repo_root is not None else None,
        "git_commit": commit,
        "git_dirty": dirty,
        "git_branch": "main",
        "provenance_status": provenance_status,
        "freshness_basis": "git_commit",
    }
    path = tmp_path / "demo.bundle.manifest.json"
    path.write_text(
        json.dumps(
            {
                "kind": "repolens.bundle.manifest",
                "run_id": "demo",
                "artifacts": [],
                "snapshot_provenance": {
                    "version": "v1",
                    "repositories": [record],
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _current(repo_root: Path, *, commit: str = "a" * 40, dirty: bool | None = False):
    def probe(_path: str | Path) -> dict[str, object]:
        return {
            "name": repo_root.name,
            "repo_root": str(repo_root),
            "git_commit": commit,
            "git_dirty": dirty,
            "git_branch": "main",
            "provenance_status": "present",
            "freshness_basis": "git_commit_and_working_tree",
        }

    return probe


def test_live_freshness_is_fresh_only_for_same_clean_commit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, repo_root=repo)

    result = evaluate_live_freshness(manifest, repo_root=repo, probe=_current(repo))

    assert result["status"] == "fresh"
    assert result["reason"] == "git_head_matches_and_working_tree_is_clean"
    assert result["read_only_git_probe"] is True
    assert result["implicit_refresh"] is False


def test_live_freshness_marks_changed_head_stale(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, repo_root=repo)

    result = evaluate_live_freshness(
        manifest,
        repo_root=repo,
        probe=_current(repo, commit="b" * 40),
    )

    assert result["status"] == "stale"
    assert result["reason"] == "git_head_mismatch"


def test_live_freshness_marks_dirty_current_tree_stale(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, repo_root=repo)

    result = evaluate_live_freshness(
        manifest,
        repo_root=repo,
        probe=_current(repo, dirty=True),
    )

    assert result["status"] == "stale"
    assert result["reason"] == "current_working_tree_is_dirty"


def test_live_freshness_does_not_call_probe_for_dirty_snapshot(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, repo_root=repo, dirty=True)
    calls = []

    def probe(_path):
        calls.append(_path)
        raise AssertionError("probe must not run")

    result = evaluate_live_freshness(manifest, repo_root=repo, probe=probe)

    assert result["status"] == "stale"
    assert result["reason"] == "snapshot_was_created_from_dirty_working_tree"
    assert calls == []


def test_live_freshness_is_unknown_when_snapshot_cleanliness_is_missing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, repo_root=repo, dirty=None)

    result = evaluate_live_freshness(manifest, repo_root=repo, probe=_current(repo))

    assert result["status"] == "unknown"
    assert result["reason"] == "snapshot_working_tree_cleanliness_unavailable"


def test_live_freshness_is_not_comparable_without_repo_root(tmp_path):
    manifest = _manifest(tmp_path, repo_root=None)

    result = evaluate_live_freshness(manifest, probe=lambda _path: {})

    assert result["status"] == "not_comparable"
    assert result["reason"] == "repo_root_redacted_or_missing"


def test_live_freshness_rejects_explicit_mismatched_repository(tmp_path):
    snapshot_repo = tmp_path / "snapshot-repo"
    requested_repo = tmp_path / "other-repo"
    snapshot_repo.mkdir()
    requested_repo.mkdir()
    manifest = _manifest(tmp_path, repo_root=snapshot_repo)

    result = evaluate_live_freshness(
        manifest,
        repo_root=requested_repo,
        probe=_current(requested_repo),
    )

    assert result["status"] == "unknown"
    assert result["reason"] == "repository_selection_ambiguous"
