import unittest
import tempfile
import shutil
import json
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from merger.lenskit.core.merge import write_reports_v2, ExtrasConfig, FileInfo, scan_repo

class TestPerRepoCohesion(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.hub = Path(self.test_dir) / "hub"
        self.hub.mkdir()

        # Setup repoA
        self.repoA = self.hub / "repoA"
        self.repoA.mkdir()
        (self.repoA / "fileA.txt").write_text("contentA", encoding="utf-8")

        # Setup repoB
        self.repoB = self.hub / "repoB"
        self.repoB.mkdir()
        (self.repoB / "fileB.txt").write_text("contentB", encoding="utf-8")

        self.merges_dir = Path(self.test_dir) / "merges"
        self.merges_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_per_repo_artifact_cohesion(self):
        # Scan repos to get file infos
        summaryA = scan_repo(self.repoA)
        summaryB = scan_repo(self.repoB)

        repo_summaries = [summaryA, summaryB]

        extras = ExtrasConfig(json_sidecar=True)

        # Run write_reports_v2 in per-repo mode
        write_reports_v2(
            merges_dir=self.merges_dir,
            hub=self.hub,
            repo_summaries=repo_summaries,
            detail="max",
            mode="pro-repo",
            max_bytes=1000,
            plan_only=False,
            output_mode="dual",
            extras=extras
        )

        # Identify generated sidecars
        json_files = list(self.merges_dir.glob("*.json"))
        # We expect 2 sidecars (one per repo).

        self.assertEqual(len(json_files), 2, "Should have 2 JSON sidecars")

        sidecarA = None
        sidecarB = None

        # Identify which is which
        for jf in json_files:
            data = json.loads(jf.read_text(encoding="utf-8"))
            repos = data["meta"]["source_repos"]
            if "repoA" in repos:
                sidecarA = data
            elif "repoB" in repos:
                sidecarB = data

        self.assertIsNotNone(sidecarA, "repoA sidecar not found")
        self.assertIsNotNone(sidecarB, "repoB sidecar not found")

        # Check Cohesion for repoA
        # Artifacts should only contain repoA stuff
        for md_part in sidecarA["artifacts"]["md_parts_basenames"]:
            self.assertIn("repoA", md_part)
            self.assertNotIn("repoB", md_part)

        chunk_idx_A = sidecarA["artifacts"]["chunk_index_basename"]
        self.assertIsNotNone(chunk_idx_A)
        self.assertIn("repoA", chunk_idx_A)
        self.assertNotIn("repoB", chunk_idx_A)

        # Check Cohesion for repoB
        # Artifacts should only contain repoB stuff
        # This checks for LEAKAGE. If repoB sidecar references repoA md parts, this fails.
        for md_part in sidecarB["artifacts"]["md_parts_basenames"]:
            self.assertIn("repoB", md_part)
            self.assertNotIn("repoA", md_part)

        chunk_idx_B = sidecarB["artifacts"]["chunk_index_basename"]
        self.assertIsNotNone(chunk_idx_B)
        self.assertIn("repoB", chunk_idx_B)
        self.assertNotIn("repoA", chunk_idx_B)

if __name__ == '__main__':
    unittest.main()
