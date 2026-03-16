import pytest
from merger.lenskit.cli.main import main as lenskit_main
from merger.lenskit.cli.rlens import main as rlens_main

def test_lenskit_main_parses_atlas_analyze_duplicates(monkeypatch):
    """Verifies that `lenskit atlas analyze duplicates <id>` routes correctly."""
    called = False

    def mock_run_analyze(args):
        nonlocal called
        called = True
        assert args.atlas_cmd == "analyze"
        assert args.analyze_command == "duplicates"
        assert args.snapshot_id == "snap_test_123"
        return 0

    import merger.lenskit.cli.cmd_atlas
    monkeypatch.setattr(merger.lenskit.cli.cmd_atlas, "run_atlas_analyze", mock_run_analyze)

    exit_code = lenskit_main(["atlas", "analyze", "duplicates", "snap_test_123"])
    assert exit_code == 0
    assert called

def test_rlens_main_parses_atlas_analyze_duplicates(monkeypatch):
    """Verifies that `rlens atlas analyze duplicates <id>` routes correctly."""
    called = False

    def mock_run_analyze(args):
        nonlocal called
        called = True
        assert args.atlas_cmd == "analyze"
        assert args.analyze_command == "duplicates"
        assert args.snapshot_id == "snap_test_123"
        return 0

    import merger.lenskit.cli.cmd_atlas
    monkeypatch.setattr(merger.lenskit.cli.cmd_atlas, "run_atlas_analyze", mock_run_analyze)

    # rlens exit strategy uses sys.exit, so we need to catch it
    # We also need to patch sys.argv because rlens_main() takes no arguments
    import sys
    monkeypatch.setattr(sys, "argv", ["rlens", "atlas", "analyze", "duplicates", "snap_test_123"])

    with pytest.raises(SystemExit) as excinfo:
        rlens_main()

    assert excinfo.value.code == 0
    assert called
