import json
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_approval_packet_review_matrix import EXPECTED_LANES, check

SCRIPT = Path("scripts/check_rashe_approval_packet_review_matrix.py")
MATRIX = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_approval_packet_review_matrix.json")


def write_matrix(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return path


def load_matrix() -> dict:
    return json.loads(MATRIX.read_text())


def test_review_matrix_checker_compact_passes_fail_closed():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_approval_packet_review_matrix_passed"] is True
    assert summary["lane_ids"] == EXPECTED_LANES
    assert summary["performance_lane_last"] is True
    assert summary["candidate_generation_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["huawei_acceptance_ready"] is False


def test_fails_if_lane_missing(tmp_path):
    matrix = load_matrix()
    matrix["lanes"] = matrix["lanes"][:-1]
    summary = check(write_matrix(tmp_path, matrix))
    assert summary["rashe_approval_packet_review_matrix_passed"] is False
    assert "lane_missing:performance_3pp_huawei_acceptance_approval" in summary["blockers"]


def test_fails_if_lane_is_approved(tmp_path):
    matrix = load_matrix()
    matrix["lanes"][0]["current_status"] = "approved"
    summary = check(write_matrix(tmp_path, matrix))
    assert summary["rashe_approval_packet_review_matrix_passed"] is False
    assert "lane_status_not_pending:runtime_behavior_approval:approved" in summary["blockers"]


def test_fails_if_performance_lane_not_last(tmp_path):
    matrix = load_matrix()
    lanes = matrix["lanes"]
    lanes[3], lanes[4] = lanes[4], lanes[3]
    for idx, lane in enumerate(lanes, start=1):
        lane["lane_order"] = idx
    summary = check(write_matrix(tmp_path, matrix))
    assert summary["rashe_approval_packet_review_matrix_passed"] is False
    assert "lane_order_mismatch" in summary["blockers"]
    assert "performance_lane_not_last" in summary["blockers"]


def test_fails_if_scorer_prerequisites_drop_candidate_or_source(tmp_path):
    matrix = load_matrix()
    scorer = next(lane for lane in matrix["lanes"] if lane["lane_id"] == "scorer_dev_holdout_full_approval")
    scorer["prerequisites"] = ["same provider/model/protocol comparator frozen"]
    summary = check(write_matrix(tmp_path, matrix))
    assert summary["rashe_approval_packet_review_matrix_passed"] is False
    assert "scorer_missing_candidate_prerequisite" in summary["blockers"]
    assert "scorer_missing_source_prerequisite" in summary["blockers"]


def test_fails_if_forbidden_claims_missing(tmp_path):
    matrix = load_matrix()
    matrix["lanes"][0]["forbidden_claims"] = []
    summary = check(write_matrix(tmp_path, matrix))
    assert summary["rashe_approval_packet_review_matrix_passed"] is False
    assert "lane_required_list_empty:runtime_behavior_approval:forbidden_claims" in summary["blockers"]
    assert "lane_forbidden_claims_missing:runtime_behavior_approval" in summary["blockers"]


def test_fails_if_matrix_says_huawei_or_performance_ready(tmp_path):
    matrix = load_matrix()
    matrix["huawei_acceptance_ready"] = True
    matrix["performance_evidence"] = True
    summary = check(write_matrix(tmp_path, matrix))
    assert summary["rashe_approval_packet_review_matrix_passed"] is False
    assert "matrix_forbidden_ready_field_true:huawei_acceptance_ready" in summary["blockers"]
    assert "matrix_forbidden_ready_field_true:performance_evidence" in summary["blockers"]
