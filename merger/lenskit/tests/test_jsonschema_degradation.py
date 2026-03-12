import sys
import os
import subprocess
from pathlib import Path

# This file aims to test the degradation of modules when jsonschema is not available.
# We run these tests in a separate subprocess to avoid polluting the global sys.modules
# state and pytest's cache.

def get_repo_root() -> Path:
    # merger/lenskit/tests/test_jsonschema_degradation.py -> parents[3] is the repo root
    return Path(__file__).resolve().parents[3]

def get_test_env() -> dict:
    env = os.environ.copy()
    repo_root = str(get_repo_root())
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{repo_root}{os.pathsep}{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = repo_root
    return env

def test_modules_import_without_jsonschema():
    """
    Ensure that importing the modules doesn't fail with a ModuleNotFoundError
    when jsonschema is completely unavailable.
    """
    code = """
import sys
sys.modules['jsonschema'] = None

import merger.lenskit.core.range_resolver as rr
import merger.lenskit.architecture.graph_index as gi
import merger.lenskit.cli.policy_loader as pl

assert getattr(rr, "jsonschema", None) is None
assert getattr(gi, "jsonschema", None) is None
assert getattr(pl, "jsonschema", None) is None
print("Success")
"""
    repo_root = get_repo_root()
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=get_test_env(), cwd=repo_root)
    assert result.returncode == 0
    assert "Success" in result.stdout


def test_range_resolver_degradation(tmp_path):
    manifest_path = tmp_path / "bundle.manifest.json"
    manifest_path.write_text('{"kind": "repolens.bundle.manifest"}', encoding="utf-8")

    code = f"""
import sys
sys.modules['jsonschema'] = None
import merger.lenskit.core.range_resolver as rr
from pathlib import Path

try:
    rr.resolve_range_ref(Path("{manifest_path}"), {{}})
    sys.exit(1)
except RuntimeError as e:
    if "Schema validation requested but jsonschema is unavailable" in str(e):
        print("Success")
    else:
        print(f"Wrong error: {{e}}")
        sys.exit(1)
"""
    repo_root = get_repo_root()
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=get_test_env(), cwd=repo_root)
    assert result.returncode == 0
    assert "Success" in result.stdout

def test_policy_loader_degradation(tmp_path):
    policy_path = tmp_path / "policy.json"
    policy_path.write_text('{"model_name": "test-model"}', encoding="utf-8")

    code = f"""
import sys
sys.modules['jsonschema'] = None
import merger.lenskit.cli.policy_loader as pl
from pathlib import Path

try:
    pl.load_and_validate_embedding_policy(Path("{policy_path}"))
    sys.exit(1)
except pl.EmbeddingPolicyError as e:
    if "Schema validation requested but jsonschema is unavailable" in str(e):
        print("Success")
    else:
        print(f"Wrong error: {{e}}")
        sys.exit(1)
"""
    repo_root = get_repo_root()
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=get_test_env(), cwd=repo_root)
    assert result.returncode == 0
    assert "Success" in result.stdout


def test_graph_index_degradation(tmp_path):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text('{"distances": {}}', encoding="utf-8")

    code = f"""
import sys
sys.modules['jsonschema'] = None
import merger.lenskit.architecture.graph_index as gi
from pathlib import Path

import logging
logging.basicConfig(level=logging.WARNING)

result = gi.load_graph_index(Path("{graph_path}"))
if result["status"] == "ok" and "graph" in result:
    print("Success")
else:
    sys.exit(1)
"""
    repo_root = get_repo_root()
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=get_test_env(), cwd=repo_root)
    assert result.returncode == 0
    assert "Success" in result.stdout
    assert "Schema validation skipped" in result.stderr
