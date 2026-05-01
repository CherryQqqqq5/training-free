import json
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_main_merge_readiness_after_runtime_behavior import check

SCRIPT = Path("scripts/check_rashe_main_merge_readiness_after_runtime_behavior.py")
ACTIVE = Path("outputs/artifacts/stage1_bfcl_acceptance/active_evidence_index.json")
REPORT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_main_merge_readiness.json")


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def test_legacy_post_runtime_main_readiness_checker_rejects_current_source_approved_matrix():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    summary = json.loads(result.stdout)
    assert summary["rashe_main_merge_after_runtime_behavior_ready"] is False
    assert summary["runtime_behavior_approval_status"] == "approved"
    assert summary["runtime_behavior_authorized"] is True
    assert summary["runtime_behavior_scope"] == "synthetic_default_disabled_only"
    assert summary["runtime_behavior_approved_passed"] is True
    assert summary["after_runtime_matrix_passed"] is False
    assert any("check_rashe_approval_packet_review_matrix_after_runtime_behavior.py" in blocker for blocker in summary["blockers"])
    assert any("source_real_trace_approval:approved" in blocker for blocker in summary["blockers"])
    assert summary["candidate_generation_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["huawei_acceptance_ready"] is False


def test_source_approved_successor_gates_pass_current_artifacts():
    for command in [
        [sys.executable, "scripts/check_rashe_source_real_trace_approved.py", "--compact", "--strict"],
        [sys.executable, "scripts/check_rashe_approval_packet_review_matrix_after_source_approval.py", "--compact", "--strict"],
    ]:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr


def test_fails_if_runtime_status_is_pending(tmp_path):
    active = json.loads(ACTIVE.read_text())
    active["runtime_behavior_approval_status"] = "pending"
    path = write_json(tmp_path / "active.json", active)
    summary = check(path, REPORT)
    assert summary["rashe_main_merge_after_runtime_behavior_ready"] is False
    assert "active_index_runtime_behavior_approval_status_not_approved" in summary["blockers"]


def test_fails_if_ambiguous_offline_scaffold_runtime_key_returns(tmp_path):
    active = json.loads(ACTIVE.read_text())
    active["rashe_offline_scaffold"]["runtime_behavior_authorized"] = False
    path = write_json(tmp_path / "active.json", active)
    summary = check(path, REPORT)
    assert summary["rashe_main_merge_after_runtime_behavior_ready"] is False
    assert "rashe_offline_scaffold_ambiguous_runtime_behavior_authorized_key_present" in summary["blockers"]


def test_fails_if_downstream_authorized(tmp_path):
    active = json.loads(ACTIVE.read_text())
    active["scorer_authorized"] = True
    active["claim_readiness"]["performance_evidence"] = True
    path = write_json(tmp_path / "active.json", active)
    summary = check(path, REPORT)
    assert summary["rashe_main_merge_after_runtime_behavior_ready"] is False
    assert "active_index_downstream_field_true:scorer_authorized" in summary["blockers"]
    assert "claim_readiness_downstream_field_true:performance_evidence" in summary["blockers"]


def test_fails_if_self_referential_current_head_returns(tmp_path):
    active = json.loads(ACTIVE.read_text())
    active["current_head"] = "deadbeef"
    path = write_json(tmp_path / "active.json", active)
    summary = check(path, REPORT)
    assert summary["rashe_main_merge_after_runtime_behavior_ready"] is False
    assert "active_index_self_referential_field_present:current_head" in summary["blockers"]
