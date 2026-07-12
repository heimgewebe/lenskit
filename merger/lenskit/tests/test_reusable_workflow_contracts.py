from pathlib import Path

from scripts.ci.check_reusable_workflow_contracts import scan


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_repository_reusable_workflow_callers_match_contracts() -> None:
    assert scan(_repo_root()) == []


def test_contract_rejects_lower_permission_and_secret_fanout(tmp_path: Path) -> None:
    contract_source = _repo_root() / ".github/reusable-workflow-contracts.json"
    contract_target = tmp_path / ".github/reusable-workflow-contracts.json"
    contract_target.parent.mkdir(parents=True)
    contract_target.write_bytes(contract_source.read_bytes())
    caller = tmp_path / ".github/workflows/pr-heimgewebe-commands.yml"
    caller.parent.mkdir(parents=True)
    caller.write_text(
        """\npermissions:\n  contents: read\njobs:\n  dispatch:\n    if: github.event.issue.pull_request != null\n    uses: heimgewebe/metarepo/.github/workflows/heimgewebe-command-dispatch.yml@10daa1c84469dce76e93cdc24c47c1dfc5e156d6\n    secrets:\n      inherit: true\n""",
        encoding="utf-8",
    )
    wgx_source = _repo_root() / ".github/workflows/wgx-guard.yml"
    wgx_target = tmp_path / ".github/workflows/wgx-guard.yml"
    wgx_target.write_bytes(wgx_source.read_bytes())
    codes = {finding.code for finding in scan(tmp_path)}
    assert codes == {
        "insufficient_caller_permission",
        "caller_secret_contract_mismatch",
        "missing_caller_condition",
    }


def test_contract_rejects_stale_wgx_guard_pin(tmp_path: Path) -> None:
    contract_source = _repo_root() / ".github/reusable-workflow-contracts.json"
    contract_target = tmp_path / ".github/reusable-workflow-contracts.json"
    contract_target.parent.mkdir(parents=True)
    contract_target.write_bytes(contract_source.read_bytes())

    command_caller_source = _repo_root() / ".github/workflows/pr-heimgewebe-commands.yml"
    command_caller_target = tmp_path / ".github/workflows/pr-heimgewebe-commands.yml"
    command_caller_target.parent.mkdir(parents=True, exist_ok=True)
    command_caller_target.write_bytes(command_caller_source.read_bytes())

    wgx_caller = tmp_path / ".github/workflows/wgx-guard.yml"
    wgx_caller.write_text(
        """\npermissions:\n  contents: read\njobs:\n  guard:\n    uses: heimgewebe/wgx/.github/workflows/wgx-guard.yml@44069602da536e781675a788e8d9d4c45c7c1f75\n""",
        encoding="utf-8",
    )

    findings = scan(tmp_path)
    assert [(finding.caller_path, finding.code) for finding in findings] == [
        (".github/workflows/wgx-guard.yml", "reusable_workflow_pin_mismatch")
    ]


def test_contract_reports_missing_caller_file(tmp_path: Path) -> None:
    contract_source = _repo_root() / ".github/reusable-workflow-contracts.json"
    contract_target = tmp_path / ".github/reusable-workflow-contracts.json"
    contract_target.parent.mkdir(parents=True)
    contract_target.write_bytes(contract_source.read_bytes())

    findings = scan(tmp_path)
    assert {(finding.caller_path, finding.code) for finding in findings} == {
        (".github/workflows/pr-heimgewebe-commands.yml", "missing_caller_file"),
        (".github/workflows/wgx-guard.yml", "missing_caller_file"),
    }
