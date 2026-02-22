import os
import sys
from unittest.mock import MagicMock
import unittest
from pathlib import Path

# Mock dependencies that might be missing in the environment
mock_fastapi = MagicMock()
sys.modules["fastapi"] = mock_fastapi
sys.modules["fastapi.staticfiles"] = MagicMock()
sys.modules["fastapi.responses"] = MagicMock()
sys.modules["fastapi.middleware.cors"] = MagicMock()
sys.modules["starlette.concurrency"] = MagicMock()
sys.modules["pydantic"] = MagicMock()

# Create a mock for models to avoid pydantic issues
models_mock = MagicMock()
class Dummy:
    pass
models_mock.JobRequest = Dummy
models_mock.Job = Dummy
models_mock.Artifact = Dummy
models_mock.AtlasRequest = Dummy
models_mock.AtlasArtifact = Dummy
models_mock.AtlasEffective = Dummy
models_mock.PrescanRequest = Dummy
models_mock.PrescanResponse = Dummy
models_mock.FSRoot = Dummy
models_mock.FSRootsResponse = Dummy
models_mock.calculate_job_hash = lambda *args, **kwargs: "hash"

# Set up mock modules for all relative imports in app.py
sys.modules["merger.lenskit.service.models"] = models_mock
sys.modules["merger.lenskit.service.jobstore"] = MagicMock()
sys.modules["merger.lenskit.service.runner"] = MagicMock()
sys.modules["merger.lenskit.service.logging_provider"] = MagicMock()
sys.modules["merger.lenskit.service.auth"] = MagicMock()
sys.modules["merger.lenskit.adapters.security"] = MagicMock()
sys.modules["merger.lenskit.adapters.filesystem"] = MagicMock()
sys.modules["merger.lenskit.adapters.atlas"] = MagicMock()
sys.modules["merger.lenskit.adapters.metarepo"] = MagicMock()
sys.modules["merger.lenskit.adapters.sources"] = MagicMock()
sys.modules["merger.lenskit.adapters.diagnostics"] = MagicMock()
sys.modules["merger.lenskit.core.merge"] = MagicMock()

# Add repo root to sys.path
sys.path.insert(0, os.getcwd())

class TestSecurityFix(unittest.TestCase):
    def test_init_service_does_not_allow_root_fs(self):
        try:
            from merger.lenskit.service.app import init_service
            from merger.lenskit.adapters.security import get_security_config
        except ImportError:
            self.skipTest("Could not import init_service due to missing dependencies")

        # Set the environment variable that PREVIOUSLY enabled the vulnerability
        os.environ["RLENS_ALLOW_FS_ROOT"] = "1"

        hub = Path("/tmp/hub").resolve()
        if not hub.exists():
            hub.mkdir(parents=True, exist_ok=True)

        sec = get_security_config()
        # Mock add_allowlist_root to track calls
        sec.add_allowlist_root = MagicMock()

        # Initialize service
        init_service(hub, token="test-token")

        # Verify Path("/") was NEVER called on add_allowlist_root
        for call in sec.add_allowlist_root.call_args_list:
            args, _ = call
            self.assertNotEqual(args[0], Path("/"))
            self.assertNotEqual(str(args[0]), "/")

    def test_file_content_no_longer_contains_vulnerability(self):
        # Direct check of the source code to ensure the dangerous lines are gone
        app_path = Path("merger/lenskit/service/app.py")
        content = app_path.read_text()
        self.assertNotIn("RLENS_ALLOW_FS_ROOT", content)
        self.assertNotIn('sec.add_allowlist_root(Path("/"))', content)
        self.assertNotIn('FS_ROOT = Path("/").resolve()', content)

if __name__ == "__main__":
    unittest.main()
