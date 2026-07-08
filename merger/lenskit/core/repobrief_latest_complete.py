"""Latest-complete RepoBrief bundle registry.

The registry is a small, machine-readable pointer to the latest known complete
bundle for a repository/ref lane. It is not an automatic refresh mechanism.
Read paths may compare recorded snapshot provenance to an explicitly supplied
local repo HEAD, but they must never create snapshots, mutate Git, or update the
registry as a side effect.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

KIND = "repobrief.latest_complete_registry"
VERSION = "v1"
STATUS_KIND = "repobrief.latest_complete_status"
WRITE_KIND = "repobrief.latest_complete_registry_write"

FRESHNESS_VALUES = ("fresh", "stale", "unknown", "not_comparable")
HEALTH_VALUES = ("pass", "warn", "fail", "unknown")

DOES_NOT_ESTABLISH = (
    "truth",
    "correctness",
    "completeness",
    "runtime_behavior",
    "test_sufficiency",
    "regression_absence",
    "repo_understood",
    "claims_true",
    "forensic_ready",
    "freshness_against_remote",
    "merge_readiness",
    "agent_quality_improvement",
)


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"{label} does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON: {path}") from exc
    except UnicodeError as exc:
        raise ValueError(f"{label} is not valid UTF-8: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object")
    return data


def _manifest_stem(path: Path) -> str:
    suffix = ".bundle.manifest.json"
    if path.name.endswith(suffix):
        return path.name[: -len(suffix)]
    return path.stem


def _relative_or_absolute(target: Path, base_dir: Path | None) -> str:
    target = target.resolve()
    if base_dir is None:
        return str(target)
    try:
        return Path(os.path.relpath(target, base_dir.resolve())).as_posix()
    except ValueError:
        return str(target)


def _safe_bundle_path(registry_path: Path, raw_path: Any) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    candidate = (registry_path.parent / raw_path).resolve()
    if candidate.is_file():
        return candidate
    absolute = Path(raw_path).expanduser().resolve()
    if absolute.is_file():
        return absolute
    return candidate


def _source_repositories(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    provenance = manifest.get("snapshot_provenance")
    repositories = provenance.get("repositories") if isinstance(provenance, dict) else None
    if not isinstance(repositories, list):
        return []
    result: list[dict[str, Any]] = []
    for repo in repositories:
        if not isinstance(repo, dict):
            continue
        result.append(
            {
                "name": repo.get("name") if isinstance(repo.get("name"), str) else None,
                "repo_remote": repo.get("repo_remote") if isinstance(repo.get("repo_remote"), str) else None,
                "repo_root_recorded": isinstance(repo.get("repo_root"), str) and bool(repo.get("repo_root")),
                "git_commit": repo.get("git_commit") if isinstance(repo.get("git_commit"), str) else None,
                "git_dirty": repo.get("git_dirty") if isinstance(repo.get("git_dirty"), bool) else None,
                "git_branch": repo.get("git_branch") if isinstance(repo.get("git_branch"), str) else None,
                "provenance_status": repo.get("provenance_status") if isinstance(repo.get("provenance_status"), str) else "unknown",
                "freshness_basis": repo.get("freshness_basis") if isinstance(repo.get("freshness_basis"), str) else "unknown",
            }
        )
    return result


def _primary_source_commit(repositories: list[dict[str, Any]]) -> tuple[str | None, str]:
    present = [
        repo for repo in repositories
        if repo.get("provenance_status") == "present" and isinstance(repo.get("git_commit"), str) and repo.get("git_commit")
    ]
    if not present:
        return None, "snapshot_commit_missing"
    if len(present) > 1:
        commits = {repo["git_commit"] for repo in present}
        if len(commits) == 1:
            return present[0]["git_commit"], "single_commit_multi_repo"
        return None, "multiple_source_commits_not_comparable"
    return present[0]["git_commit"], "single_repo_commit"


def _artifact_by_role(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    artifacts = manifest.get("artifacts")
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(artifacts, list):
        return result
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        role = artifact.get("role")
        if isinstance(role, str) and role not in result:
            result[role] = artifact
    return result


def _linked_path_for_role(manifest: Mapping[str, Any], role: str) -> str | None:
    role_to_link = {
        "post_emit_health": "post_emit_health_path",
        "bundle_surface_validation": "bundle_surface_validation_path",
        "output_health": "output_health_path",
    }
    links = manifest.get("links")
    key = role_to_link.get(role)
    if isinstance(links, dict) and key and isinstance(links.get(key), str):
        return links[key]
    return None


def _status_from_doc(role: str, doc: Mapping[str, Any]) -> str | None:
    if role == "output_health":
        value = doc.get("verdict") or doc.get("status")
    else:
        value = doc.get("status") or doc.get("verdict")
    if isinstance(value, str) and value in {"pass", "warn", "fail"}:
        return value
    if isinstance(value, str) and value in {"blocked", "invalid"}:
        return "fail"
    return None


def _health_signals(manifest_path: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = _artifact_by_role(manifest)
    signals: dict[str, Any] = {}
    for role in ("output_health", "post_emit_health", "bundle_surface_validation"):
        artifact = artifacts.get(role)
        raw_path = artifact.get("path") if isinstance(artifact, dict) else None
        if raw_path is None:
            raw_path = _linked_path_for_role(manifest, role)
        if not isinstance(raw_path, str) or not raw_path:
            signals[role] = {"status": "unknown", "path": None, "reason": "not_listed"}
            continue
        candidate = (manifest_path.parent / raw_path).resolve()
        try:
            candidate.relative_to(manifest_path.parent.resolve())
        except ValueError:
            signals[role] = {"status": "fail", "path": raw_path, "reason": "path_escapes_bundle_root"}
            continue
        if not candidate.is_file():
            signals[role] = {"status": "unknown", "path": raw_path, "reason": "file_missing"}
            continue
        try:
            doc = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            signals[role] = {"status": "fail", "path": raw_path, "reason": "unreadable", "error": str(exc)}
            continue
        if not isinstance(doc, dict):
            signals[role] = {"status": "fail", "path": raw_path, "reason": "not_object"}
            continue
        status = _status_from_doc(role, doc)
        signals[role] = {
            "status": status or "unknown",
            "path": raw_path,
            "reason": None if status else "status_missing_or_unrecognized",
            "kind": doc.get("kind") if isinstance(doc.get("kind"), str) else None,
        }
    return signals


def _aggregate_health(signals: Mapping[str, Any]) -> str:
    statuses = [
        signal.get("status")
        for signal in signals.values()
        if isinstance(signal, Mapping) and isinstance(signal.get("status"), str)
    ]
    if any(status == "fail" for status in statuses):
        return "fail"
    if any(status == "warn" for status in statuses):
        return "warn"
    if any(status == "pass" for status in statuses):
        return "pass"
    return "unknown"


def _unknown_freshness(reason: str, *, checked_at: str | None = None) -> dict[str, Any]:
    return {
        "status": "unknown",
        "reason": reason,
        "checked_at": checked_at,
        "snapshot_commit": None,
        "live_head": None,
        "head_drift": None,
        "basis": "git_commit",
    }


def _git(repo: Path, *args: str) -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    if result.returncode != 0:
        return None, (result.stderr or result.stdout or "git command failed").strip()
    return result.stdout.strip(), None


def evaluate_registry_freshness(
    registry: Mapping[str, Any],
    *,
    repo: str | Path | None = None,
    checked_at: str | None = None,
) -> dict[str, Any]:
    checked_at = checked_at or _now_iso()
    snapshot_commit = registry.get("source", {}).get("commit") if isinstance(registry.get("source"), Mapping) else None
    if not isinstance(snapshot_commit, str) or not snapshot_commit:
        return _unknown_freshness("snapshot_commit_missing", checked_at=checked_at)
    if repo is None:
        result = _unknown_freshness("live_repo_not_provided", checked_at=checked_at)
        result["snapshot_commit"] = snapshot_commit
        return result
    repo_path = Path(repo).expanduser().resolve()
    if not repo_path.is_dir():
        result = _unknown_freshness("live_repo_not_directory", checked_at=checked_at)
        result["snapshot_commit"] = snapshot_commit
        return result
    live_head, err = _git(repo_path, "rev-parse", "HEAD")
    if err is not None or not live_head:
        result = _unknown_freshness("live_head_unavailable", checked_at=checked_at)
        result["snapshot_commit"] = snapshot_commit
        result["error"] = err
        return result
    status, status_err = _git(repo_path, "status", "--porcelain")
    dirty = None if status_err is not None else bool(status)
    head_drift = live_head != snapshot_commit
    return {
        "status": "stale" if head_drift else "fresh",
        "reason": "head_drift" if head_drift else "head_matches_snapshot_commit",
        "checked_at": checked_at,
        "snapshot_commit": snapshot_commit,
        "live_head": live_head,
        "head_drift": head_drift,
        "live_git_dirty": dirty,
        "basis": "git_commit",
    }


def build_latest_complete_registry(
    bundle_manifest: str | Path,
    *,
    registry_path: str | Path | None = None,
    checked_at: str | None = None,
) -> dict[str, Any]:
    manifest_path = Path(bundle_manifest).expanduser().resolve()
    manifest = _read_json_object(manifest_path, label="bundle manifest")
    registry_target = Path(registry_path).expanduser().resolve() if registry_path is not None else None
    base_dir = registry_target.parent if registry_target is not None else None
    repositories = _source_repositories(manifest)
    source_commit, source_reason = _primary_source_commit(repositories)
    signals = _health_signals(manifest_path, manifest)
    registry: dict[str, Any] = {
        "kind": KIND,
        "version": VERSION,
        "updated_at": checked_at or _now_iso(),
        "bundle": {
            "stem": _manifest_stem(manifest_path),
            "manifest_path": _relative_or_absolute(manifest_path, base_dir),
            "manifest_sha256": _sha256_file(manifest_path),
            "run_id": manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None,
            "generated_at": manifest.get("created_at") if isinstance(manifest.get("created_at"), str) else None,
        },
        "source": {
            "commit": source_commit,
            "commit_status": source_reason,
            "repositories": repositories,
        },
        "health": {
            "status": _aggregate_health(signals),
            "signals": signals,
            "health_values": list(HEALTH_VALUES),
        },
        "freshness": {
            "status": "unknown",
            "reason": "live_repo_not_checked",
            "checked_at": None,
            "snapshot_commit": source_commit,
            "live_head": None,
            "head_drift": None,
            "basis": "git_commit" if source_commit else "unknown",
            "freshness_values": list(FRESHNESS_VALUES),
        },
        "mutation_boundary": {
            "writes": ["latest_complete_registry"] if registry_target is not None else [],
            "does_not_mutate": ["git", "pull_requests", "patches", "source_working_tree", "brief_bundle_artifacts"],
            "read_paths_do_not_refresh": True,
            "hidden_refresh_allowed": False,
        },
        "does_not_establish": list(DOES_NOT_ESTABLISH),
    }
    return registry


def write_latest_complete_registry(
    bundle_manifest: str | Path,
    output_path: str | Path,
    *,
    checked_at: str | None = None,
) -> dict[str, Any]:
    out = Path(output_path).expanduser().resolve()
    registry = build_latest_complete_registry(
        bundle_manifest,
        registry_path=out,
        checked_at=checked_at,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=str(out.parent),
            prefix=f".{out.name}.",
            suffix=".tmp",
        ) as handle:
            json.dump(registry, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            tmp_path = Path(handle.name)
        os.replace(tmp_path, out)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()
    return {
        "kind": WRITE_KIND,
        "version": VERSION,
        "status": "ok",
        "registry_path": str(out),
        "registry": registry,
        "mutation_boundary": {
            "writes": ["latest_complete_registry"],
            "does_not_mutate": ["git", "pull_requests", "patches", "source_working_tree", "brief_bundle_artifacts"],
            "read_paths_do_not_refresh": True,
            "hidden_refresh_allowed": False,
        },
        "does_not_establish": list(DOES_NOT_ESTABLISH),
    }


def latest_complete_status(
    registry_path: str | Path,
    *,
    repo: str | Path | None = None,
    checked_at: str | None = None,
) -> dict[str, Any]:
    path = Path(registry_path).expanduser().resolve()
    registry = _read_json_object(path, label="latest-complete registry")
    if registry.get("kind") != KIND:
        raise ValueError(f"latest-complete registry kind must be {KIND}")
    bundle_info = registry.get("bundle") if isinstance(registry.get("bundle"), dict) else {}
    bundle_path = _safe_bundle_path(path, bundle_info.get("manifest_path") if isinstance(bundle_info, dict) else None)
    manifest_hash_status = "unknown"
    observed_manifest_sha256 = None
    if bundle_path is not None and bundle_path.is_file():
        observed_manifest_sha256 = _sha256_file(bundle_path)
        expected = bundle_info.get("manifest_sha256") if isinstance(bundle_info, dict) else None
        manifest_hash_status = "match" if expected == observed_manifest_sha256 else "mismatch"
    elif bundle_path is not None:
        manifest_hash_status = "missing"
    freshness = evaluate_registry_freshness(registry, repo=repo, checked_at=checked_at)
    status = "ok"
    if manifest_hash_status in {"mismatch", "missing"}:
        status = "warn"
    return {
        "kind": STATUS_KIND,
        "version": VERSION,
        "status": status,
        "registry_path": str(path),
        "registry": registry,
        "bundle_manifest": str(bundle_path) if bundle_path is not None else None,
        "manifest_hash": {
            "status": manifest_hash_status,
            "expected_sha256": bundle_info.get("manifest_sha256") if isinstance(bundle_info, dict) else None,
            "observed_sha256": observed_manifest_sha256,
        },
        "freshness": freshness,
        "mutation_boundary": {
            "writes": [],
            "does_not_mutate": ["git", "pull_requests", "patches", "source_working_tree", "brief_bundle_artifacts", "latest_complete_registry"],
            "read_paths_do_not_refresh": True,
            "hidden_refresh_allowed": False,
        },
        "does_not_establish": list(DOES_NOT_ESTABLISH),
    }
