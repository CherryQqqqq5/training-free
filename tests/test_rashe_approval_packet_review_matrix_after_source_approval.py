import json
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_approval_packet_review_matrix_after_source_approval import EXPECTED_LANES, check

SCRIPT = Path("scripts/check_rashe_approval_packet_review_matrix_after_source_approval.py")
MATRIX = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_approval_packet_review_matrix.json")


def write_matrix(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return path


def load_matrix() -> dict:
    return json.loads(MATRIX.read_text())


def test_after_source_approval_matrix_checker_compact_passes_current_artifact():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_approval_packet_review_matrix_after_source_approval_passed"] is True
    assert summary["lane_ids"] == EXPECTED_LANES
    assert summary["runtime_behavior_authorized"] is True
    assert summary["source_collection_authorized"] is True
    assert summary["provider_calls_authorized"] is True
    assert summary["candidate_generation_authorized"] is False
    assert summary["candidate_pool_ready"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["huawei_acceptance_ready"] is False


def test_fails_if_source_lane_is_not_approved(tmp_path):
    matrix = load_matrix()
    matrix["source_real_trace_approval_status"] = "pending"
    matrix["source_real_trace_authorized"] = False
    matrix["source_collection_authorized"] = False
    for lane in matrix["lanes"]:
        if lane["lane_id"] == "source_real_trace_approval":
            lane["current_status"] = "pending"
            lane["authorized"] = False
    summary = check(write_matrix(tmp_path, matrix))
    assert summary["rashe_approval_packet_review_matrix_after_source_approval_passed"] is False
    assert "matrix_source_status_not_approved" in summary["blockers"]
    assert "matrix_source_authorized_not_true" in summary["blockers"]
    assert "matrix_source_collection_authorized_not_true" in summary["blockers"]
    assert "approved_lane_status_invalid:source_real_trace_approval:pending" in summary["blockers"]


def test_fails_if_downstream_lane_is_authorized(tmp_path):
    matrix = load_matrix()
    matrix["candidate_generation_authorized"] = True
    matrix["performance_evidence"] = True
    for lane in matrix["lanes"]:
        if lane["lane_id"] == "candidate_proposer_execution_approval":
            lane["current_status"] = "approved"
            lane["authorized"] = True
    summary = check(write_matrix(tmp_path, matrix))
    assert summary["rashe_approval_packet_review_matrix_after_source_approval_passed"] is False
    assert "matrix_forbidden_ready_field_true:candidate_generation_authorized" in summary["blockers"]
    assert "matrix_forbidden_ready_field_true:performance_evidence" in summary["blockers"]
    assert "pending_lane_status_invalid:candidate_proposer_execution_approval:approved" in summary["blockers"]
    assert "pending_lane_authorized_not_false:candidate_proposer_execution_approval" in summary["blockers"]


def test_fails_if_source_lane_checker_path_is_legacy(tmp_path):
    matrix = load_matrix()
    for lane in matrix["lanes"]:
        if lane["lane_id"] == "source_real_trace_approval":
            lane["approval_checker_path"] = "scripts/check_rashe_source_real_trace_approval_packet.py"
    summary = check(write_matrix(tmp_path, matrix))
    assert summary["rashe_approval_packet_review_matrix_after_source_approval_passed"] is False
    assert "source_lane_checker_invalid" in summary["blockers"]
