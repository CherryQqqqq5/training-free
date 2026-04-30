import json
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_main_merge_readiness import check

SCRIPT = Path("scripts/check_rashe_main_merge_readiness.py")
REPORT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_main_merge_readiness.json")
ACTIVE = Path("outputs/artifacts/stage1_bfcl_acceptance/active_evidence_index.json")


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def test_rashe_main_merge_readiness_compact_passes_fail_closed():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_main_merge_ready"] is True
    assert summary["main_merge_claim_scope"] == "offline_scaffold_only"
    assert summary["not_bfcl_performance_readiness"] is True
    assert summary["rashe_offline_scaffold_ready"] is True
    assert summary["approval_packet_review_matrix_passed"] is True
    assert summary["approval_packets_fail_closed"] is True
    assert summary["artifact_boundary_passed"] is True
    assert summary["deterministic_negative_evidence_present"] is True
    assert summary["candidate_pool_ready"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["sota_3pp_claim_ready"] is False
    assert summary["huawei_acceptance_ready"] is False
    assert summary["bfcl_performance_ready"] is False


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
