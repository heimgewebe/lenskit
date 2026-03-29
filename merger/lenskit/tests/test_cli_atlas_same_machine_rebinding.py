import subprocess
import os
import sys
from pathlib import Path

def test_cli_rejects_same_machine_rebinding(tmp_path, monkeypatch):
    """
    Tests that the CLI handles a same-machine root rebinding attempt cleanly,
    returning exit code 1 and printing an error to stderr (not a raw traceback).
    """
    repo_root = Path(__file__).resolve().parent.parent.parent.parent

    # Create two different target directories
    dir1 = tmp_path / "target1"
    dir1.mkdir()
    dir2 = tmp_path / "target2"
    dir2.mkdir()

    # Move CLI into the temporary workspace so the registry is created there
    monkeypatch.chdir(tmp_path)

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{repo_root}{os.pathsep}{existing_pythonpath}"
    env["ATLAS_MACHINE_ID"] = "test-machine"

    # 1. First scan to register the root
    cmd1 = [
        sys.executable,
        "-m", "merger.lenskit.cli.main",
        "atlas", "scan",
        str(dir1),
        "--root-id", "my_shared_root"
    ]
    res1 = subprocess.run(cmd1, capture_output=True, text=True, env=env)
    assert res1.returncode == 0

    # 2. Second scan attempting to bind the same root_id to a different path
    cmd2 = [
        sys.executable,
        "-m", "merger.lenskit.cli.main",
        "atlas", "scan",
        str(dir2),
        "--root-id", "my_shared_root"
    ]
    res2 = subprocess.run(cmd2, capture_output=True, text=True, env=env)

    # It must fail cleanly
    assert res2.returncode == 1
    # Check that the stderr contains the expected error message and no raw traceback
    assert "Error during root registration:" in res2.stderr
    assert "Cannot silently rebind" in res2.stderr
    assert "Traceback" not in res2.stderr
