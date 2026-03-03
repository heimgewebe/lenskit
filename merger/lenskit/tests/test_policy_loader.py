import json
from pathlib import Path
import pytest
from merger.lenskit.cli.policy_loader import load_and_validate_embedding_policy

def test_load_and_validate_embedding_policy_success(tmp_path):
    policy_path = tmp_path / "valid_policy.json"
    valid_policy = {
        "model_name": "test-model",
        "dimensions": 128,
        "provider": "local",
        "similarity_metric": "cosine"
    }
    policy_path.write_text(json.dumps(valid_policy), encoding="utf-8")

    loaded = load_and_validate_embedding_policy(policy_path)
    assert loaded["model_name"] == "test-model"
    assert loaded["dimensions"] == 128

def test_load_and_validate_embedding_policy_invalid_json(tmp_path, capsys):
    policy_path = tmp_path / "invalid_json.json"
    policy_path.write_text("{ broken json ", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        load_and_validate_embedding_policy(policy_path)

    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Error: Failed to parse embedding policy JSON" in captured.err

def test_load_and_validate_embedding_policy_invalid_schema(tmp_path, capsys):
    policy_path = tmp_path / "invalid_schema.json"
    invalid_policy = {
        "model_name": "test-model",
        "dimensions": -5,  # Invalid minimum
        "provider": "alien", # Invalid enum
        "similarity_metric": "cosine"
    }
    policy_path.write_text(json.dumps(invalid_policy), encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        load_and_validate_embedding_policy(policy_path)

    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Error: Embedding policy validation failed" in captured.err

def test_load_and_validate_embedding_policy_not_found(tmp_path, capsys):
    policy_path = tmp_path / "not_found.json"

    with pytest.raises(SystemExit) as exc:
        load_and_validate_embedding_policy(policy_path)

    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Error: Embedding policy file not found" in captured.err
