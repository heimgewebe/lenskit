
import pytest
import shutil
import tempfile
from pathlib import Path

# Setup context for testing the service app
@pytest.fixture
def service_client():
    # Attempt import inside fixture to handle missing dependencies gracefully
    # or let it fail if environment is expected to have it.
    try:
        from fastapi.testclient import TestClient
        # Canonical imports only - strict environment check
        from merger.lenskit.service.app import app, init_service, state
    except ImportError as e:
        pytest.skip(f"Service dependencies missing: {e}")

    # Setup
    temp_dir = tempfile.mkdtemp()
    hub_path = Path(temp_dir) / "hub"
    hub_path.mkdir()
    merges_dir = hub_path / "merges"
    merges_dir.mkdir()

    # Create a dummy repo for scanning
    (hub_path / "repo-test").mkdir()
    (hub_path / "repo-test" / "README.md").write_text("Test Content")

    token = "test-token-123"

    # Ensure FS token secret is available for tests
    import os
    os.environ["RLENS_TOKEN"] = token

    # Initialize service with explicit token and merges_dir
    init_service(hub_path, token=token, merges_dir=merges_dir)

    client = TestClient(app)
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Expose useful objects
    class Context:
        def __init__(self):
            self.client = client
            self.headers = auth_headers
            self.store = state.job_store
            self.hub_path = hub_path
            self.merges_dir = merges_dir
            self.runner = state.runner

    ctx = Context()

    yield ctx

    # Teardown
    shutil.rmtree(temp_dir, ignore_errors=True)
