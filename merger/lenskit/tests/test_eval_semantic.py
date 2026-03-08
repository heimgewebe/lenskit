import json
from pathlib import Path
import pytest

from merger.lenskit.cli import cmd_eval
from merger.lenskit.retrieval import eval_core
from merger.lenskit.retrieval import index_db

@pytest.fixture
def mini_index_for_eval(tmp_path):
    # Setup paths
    dump_path = tmp_path / "dump.json"
    chunk_path = tmp_path / "chunks.jsonl"
    db_path = tmp_path / "index.sqlite"

    # Write chunks covering typical targets
    chunk_data = [
        {"chunk_id": "c1", "repo_id": "r1", "path": "src/auth/login.py", "content": "def login(): pass", "start_line": 1, "end_line": 1, "layer": "core", "artifact_type": "code"},
        {"chunk_id": "c2", "repo_id": "r1", "path": "src/config/settings.py", "content": "SECRET_KEY = 'xyz'", "start_line": 1, "end_line": 1, "layer": "core", "artifact_type": "code"},
        {"chunk_id": "c3", "repo_id": "r1", "path": "tests/test_main.py", "content": "def test_main(): pass", "start_line": 1, "end_line": 1, "layer": "test", "artifact_type": "code"},
    ]
    with chunk_path.open("w", encoding="utf-8") as f:
        for c in chunk_data:
            f.write(json.dumps(c) + "\n")

    dump_path.write_text(json.dumps({"dummy": "data"}), encoding="utf-8")
    index_db.build_index(dump_path, chunk_path, db_path)
    return db_path

def test_eval_semantic_delta(mini_index_for_eval, tmp_path, capsys, monkeypatch):
    # We will write a deterministic mock for _get_semantic_model similar to test_retrieval_query.py

    # Create queries.md
    queries_md = tmp_path / "eval_queries.md"
    queries_md.write_text("""
1. **"login"**
   *Category:* feature
   *Expected:* `login.py`

2. **"test_main"**
   *Category:* test
   *Expected:* `test_main.py`
""", encoding="utf-8")

    # Create policy
    policy_json = tmp_path / "policy.json"
    policy_json.write_text(json.dumps({
        "provider": "local",
        "similarity_metric": "cosine",
        "model_name": "mock-model",
        "dimensions": 384,
        "fallback_behavior": "ignore"
    }), encoding="utf-8")

    class MockSemanticModel:
        def encode(self, texts):
            # If input is string, make it list-like for uniform processing
            is_single = isinstance(texts, str)
            if is_single: texts = [texts]

            embeddings = []
            for t in texts:
                t = t.lower()
                # Determine mock vectors based on content to force order
                if "test_main" in t:
                    embeddings.append([1.0, 0.0])
                elif "print" in t:
                    embeddings.append([0.0, 1.0])
                elif "def" == t:
                    embeddings.append([1.0, 0.0])
                else:
                    embeddings.append([0.5, 0.5])

            if is_single:
                import numpy as np
                return np.array(embeddings[0])
            import numpy as np
            return np.array(embeddings)

    def mock_get_semantic_model(name):
        return MockSemanticModel()

    monkeypatch.setattr("merger.lenskit.retrieval.query_core._get_semantic_model", mock_get_semantic_model)

    # Mock args
    class Args:
        index = str(mini_index_for_eval)
        queries = str(queries_md)
        k = 5
        emit = "json"
        stale_policy = "ignore"
        embedding_policy = str(policy_json)
        graph_index = None
        graph_weights = None

    # Run Eval
    ret_code = cmd_eval.run_eval(Args())
    assert ret_code == 0

    # Capture JSON output
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert "metrics" in output
    metrics = output["metrics"]

    # General output structure assertions
    assert "baseline_MRR" in metrics
    assert "semantic_MRR" in metrics
    assert "delta_mrr" in metrics
    assert "delta_recall" in metrics
    assert "baseline_recall@5" in metrics
    assert "semantic_recall@5" in metrics

    # Semantic delta logic assertions
    assert metrics["baseline_hits"] >= 0
    assert metrics["semantic_hits"] >= 0
    assert metrics["delta_mrr"] > -2.0 # Check existence and typability

    # In details, verify it emits both baseline and semantic keys
    details = output["details"]
    assert len(details) == 2
    for d in details:
        assert "baseline" in d
        assert "semantic" in d
        assert "delta_rr" in d

        assert "rr" in d["baseline"]
        assert "rr" in d["semantic"]
