import json
import pytest

from merger.lenskit.cli.main import main


@pytest.fixture
def ac_pr_review(tmp_path):
    p = tmp_path / "answer-compliance.json"
    p.write_text(json.dumps({
        "kind": "lenskit.answer_compliance",
        "version": "1.0",
        "task_profile": "pr_review",
        "declared_artifacts": [
            "agent_reading_pack",
            "canonical_md",
            "citation_map_jsonl",
            "post_emit_health"
        ],
        "declared_citations": [],
        "declared_ranges": [],
        "unread_required_artifacts": [],
        "unread_recommended_artifacts": [],
        "epistemic_gaps": [],
        "does_not_establish": [
            "actual_reading_proven",
            "answer_correct",
            "repo_understood",
            "all_relevant_context_used",
            "claims_true",
            "test_sufficiency",
            "regression_absence",
            "runtime_behavior",
            "forensic_ready"
        ]
    }), encoding="utf-8")
    return p


def test_cli_required_stdout(capsys):
    rc = main([
        "agent-consumption", "required",
        "--task-profile", "basic_repo_question",
        "--available-roles", "agent_reading_pack,canonical_md,citation_map_jsonl"
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["task_profile"] == "basic_repo_question"
    assert out["status"] in ("pass", "warn")


def test_cli_required_out_file(tmp_path, capsys):
    out_file = tmp_path / "out.json"
    rc = main([
        "agent-consumption", "required",
        "--task-profile", "basic_repo_question",
        "--available-roles", "agent_reading_pack,canonical_md,citation_map_jsonl",
        "--out", str(out_file)
    ])
    assert rc == 0
    assert out_file.exists()
    out = json.loads(out_file.read_text(encoding="utf-8"))
    assert out["task_profile"] == "basic_repo_question"
    assert out["status"] in ("pass", "warn")
    assert capsys.readouterr().out == ""


def test_cli_required_missing_required(capsys):
    rc = main([
        "agent-consumption", "required",
        "--task-profile", "pr_review",
        "--available-roles", "agent_reading_pack"
    ])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "fail"
    assert len(out["missing_required"]) > 0


def test_cli_required_unknown_profile(capsys):
    rc = main([
        "agent-consumption", "required",
        "--task-profile", "unknown_profile"
    ])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "not_applicable"


def test_cli_validate_trace_pass(tmp_path, capsys, ac_pr_review):
    rr_file = tmp_path / "rr.json"
    main([
        "agent-consumption", "required",
        "--task-profile", "pr_review",
        "--available-roles", "agent_reading_pack,canonical_md,citation_map_jsonl,post_emit_health,bundle_surface_validation,claim_evidence_map_json",
        "--out", str(rr_file)
    ])
    
    rc = main([
        "agent-consumption", "validate-trace",
        "--required-reading", str(rr_file),
        "--answer-compliance", str(ac_pr_review),
        "--available-roles", "agent_reading_pack,canonical_md,citation_map_jsonl,post_emit_health"
    ])
    out = json.loads(capsys.readouterr().out)
    assert out["status"] in ("pass", "warn")
    assert rc == 0


def test_cli_validate_trace_warn(tmp_path, capsys):
    rr_file = tmp_path / "rr.json"
    rr_file.write_text(json.dumps({
        "task_profile": "pr_review",
        "required": ["canonical_md"],
        "recommended": ["citation_map_jsonl"],
        "status": "warn"
    }))
    ac_file = tmp_path / "ac.json"
    ac_file.write_text(json.dumps({
        "task_profile": "pr_review",
        "declared_artifacts": ["canonical_md"],
        "does_not_establish": [
            "actual_reading_proven",
            "answer_correct",
            "repo_understood",
            "all_relevant_context_used",
            "claims_true",
            "test_sufficiency",
            "regression_absence",
            "runtime_behavior",
            "forensic_ready"
        ]
    }))
    rc = main([
        "agent-consumption", "validate-trace",
        "--required-reading", str(rr_file),
        "--answer-compliance", str(ac_file)
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "warn"


def test_cli_validate_trace_warn_strict(tmp_path, capsys):
    rr_file = tmp_path / "rr.json"
    rr_file.write_text(json.dumps({
        "task_profile": "pr_review",
        "required": ["canonical_md"],
        "recommended": ["citation_map_jsonl"],
        "status": "warn"
    }))
    ac_file = tmp_path / "ac.json"
    ac_file.write_text(json.dumps({
        "task_profile": "pr_review",
        "declared_artifacts": ["canonical_md"],
        "does_not_establish": [
            "actual_reading_proven",
            "answer_correct",
            "repo_understood",
            "all_relevant_context_used",
            "claims_true",
            "test_sufficiency",
            "regression_absence",
            "runtime_behavior",
            "forensic_ready"
        ]
    }))
    rc = main([
        "agent-consumption", "validate-trace",
        "--required-reading", str(rr_file),
        "--answer-compliance", str(ac_file),
        "--strict"
    ])
    assert rc == 1


def test_cli_validate_trace_fail(tmp_path, capsys):
    rr_file = tmp_path / "rr.json"
    rr_file.write_text(json.dumps({
        "task_profile": "pr_review",
        "required": ["canonical_md"],
        "status": "fail"
    }))
    ac_file = tmp_path / "ac.json"
    ac_file.write_text(json.dumps({
        "task_profile": "pr_review",
        "declared_artifacts": [], 
        "does_not_establish": [
            "actual_reading_proven",
            "answer_correct",
            "repo_understood",
            "all_relevant_context_used",
            "claims_true",
            "test_sufficiency",
            "regression_absence",
            "runtime_behavior",
            "forensic_ready"
        ]
    }))
    rc = main([
        "agent-consumption", "validate-trace",
        "--required-reading", str(rr_file),
        "--answer-compliance", str(ac_file)
    ])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "fail"


def test_cli_validate_trace_out_file(tmp_path, capsys):
    rr_file = tmp_path / "rr.json"
    rr_file.write_text(json.dumps({
        "task_profile": "pr_review",
        "required": ["canonical_md"],
        "status": "pass"
    }))
    ac_file = tmp_path / "ac.json"
    ac_file.write_text(json.dumps({
        "task_profile": "pr_review",
        "declared_artifacts": ["canonical_md"],
        "does_not_establish": [
            "actual_reading_proven",
            "answer_correct",
            "repo_understood",
            "all_relevant_context_used",
            "claims_true",
            "test_sufficiency",
            "regression_absence",
            "runtime_behavior",
            "forensic_ready"
        ]
    }))
    out_file = tmp_path / "trace.json"
    rc = main([
        "agent-consumption", "validate-trace",
        "--required-reading", str(rr_file),
        "--answer-compliance", str(ac_file),
        "--out", str(out_file)
    ])
    assert rc == 0
    assert out_file.exists()
    out = json.loads(out_file.read_text(encoding="utf-8"))
    assert out["status"] == "pass"
    assert capsys.readouterr().out == ""


def test_cli_missing_input_path(capsys):
    with pytest.raises(SystemExit) as exc:
        main([
            "agent-consumption", "validate-trace",
            "--required-reading", "does_not_exist.json",
            "--answer-compliance", "does_not_exist2.json"
        ])
    assert exc.value.code == 2
    assert "Could not read" in capsys.readouterr().err


def test_cli_invalid_json(tmp_path, capsys):
    rr_file = tmp_path / "rr.json"
    rr_file.write_text("{invalid")
    ac_file = tmp_path / "ac.json"
    ac_file.write_text("{}")
    
    with pytest.raises(SystemExit) as exc:
        main([
            "agent-consumption", "validate-trace",
            "--required-reading", str(rr_file),
            "--answer-compliance", str(ac_file)
        ])
    assert exc.value.code == 2
    assert "Invalid JSON" in capsys.readouterr().err


def test_cli_roles_file_list(tmp_path, capsys):
    roles_file = tmp_path / "roles.json"
    roles_file.write_text('["role1", "role2"]')
    rc = main([
        "agent-consumption", "required",
        "--task-profile", "unknown",
        "--available-roles-file", str(roles_file)
    ])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert set(out["available_required"]) == set()


def test_cli_roles_file_object(tmp_path, capsys):
    roles_file = tmp_path / "roles.json"
    roles_file.write_text('{"available_roles": ["role3", "role4"]}')
    rc = main([
        "agent-consumption", "required",
        "--task-profile", "unknown",
        "--available-roles-file", str(roles_file)
    ])
    assert rc == 1


def test_cli_roles_union(tmp_path, capsys):
    roles_file = tmp_path / "roles.json"
    roles_file.write_text('["role1"]')
    rc = main([
        "agent-consumption", "required",
        "--task-profile", "basic_repo_question",
        "--available-roles", "canonical_md",
        "--available-roles-file", str(roles_file)
    ])
    assert rc in (0, 1)
