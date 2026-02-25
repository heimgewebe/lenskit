import tempfile
from pathlib import Path
import sys

# Ensure we can import from the repo root
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from merger.lenskit.core.merge import write_reports_v2, scan_repo, ExtrasConfig
from merger.lenskit.core import merge as merge_module


def test_redaction_pipeline_applies_to_generated_markdown(monkeypatch):
    """
    Integration test:
    Ensures write_reports_v2(..., redact_secrets=True)
    applies redaction before Markdown emission.

    No secret-like values are written to disk.
    """

    # Construct secret dynamically to avoid scanner triggers
    dummy_secret = "DUMMY_" + "SECRET_VALUE_FOR_TESTING_PURPOSES"
    key_name = "api" + "_key"
    injected_content = f'{key_name} = "{dummy_secret}"\n'

    call_count = {"n": 0}

    # Patch read_smart_content to return injected secret content
    # The signature in merge.py is:
    # def read_smart_content(fi: FileInfo, max_bytes: int, encoding="utf-8") -> Tuple[str, bool, str]:
    def fake_read_smart_content(fi, max_file_bytes, encoding="utf-8"):
        call_count["n"] += 1
        return injected_content, False, None

    monkeypatch.setattr(merge_module, "read_smart_content", fake_read_smart_content)

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        hub = tmp_dir / "hub"
        hub.mkdir()

        repo_root = hub / "repo"
        repo_root.mkdir()

        # Create harmless file (content irrelevant due to patch)
        # We need a file that is considered "text" and "included"
        (repo_root / "config.py").write_text("placeholder\n", encoding="utf-8")

        # scan_repo to get the summary
        summary = scan_repo(repo_root, calculate_md5=True)

        # Ensure we have at least one file
        assert len(summary['files']) > 0

        merges_dir = tmp_dir / "merges"
        merges_dir.mkdir()

        extras = ExtrasConfig(json_sidecar=False)

        # Run write_reports_v2 with redact_secrets=True
        artifacts = write_reports_v2(
            merges_dir=merges_dir,
            hub=hub,
            repo_summaries=[summary],
            detail="max",
            mode="gesamt",
            max_bytes=0,
            plan_only=False,
            code_only=False,
            split_size=0,
            debug=False,
            extras=extras,
            output_mode="archive",
            redact_secrets=True
        )

        # Ensure our hook was actually called
        assert call_count["n"] > 0, "Mocked read_smart_content was never called!"

        # Verify the output
        md_path = artifacts.canonical_md
        assert md_path is not None
        md_content = md_path.read_text(encoding="utf-8")

        # Assertions
        # 1. Secret should NOT be present
        assert dummy_secret not in md_content, "Secret leaked into output!"

        # 2. Redaction marker should be present
        assert "[REDACTED]" in md_content, "Redaction marker missing!"

        # 3. Context (key name) should be present
        assert key_name in md_content, "Key name missing from output!"
