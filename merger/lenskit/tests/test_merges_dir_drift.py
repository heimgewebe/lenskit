import pytest
from unittest.mock import MagicMock, patch
from merger.lenskit.service.runner import JobRunner
from merger.lenskit.service.jobstore import JobStore
from merger.lenskit.service.models import JobRequest, Job, Artifact
from merger.lenskit.service.app import download_artifact
from merger.lenskit.adapters import security
from merger.lenskit.adapters.security import SecurityConfig
from pathlib import Path
import tempfile

@pytest.fixture
def temp_hub():
    with tempfile.TemporaryDirectory() as tmp:
        hub = Path(tmp).resolve()
        (hub / "repoA").mkdir()
        (hub / "repoA" / "README.md").write_text("content")

        # Use a fresh SecurityConfig for this test, replacing the global singleton
        new_config = SecurityConfig()
        new_config.add_allowlist_root(hub)

        with patch.object(security, "_security_config", new_config):
            yield hub

def test_runner_resolves_and_creates_relative_merges_dir(temp_hub):
    """
    Integration test: Runner should resolve relative merges_dir against HUB,
    create the directory, and persist absolute path in Artifact.
    """
    # 1. Setup Real JobStore
    store = JobStore(temp_hub)
    runner = JobRunner(store)

    # 2. Setup Job with relative merges_dir
    rel_path = "output/merges"
    req = JobRequest(
        hub=str(temp_hub),
        repos=["repoA"],
        merges_dir=rel_path
    )
    job = Job.create(req)
    job.hub_resolved = str(temp_hub)
    store.add_job(job)

    # 3. Run Job (Synchronously via private method)
    # We mock write_reports_v2 to return a dummy artifact object but let directory creation happen
    # scan_repo can also be mocked to avoid dependency on actual repo content logic if desired,
    # but since we created a dummy repo, it might run fine. Let's mock scan_repo for speed/isolation.
    with patch("merger.lenskit.service.runner.write_reports_v2") as mock_write, \
         patch("merger.lenskit.service.runner.scan_repo") as mock_scan:

        mock_artifacts = MagicMock()
        mock_artifacts.get_all_paths.return_value = [Path("dummy.md")]
        mock_artifacts.index_json = None
        mock_artifacts.canonical_md = None
        mock_artifacts.md_parts = []
        mock_artifacts.chunk_index = None
        mock_artifacts.dump_index = None
        mock_artifacts.sqlite_index = None
        mock_artifacts.retrieval_eval = None
        mock_artifacts.derived_manifest = None
        mock_artifacts.bundle_manifest = None
        mock_write.return_value = mock_artifacts

        mock_scan.return_value = {} # Dummy summary

        runner._run_job(job.id)

    # 4. Verification

    # A. Check Directory Exists at Absolute Path
    expected_abs_path = (temp_hub / rel_path).resolve()
    assert expected_abs_path.exists(), f"Directory {expected_abs_path} was not created"
    assert expected_abs_path.is_dir()

    # B. Check Job Status
    updated_job = store.get_job(job.id)
    assert updated_job.status == "succeeded", f"Job failed with error: {updated_job.error}"

    # C. Check Artifact Persistence
    assert len(updated_job.artifact_ids) == 1
    art = store.get_artifact(updated_job.artifact_ids[0])
    assert art is not None

    # D. Check Artifact.merges_dir is absolute and correct
    assert art.merges_dir == str(expected_abs_path)
    assert Path(art.merges_dir).is_absolute()

    # E. Check Artifact.params.merges_dir (Request object was updated in memory)
    # Note: JobStore saves the updated request object
    assert art.params.merges_dir == str(expected_abs_path)


def test_download_artifact_uses_persisted_merges_dir(temp_hub):
    """
    Test that download_artifact uses the persisted absolute merges_dir.
    """
    # Setup manual artifact
    abs_merges_dir = temp_hub / "custom_output"
    abs_merges_dir.mkdir()
    (abs_merges_dir / "test.md").write_text("secret content")

    store = JobStore(temp_hub)

    art = Artifact(
        id="art_dl_test",
        job_id="job_dl_test",
        hub=str(temp_hub),
        repos=["repoA"],
        created_at="2024-01-01",
        paths={"md": "test.md"},
        params=JobRequest(hub=str(temp_hub), repos=["repoA"]),
        merges_dir=str(abs_merges_dir) # Persisted absolute path
    )
    store.add_artifact(art)

    # Patch global state for app.py
    # We need to ensure get_security_config allows the path

    with patch("merger.lenskit.service.app.state") as mock_state, \
         patch("merger.lenskit.service.app.get_security_config") as mock_get_sec:

        mock_state.job_store = store

        # Mock security to be permissive (we are testing path logic here)
        mock_sec = MagicMock()
        mock_sec.validate_path.side_effect = lambda p: p
        mock_get_sec.return_value = mock_sec

        response = download_artifact("art_dl_test", "md")

        assert str(response.path) == str(abs_merges_dir / "test.md")


def test_download_artifact_resolves_legacy_relative_path(temp_hub):
    """
    Test backward compatibility: if merges_dir is missing in Artifact,
    it uses params.merges_dir and resolves it against Hub.
    """
    rel_path = "legacy_output"
    abs_merges_dir = temp_hub / rel_path
    abs_merges_dir.mkdir()
    (abs_merges_dir / "legacy.md").write_text("legacy content")

    store = JobStore(temp_hub)

    art = Artifact(
        id="art_legacy",
        job_id="job_legacy",
        hub=str(temp_hub),
        repos=["repoA"],
        created_at="2024-01-01",
        paths={"md": "legacy.md"},
        params=JobRequest(
            hub=str(temp_hub),
            repos=["repoA"],
            merges_dir=rel_path # Relative in params
        ),
        merges_dir=None # Simulate legacy artifact
    )
    store.add_artifact(art)

    with patch("merger.lenskit.service.app.state") as mock_state, \
         patch("merger.lenskit.service.app.get_security_config") as mock_get_sec:

        mock_state.job_store = store

        mock_sec = MagicMock()
        mock_sec.validate_path.side_effect = lambda p: p
        mock_get_sec.return_value = mock_sec

        response = download_artifact("art_legacy", "md")

        # It should have resolved rel_path against temp_hub
        expected_path = abs_merges_dir / "legacy.md"
        assert str(response.path) == str(expected_path)

def test_runner_blocks_path_traversal(temp_hub):
    """
    Test that relative paths trying to escape the Hub are blocked.
    """
    store = JobStore(temp_hub)
    runner = JobRunner(store)

    # Try to write outside temp_hub using traversal
    rel_path = "../escaped_dir"

    req = JobRequest(
        hub=str(temp_hub),
        repos=["repoA"],
        merges_dir=rel_path
    )
    job = Job.create(req)
    job.hub_resolved = str(temp_hub)
    store.add_job(job)

    with patch("merger.lenskit.service.runner.write_reports_v2"), \
         patch("merger.lenskit.service.runner.scan_repo") as mock_scan:

        mock_scan.return_value = {}

        runner._run_job(job.id)

    updated_job = store.get_job(job.id)
    assert updated_job.status == "failed"
    assert "SECURITY:" in updated_job.error

def test_download_artifact_resolves_drifted_persisted_relative_path(temp_hub):
    """
    Test Priority 1 defense-in-depth: if art.merges_dir is somehow relative
    (drifted persistence), it should be resolved against hub.
    """
    rel_path = "drifted_out"
    abs_merges_dir = temp_hub / rel_path
    abs_merges_dir.mkdir()
    (abs_merges_dir / "drift.md").write_text("content")

    store = JobStore(temp_hub)

    art = Artifact(
        id="art_drift",
        job_id="job_drift",
        hub=str(temp_hub),
        repos=["repoA"],
        created_at="2024-01-01",
        paths={"md": "drift.md"},
        params=JobRequest(hub=str(temp_hub), repos=["repoA"]),
        merges_dir=rel_path # Relative persisted path (simulating bad state)
    )
    store.add_artifact(art)

    with patch("merger.lenskit.service.app.state") as mock_state, \
         patch("merger.lenskit.service.app.get_security_config") as mock_get_sec:

        mock_state.job_store = store

        mock_sec = MagicMock()
        mock_sec.validate_path.side_effect = lambda p: p
        mock_get_sec.return_value = mock_sec

        response = download_artifact("art_drift", "md")

        expected_path = abs_merges_dir / "drift.md"
        assert str(response.path) == str(expected_path)

def test_download_artifact_uses_default_merges_dir(temp_hub):
    """
    Test Priority 3: No merges_dir in artifact or params -> use default.
    """
    # Need to import MERGES_DIR_NAME.
    # It is usually 'merges' but better to import if possible,
    # or hardcode if test needs to be standalone.
    # merger.lenskit.core.merge import MERGES_DIR_NAME might fail if dependencies missing?
    # We already imported app, models etc. so core should be available.
    try:
        from merger.lenskit.core.merge import MERGES_DIR_NAME
    except ImportError:
        MERGES_DIR_NAME = "merges"

    default_dir = temp_hub / MERGES_DIR_NAME
    default_dir.mkdir(exist_ok=True)
    (default_dir / "default.md").write_text("content")

    store = JobStore(temp_hub)

    art = Artifact(
        id="art_default",
        job_id="job_default",
        hub=str(temp_hub),
        repos=["repoA"],
        created_at="2024-01-01",
        paths={"md": "default.md"},
        params=JobRequest(hub=str(temp_hub), repos=["repoA"]),
        merges_dir=None
    )
    store.add_artifact(art)

    with patch("merger.lenskit.service.app.state") as mock_state, \
         patch("merger.lenskit.service.app.get_security_config") as mock_get_sec:

        mock_state.job_store = store

        mock_sec = MagicMock()
        mock_sec.validate_path.side_effect = lambda p: p
        mock_get_sec.return_value = mock_sec

        response = download_artifact("art_default", "md")

        expected_path = default_dir / "default.md"
        assert str(response.path) == str(expected_path)

def test_runner_logs_output_paths(temp_hub):
    """
    Test that the runner logs the generated file paths (at least the first 10).
    """
    store = JobStore(temp_hub)
    runner = JobRunner(store)

    req = JobRequest(hub=str(temp_hub), repos=["repoA"])
    job = Job.create(req)
    job.hub_resolved = str(temp_hub)
    store.add_job(job)

    # Mock dependencies
    with patch("merger.lenskit.service.runner.scan_repo") as mock_scan, \
         patch("merger.lenskit.service.runner.write_reports_v2") as mock_write, \
         patch("merger.lenskit.service.runner.validate_source_dir"):

        mock_scan.return_value = {}

        # Setup mock artifacts with some paths
        mock_artifacts = MagicMock()
        mock_artifacts.index_json = None
        mock_artifacts.canonical_md = None
        mock_artifacts.md_parts = []
        mock_artifacts.other = []
        mock_artifacts.chunk_index = None
        mock_artifacts.dump_index = None
        mock_artifacts.sqlite_index = None
        mock_artifacts.retrieval_eval = None
        mock_artifacts.derived_manifest = None
        mock_artifacts.bundle_manifest = None

        # Create dummy paths (more than 10 to test truncation)
        # Use temp_hub to be semantically consistent, though specific path doesn't matter for this test
        paths = [temp_hub / f"output_{i}.md" for i in range(15)]
        mock_artifacts.get_all_paths.return_value = paths

        mock_write.return_value = mock_artifacts

        runner._run_job(job.id)

    # Verify logs
    logs = store.read_log_lines(job.id)

    # We expect a log message containing the paths
    # The current implementation limits to 10.
    # "Generated 15 files: ['.../output_0.md', ...]"

    found_msg = False
    for line in logs:
        # Match the log line for generated files
        if "Generated 15 files:" in line:
            found_msg = True
            # Check for first few paths using dynamic string representation
            assert str(paths[0]) in line
            assert str(paths[9]) in line
            # Check that 11th path is NOT in line (truncation)
            assert str(paths[10]) not in line
            # Check for "more" count
            assert "(+5 more)" in line
            break

    assert found_msg, f"Log message about generated files not found. Logs: {logs}"
