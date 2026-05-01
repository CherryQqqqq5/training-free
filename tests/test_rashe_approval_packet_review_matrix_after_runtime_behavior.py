import json
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_approval_packet_review_matrix_after_runtime_behavior import EXPECTED_LANES, check

SCRIPT = Path("scripts/check_rashe_approval_packet_review_matrix_after_runtime_behavior.py")
MATRIX = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_approval_packet_review_matrix.json")


def write_matrix(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return path


def load_matrix() -> dict:
    return json.loads(MATRIX.read_text())


def test_after_runtime_behavior_matrix_checker_compact_passes_current_artifact():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_approval_packet_review_matrix_after_runtime_behavior_passed"] is True
    assert summary["lane_ids"] == EXPECTED_LANES
    assert summary["runtime_behavior_authorized"] is True
    assert summary["source_collection_authorized"] is False
    assert summary["candidate_generation_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["huawei_acceptance_ready"] is False


def test_fails_if_first_lane_is_not_approved(tmp_path):
    matrix = load_matrix()
    matrix["lanes"][0]["current_status"] = "pending"
    matrix["lanes"][0]["authorized"] = False
    summary = check(write_matrix(tmp_path, matrix))
    assert summary["rashe_approval_packet_review_matrix_after_runtime_behavior_passed"] is False
    assert "first_lane_status_not_approved:pending" in summary["blockers"]
    assert "first_lane_authorized_not_true" in summary["blockers"]


def test_fails_if_downstream_lane_is_approved(tmp_path):
    matrix = load_matrix()
    matrix["lanes"][1]["current_status"] = "approved"
    matrix["lanes"][1]["authorized"] = True
    summary = check(write_matrix(tmp_path, matrix))
    assert summary["rashe_approval_packet_review_matrix_after_runtime_behavior_passed"] is False
    assert "downstream_lane_status_not_pending:source_real_trace_approval:approved" in summary["blockers"]
    assert "downstream_lane_authorized_not_false:source_real_trace_approval" in summary["blockers"]


def test_fails_if_downstream_readiness_is_true(tmp_path):
    matrix = load_matrix()
    matrix["performance_evidence"] = True
    matrix["huawei_acceptance_ready"] = True
    summary = check(write_matrix(tmp_path, matrix))
    assert summary["rashe_approval_packet_review_matrix_after_runtime_behavior_passed"] is False
    assert "matrix_forbidden_ready_field_true:performance_evidence" in summary["blockers"]
    assert "matrix_forbidden_ready_field_true:huawei_acceptance_ready" in summary["blockers"]


def test_fails_if_scorer_prerequisites_drop_candidate_or_source(tmp_path):
    matrix = load_matrix()
    scorer = next(lane for lane in matrix["lanes"] if lane["lane_id"] == "scorer_dev_holdout_full_approval")
    scorer["prerequisites"] = ["same provider/model/protocol comparator frozen"]
    summary = check(write_matrix(tmp_path, matrix))
    assert summary["rashe_approval_packet_review_matrix_after_runtime_behavior_passed"] is False
    assert "scorer_missing_candidate_prerequisite" in summary["blockers"]
    assert "scorer_missing_source_prerequisite" in summary["blockers"]
