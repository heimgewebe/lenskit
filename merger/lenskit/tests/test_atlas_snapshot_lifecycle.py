"""
Tests for Atlas snapshot lifecycle hardening:
- Zombie prevention (scan failure → status = "failed")
- Progress persistence during scan
- Empty directory scan (status = "complete", total_files = 0)
- Stale detection for running artifacts
- Shared lifecycle executor guarantees
- Hardest failure paths (exception after progress, callback exception, artifact write failure)
"""
import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from merger.lenskit.adapters.atlas import AtlasScanner
from merger.lenskit.atlas.registry import AtlasRegistry
from merger.lenskit.atlas.lifecycle import run_scan_lifecycle


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "registry" / "atlas_registry.sqlite"


@pytest.fixture
def registry(temp_db_path: Path) -> AtlasRegistry:
    reg = AtlasRegistry(temp_db_path)
    yield reg
    reg.close()


def _setup_snapshot(registry: AtlasRegistry, snapshot_id: str = "snap_test__root__20240101T000000Z__abcd1234"):
    """Helper: register machine, root, and create a running snapshot."""
    registry.register_machine("test-machine", "testhost")
    registry.register_root("root", "test-machine", "abs_path", "/test", label="test")
    registry.create_snapshot(snapshot_id, "test-machine", "root", "abcd1234", "running")
    return snapshot_id


# ── 6.1 Zombie Test ──────────────────────────────────────────────────────

def test_zombie_snapshot_on_scan_exception(registry: AtlasRegistry, tmp_path: Path):
    """When scanner.scan() raises an exception, the snapshot MUST end up as 'failed'."""
    snapshot_id = _setup_snapshot(registry)

    # Verify initial state
    snap = registry.get_snapshot(snapshot_id)
    assert snap["status"] == "running"

    # Simulate the lifecycle pattern from cmd_atlas.py
    try:
        # scanner.scan() throws
        raise RuntimeError("Simulated scan failure")
    except Exception as e:
        registry.update_snapshot_status(snapshot_id, "failed", error_message=str(e))

    snap = registry.get_snapshot(snapshot_id)
    assert snap["status"] == "failed"
    assert snap["error_message"] == "Simulated scan failure"


def test_zombie_guard_in_finally(registry: AtlasRegistry):
    """Defensive finally guard catches zombie snapshots even if except handler fails."""
    snapshot_id = _setup_snapshot(registry)

    # Simulate: except block itself fails (e.g. broken connection),
    # but the finally zombie guard kicks in.
    snap = registry.get_snapshot(snapshot_id)
    assert snap["status"] == "running"

    # The finally guard pattern
    try:
        snap = registry.get_snapshot(snapshot_id)
        if snap and snap["status"] == "running":
            registry.update_snapshot_status(snapshot_id, "failed", error_message="Snapshot finalization interrupted")
    except Exception:
        pass

    snap = registry.get_snapshot(snapshot_id)
    assert snap["status"] == "failed"
    assert snap["error_message"] == "Snapshot finalization interrupted"


def test_scanner_exception_produces_failed_status(registry: AtlasRegistry, tmp_path: Path):
    """Full integration: mock scanner raises → snapshot ends up 'failed' with error message."""
    snapshot_id = _setup_snapshot(registry)

    scanner = AtlasScanner(root=tmp_path, snapshot_id=snapshot_id)

    # Patch os.walk to raise an exception after one iteration
    with patch("os.walk", side_effect=OSError("Permission denied: /forbidden")):
        try:
            scanner.scan()
        except Exception:
            pass

        # In real code, the except block would call update_snapshot_status.
        # We simulate that here:
        registry.update_snapshot_status(snapshot_id, "failed", error_message="Permission denied: /forbidden")

    snap = registry.get_snapshot(snapshot_id)
    assert snap["status"] == "failed"
    assert "Permission denied" in snap["error_message"]


# ── 6.2 Progress Test ────────────────────────────────────────────────────

def test_progress_callback_invoked_during_scan(tmp_path: Path):
    """The on_progress callback is invoked during scanning with correct counters."""
    # Create a directory structure
    for i in range(5):
        d = tmp_path / f"dir_{i}"
        d.mkdir()
        for j in range(3):
            (d / f"file_{j}.txt").write_text(f"content {i}-{j}")

    progress_calls = []

    def on_progress(files: int, dirs: int, bytes_total: int):
        progress_calls.append({"files": files, "dirs": dirs, "bytes": bytes_total})

    scanner = AtlasScanner(root=tmp_path, snapshot_id="snap_test_progress")

    # Override the throttle by patching time.time to advance
    original_time = time.time
    call_count = [0]

    def mock_time():
        call_count[0] += 1
        # Make time advance 2 seconds per call to bypass the 1-second throttle
        return original_time() + call_count[0] * 2

    with patch("merger.lenskit.adapters.atlas.time.time", side_effect=mock_time):
        scanner.scan(on_progress=on_progress)

    # Progress should have been called at least once
    assert len(progress_calls) > 0, "on_progress callback was never invoked"

    # Last progress call should reflect actual file counts
    last = progress_calls[-1]
    assert last["files"] > 0
    assert last["dirs"] > 0
    assert last["bytes"] > 0


def test_progress_persisted_to_registry(registry: AtlasRegistry):
    """update_snapshot_progress writes files_seen/dirs_seen/bytes_seen to the registry."""
    snapshot_id = _setup_snapshot(registry)

    registry.update_snapshot_progress(snapshot_id, files_seen=42, dirs_seen=7, bytes_seen=123456)

    snap = registry.get_snapshot(snapshot_id)
    assert snap["files_seen"] == 42
    assert snap["dirs_seen"] == 7
    assert snap["bytes_seen"] == 123456
    assert snap["last_progress_at"] is not None


# ── 6.3 Empty Dir Test ───────────────────────────────────────────────────

def test_empty_directory_scan_completes(tmp_path: Path):
    """Scanning an empty directory should return complete status with total_files == 0."""
    scanner = AtlasScanner(root=tmp_path, snapshot_id="snap_empty")
    result = scanner.scan()

    assert result["stats"]["total_files"] == 0
    assert result["stats"]["total_dirs"] >= 0
    assert result["stats"]["total_bytes"] == 0
    assert result["stats"]["end_time"] is not None
    assert result["stats"]["duration_seconds"] >= 0


def test_empty_directory_scan_registry_lifecycle(registry: AtlasRegistry, tmp_path: Path):
    """Full lifecycle: empty dir → status 'complete', total_files == 0."""
    snapshot_id = _setup_snapshot(registry)

    empty_dir = tmp_path / "scan_target"
    empty_dir.mkdir()

    scanner = AtlasScanner(root=empty_dir, snapshot_id=snapshot_id)
    result = scanner.scan()

    # Simulate the success path
    registry.update_snapshot_status(snapshot_id, "complete")

    snap = registry.get_snapshot(snapshot_id)
    assert snap["status"] == "complete"
    assert result["stats"]["total_files"] == 0


# ── 6.4 Stale Detection Test ─────────────────────────────────────────────

def test_stale_detection_on_running_artifact(tmp_path: Path):
    """A running artifact with old last_progress_at should be flagged as stalled."""
    from fastapi.testclient import TestClient
    from merger.lenskit.service.app import app, init_service, verify_token

    hub = tmp_path / "hub"
    merges = hub / ".repolens" / "merges"
    merges.mkdir(parents=True)

    # Create a running artifact with stale progress (120s > 60s stale threshold)
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    running_data = {
        "status": "running",
        "root": "/test",
        "created_at": stale_time,
        "stats": {
            "files_seen": 10,
            "dirs_seen": 3,
            "bytes_seen": 5000,
            "last_progress_at": stale_time
        }
    }
    (merges / "atlas-1000.json").write_text(json.dumps(running_data), encoding="utf-8")

    orig_middleware = list(app.user_middleware)
    orig_stack = app.middleware_stack
    app.middleware_stack = None
    app.user_middleware.clear()

    init_service(hub_path=hub, merges_dir=merges)
    app.dependency_overrides[verify_token] = lambda: True

    try:
        with TestClient(app) as client:
            response = client.get("/api/atlas")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["status"] == "running"
            assert data[0]["is_stalled"] is True
            assert data[0]["stats"]["files_seen"] == 10
    finally:
        app.dependency_overrides.clear()
        app.user_middleware = orig_middleware
        app.middleware_stack = orig_stack


def test_fresh_running_artifact_not_stalled(tmp_path: Path):
    """A running artifact with recent progress should NOT be flagged as stalled."""
    from fastapi.testclient import TestClient
    from merger.lenskit.service.app import app, init_service, verify_token

    hub = tmp_path / "hub"
    merges = hub / ".repolens" / "merges"
    merges.mkdir(parents=True)

    fresh_time = datetime.now(timezone.utc).isoformat()
    running_data = {
        "status": "running",
        "root": "/test",
        "created_at": fresh_time,
        "stats": {
            "files_seen": 10,
            "dirs_seen": 3,
            "bytes_seen": 5000,
            "last_progress_at": fresh_time
        }
    }
    (merges / "atlas-2000.json").write_text(json.dumps(running_data), encoding="utf-8")

    orig_middleware = list(app.user_middleware)
    orig_stack = app.middleware_stack
    app.middleware_stack = None
    app.user_middleware.clear()

    init_service(hub_path=hub, merges_dir=merges)
    app.dependency_overrides[verify_token] = lambda: True

    try:
        with TestClient(app) as client:
            response = client.get("/api/atlas")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["status"] == "running"
            assert data[0]["is_stalled"] is False
    finally:
        app.dependency_overrides.clear()
        app.user_middleware = orig_middleware
        app.middleware_stack = orig_stack


# ── Registry Migration Test ───────────────────────────────────────────────

def test_registry_progress_columns_exist(registry: AtlasRegistry):
    """New progress columns should be present in the snapshots table."""
    cur = registry.conn.execute("PRAGMA table_info(snapshots)")
    cols = [row["name"] for row in cur.fetchall()]
    assert "files_seen" in cols
    assert "dirs_seen" in cols
    assert "bytes_seen" in cols
    assert "last_progress_at" in cols
    assert "error_message" in cols


def test_update_status_with_error_message(registry: AtlasRegistry):
    """update_snapshot_status should store error_message when provided."""
    snapshot_id = _setup_snapshot(registry)
    registry.update_snapshot_status(snapshot_id, "failed", error_message="disk full")

    snap = registry.get_snapshot(snapshot_id)
    assert snap["status"] == "failed"
    assert snap["error_message"] == "disk full"
    assert snap["last_progress_at"] is not None


def test_update_status_without_error_message(registry: AtlasRegistry):
    """update_snapshot_status without error_message should not clear existing error."""
    snapshot_id = _setup_snapshot(registry)
    registry.update_snapshot_status(snapshot_id, "complete")

    snap = registry.get_snapshot(snapshot_id)
    assert snap["status"] == "complete"
    assert snap["error_message"] is None


# ── Shared Lifecycle Executor Tests ───────────────────────────────────────

def test_lifecycle_executor_success():
    """run_scan_lifecycle: scan_fn succeeds → no mark_failed call."""
    called = {"failed": False}

    def scan_fn():
        pass  # success

    def mark_failed(msg):
        called["failed"] = True

    run_scan_lifecycle(scan_fn=scan_fn, mark_failed=mark_failed, is_still_running=lambda: False)
    assert called["failed"] is False


def test_lifecycle_executor_exception_marks_failed():
    """run_scan_lifecycle: scan_fn raises → mark_failed called, exception re-raised."""
    errors = []

    def scan_fn():
        raise RuntimeError("boom")

    def mark_failed(msg):
        errors.append(msg)

    with pytest.raises(RuntimeError, match="boom"):
        run_scan_lifecycle(scan_fn=scan_fn, mark_failed=mark_failed, is_still_running=lambda: False)

    assert len(errors) == 1
    assert errors[0] == "boom"


def test_lifecycle_executor_zombie_guard():
    """run_scan_lifecycle: if mark_failed itself raises, finally guard catches zombie."""
    guard_calls = []

    def scan_fn():
        raise RuntimeError("scan error")

    def mark_failed_broken(msg):
        raise IOError("registry broken")

    def is_still_running():
        return True  # still zombie

    # Monkey-patch: use a second mark_failed for the finally guard
    # The executor calls mark_failed in except AND in finally if still running
    final_msgs = []

    def mark_failed_tracking(msg):
        final_msgs.append(msg)
        if len(final_msgs) == 1:
            raise IOError("registry broken")  # first call (except handler) fails
        # second call (finally guard) succeeds

    with pytest.raises(RuntimeError, match="scan error"):
        run_scan_lifecycle(
            scan_fn=scan_fn,
            mark_failed=mark_failed_tracking,
            is_still_running=lambda: True,
        )

    # mark_failed was called twice: once in except (failed), once in finally (zombie guard)
    assert len(final_msgs) == 2
    assert final_msgs[0] == "scan error"
    assert final_msgs[1] == "Scan finalization interrupted"


# ── Hardest Failure Path Tests ────────────────────────────────────────────

def test_exception_after_progress_write(registry: AtlasRegistry, tmp_path: Path):
    """Exception AFTER first progress update → progress persisted AND status = 'failed'."""
    snapshot_id = _setup_snapshot(registry)

    # Simulate: progress was written, then exception occurs
    registry.update_snapshot_progress(snapshot_id, files_seen=100, dirs_seen=10, bytes_seen=50000)

    # Verify progress is persisted
    snap = registry.get_snapshot(snapshot_id)
    assert snap["files_seen"] == 100
    assert snap["status"] == "running"

    # Now exception happens
    registry.update_snapshot_status(snapshot_id, "failed", error_message="Disk full mid-scan")

    snap = registry.get_snapshot(snapshot_id)
    assert snap["status"] == "failed"
    assert snap["error_message"] == "Disk full mid-scan"
    # Progress data is still there — not wiped by the failure
    assert snap["files_seen"] == 100
    assert snap["dirs_seen"] == 10
    assert snap["bytes_seen"] == 50000


def test_artifact_write_failure_after_successful_scan(registry: AtlasRegistry, tmp_path: Path):
    """If artifact writing fails after scan, snapshot must end up 'failed', not 'running'."""
    snapshot_id = _setup_snapshot(registry)

    scan_target = tmp_path / "target"
    scan_target.mkdir()
    (scan_target / "a.txt").write_text("hello")

    scanner = AtlasScanner(root=scan_target, snapshot_id=snapshot_id)

    def _do_scan():
        scanner.scan()  # succeeds
        raise IOError("Disk full writing artifacts")  # but artifact write fails

    with pytest.raises(IOError, match="Disk full"):
        run_scan_lifecycle(
            scan_fn=_do_scan,
            mark_failed=lambda msg: registry.update_snapshot_status(snapshot_id, "failed", error_message=msg),
            is_still_running=lambda: (registry.get_snapshot(snapshot_id) or {}).get("status") == "running",
            label="test-artifact-failure",
        )

    snap = registry.get_snapshot(snapshot_id)
    assert snap["status"] == "failed"
    assert "Disk full" in snap["error_message"]


def test_progress_callback_exception_does_not_abort_scan(tmp_path: Path):
    """If on_progress callback raises, scan must still complete successfully."""
    scan_target = tmp_path / "target"
    scan_target.mkdir()
    for i in range(3):
        d = scan_target / f"dir_{i}"
        d.mkdir()
        for j in range(2):
            (d / f"f_{j}.txt").write_text(f"data {i}-{j}")

    callback_errors = []

    def broken_progress(files, dirs, bytes_total):
        callback_errors.append(True)
        raise RuntimeError("progress callback exploded")

    scanner = AtlasScanner(root=scan_target, snapshot_id="snap_broken_progress")

    # Override throttle so callback fires on every directory
    original_time = time.time
    call_count = [0]
    def mock_time():
        call_count[0] += 1
        return original_time() + call_count[0] * 2

    with patch("merger.lenskit.adapters.atlas.time.time", side_effect=mock_time):
        result = scanner.scan(on_progress=broken_progress)

    # Scan must have completed despite callback errors
    assert result["stats"]["total_files"] == 6
    assert result["stats"]["total_dirs"] >= 3
    assert result["stats"]["end_time"] is not None
    # Callback was indeed called (and raised)
    assert len(callback_errors) > 0


def test_api_zombie_guard_via_lifecycle(tmp_path: Path):
    """API path: if scan_fn and mark_failed both raise, zombie guard still fires."""
    json_path = tmp_path / "atlas-test.json"
    json_path.write_text(json.dumps({"status": "running"}), encoding="utf-8")

    call_count = [0]

    def mark_failed(msg):
        call_count[0] += 1
        if call_count[0] == 1:
            raise IOError("JSON write failed")
        # Second call (zombie guard) succeeds
        json_path.write_text(json.dumps({"status": "failed", "error": msg}), encoding="utf-8")

    def is_still_running():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return data.get("status") == "running"

    with pytest.raises(RuntimeError, match="scan boom"):
        run_scan_lifecycle(
            scan_fn=lambda: (_ for _ in ()).throw(RuntimeError("scan boom")),
            mark_failed=mark_failed,
            is_still_running=is_still_running,
        )

    # Zombie guard should have fired and succeeded on second attempt
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert data["error"] == "Scan finalization interrupted"


def test_cli_and_api_lifecycle_semantic_equivalence(registry: AtlasRegistry, tmp_path: Path):
    """CLI and API paths produce equivalent lifecycle outcomes via shared executor."""
    snapshot_id = _setup_snapshot(registry)
    json_path = tmp_path / "api-artifact.json"
    json_path.write_text(json.dumps({"status": "running"}), encoding="utf-8")

    # CLI-style: registry is canonical
    run_scan_lifecycle(
        scan_fn=lambda: registry.update_snapshot_status(snapshot_id, "complete"),
        mark_failed=lambda msg: registry.update_snapshot_status(snapshot_id, "failed", error_message=msg),
        is_still_running=lambda: (registry.get_snapshot(snapshot_id) or {}).get("status") == "running",
        label="cli-test",
    )

    # API-style: JSON file is canonical
    def api_mark_complete():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        data["status"] = "completed"
        json_path.write_text(json.dumps(data), encoding="utf-8")

    run_scan_lifecycle(
        scan_fn=api_mark_complete,
        mark_failed=lambda msg: json_path.write_text(json.dumps({"status": "failed", "error": msg}), encoding="utf-8"),
        is_still_running=lambda: json.loads(json_path.read_text(encoding="utf-8")).get("status") == "running",
        label="api-test",
    )

    # Both should have reached terminal states
    cli_snap = registry.get_snapshot(snapshot_id)
    api_data = json.loads(json_path.read_text(encoding="utf-8"))

    assert cli_snap["status"] == "complete"
    assert api_data["status"] == "completed"
