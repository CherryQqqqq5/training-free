import json
import subprocess
import sys
from pathlib import Path

import scripts.check_rashe_main_merge_readiness as readiness
from scripts.check_rashe_main_merge_readiness import check

SCRIPT = Path("scripts/check_rashe_main_merge_readiness.py")
REPORT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_main_merge_readiness.json")
ACTIVE = Path("outputs/artifacts/stage1_bfcl_acceptance/active_evidence_index.json")


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def test_legacy_main_merge_readiness_rejects_current_post_runtime_artifacts():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    summary = json.loads(result.stdout)
    assert summary["rashe_main_merge_ready"] is False
    assert summary["main_merge_claim_scope"] == "offline_scaffold_only"
    assert summary["runtime_behavior_authorized"] is False
    assert any("check_rashe_approval_packets.py" in blocker for blocker in summary["blockers"])
    assert any("check_rashe_approval_packet_review_matrix.py" in blocker for blocker in summary["blockers"])
    assert any("runtime_behavior" in blocker for blocker in summary["blockers"])


def test_source_approved_successor_gate_is_separate_from_legacy_gate():
    legacy = subprocess.run(
        [sys.executable, "scripts/check_rashe_main_merge_readiness_after_runtime_behavior.py", "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert legacy.returncode != 0
    legacy_summary = json.loads(legacy.stdout)
    assert legacy_summary["rashe_main_merge_after_runtime_behavior_ready"] is False
    assert legacy_summary["after_runtime_matrix_passed"] is False

    result = subprocess.run(
        [sys.executable, "scripts/check_rashe_approval_packet_review_matrix_after_source_approval.py", "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_approval_packet_review_matrix_after_source_approval_passed"] is True
    assert summary["source_collection_authorized"] is True
    assert summary["provider_calls_authorized"] is True
    assert summary["candidate_generation_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["huawei_acceptance_ready"] is False


def test_fails_if_report_scope_is_not_offline_scaffold(tmp_path):
    report = json.loads(REPORT.read_text())
    report["main_merge_claim_scope"] = "bfcl_performance"
    summary = check(write_json(tmp_path / "report.json", report), ACTIVE)
    assert summary["rashe_main_merge_ready"] is False
    assert "report_scope_not_offline_scaffold_only" in summary["blockers"]


def test_fails_if_active_index_route_not_rashe(tmp_path):
    active = json.loads(ACTIVE.read_text())
    active["active_route"] = "legacy_deterministic"
    summary = check(REPORT, write_json(tmp_path / "active.json", active))
    assert summary["rashe_main_merge_ready"] is False
    assert "active_index_route_not_rashe" in summary["blockers"]


def test_fails_if_deterministic_negative_evidence_missing(tmp_path):
    active = json.loads(ACTIVE.read_text())
    active["deterministic_stage1_family_search_exhausted"] = False
    active.pop("deterministic_argument_structural_and_tool_name_paths_zero_yield", None)
    summary = check(REPORT, write_json(tmp_path / "active.json", active))
    assert summary["rashe_main_merge_ready"] is False
    assert "deterministic_negative_evidence_missing" in summary["blockers"]
    assert "deterministic_zero_yield_summary_missing" in summary["blockers"]


def test_fails_if_report_sets_performance_ready(tmp_path):
    report = json.loads(REPORT.read_text())
    report["fail_closed_fields"]["performance_evidence"] = True
    report["fail_closed_fields"]["huawei_acceptance_ready"] = True
    summary = check(write_json(tmp_path / "report.json", report), ACTIVE)
    assert summary["rashe_main_merge_ready"] is False
    assert "report_forbidden_true:fail_closed_fields.performance_evidence" in summary["blockers"]
    assert "report_forbidden_true:fail_closed_fields.huawei_acceptance_ready" in summary["blockers"]


def test_legacy_checker_accepts_main_branch_name_but_still_rejects_post_runtime_artifacts(monkeypatch):
    real_git_value = readiness.git_value

    def fake_git_value(args):
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return "main"
        return real_git_value(args)

    monkeypatch.setattr(readiness, "git_value", fake_git_value)
    summary = check(REPORT, ACTIVE)
    assert summary["rashe_main_merge_ready"] is False
    assert summary["target_branch"] == "main"
    assert summary["source_branch_provenance"] == "stage1-bfcl-performance-sprint"
    assert summary["performance_evidence"] is False
    assert summary["huawei_acceptance_ready"] is False


def test_fails_if_target_branch_unexpected(monkeypatch):
    real_git_value = readiness.git_value

    def fake_git_value(args):
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return "feature/unreviewed"
        return real_git_value(args)

    monkeypatch.setattr(readiness, "git_value", fake_git_value)
    summary = check(REPORT, ACTIVE)
    assert summary["rashe_main_merge_ready"] is False
    assert "unexpected_target_branch:feature/unreviewed" in summary["blockers"]
