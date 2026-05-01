import json
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_source_real_trace_approval_packet import check

SCRIPT = Path("scripts/check_rashe_source_real_trace_approval_packet.py")
PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_real_trace_approval_packet.json")
MATRIX = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_approval_packet_review_matrix.json")


def copy_inputs(tmp_path: Path) -> tuple[Path, Path]:
    packet = tmp_path / "packet.json"
    matrix = tmp_path / "matrix.json"
    shutil.copy(PACKET, packet)
    shutil.copy(MATRIX, matrix)
    return packet, matrix


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_source_real_trace_approval_checker_compact_passes_pending_fail_closed_packet():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["source_real_trace_approval_pending_fail_closed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["authorized"] is False
    assert summary["source_collection_authorized"] is False
    assert summary["provider_calls_authorized"] is False
    assert summary["raw_trace_capture_authorized"] is False
    assert summary["raw_payload_capture_authorized"] is False
    assert summary["candidate_generation_authorized"] is False
    assert summary["candidate_pool_ready"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["huawei_acceptance_ready"] is False
    assert summary["artifact_boundary_passed"] is True
    assert summary["blockers"] == []


def test_fails_if_source_lane_is_approved_or_authorized(tmp_path):
    packet_path, matrix_path = copy_inputs(tmp_path)
    packet = load_json(packet_path)
    packet["approval_status"] = "approved"
    packet["authorized"] = True
    packet["source_collection_authorized"] = True
    write_json(packet_path, packet)

    summary = check(packet_path, matrix_path, artifact_boundary=False)
    assert summary["source_real_trace_approval_pending_fail_closed"] is False
    assert "packet_approval_status_invalid:'approved'" in summary["blockers"]
    assert "packet_authorized_invalid:True" in summary["blockers"]
    assert "packet_source_collection_authorized_invalid:True" in summary["blockers"]


def test_fails_if_provider_or_raw_capture_is_authorized(tmp_path):
    packet_path, matrix_path = copy_inputs(tmp_path)
    packet = load_json(packet_path)
    packet["provider_calls_authorized"] = True
    packet["raw_trace_capture_authorized"] = True
    packet["raw_payload_capture_authorized"] = True
    write_json(packet_path, packet)

    summary = check(packet_path, matrix_path, artifact_boundary=False)
    assert summary["source_real_trace_approval_pending_fail_closed"] is False
    assert "packet_provider_calls_authorized_invalid:True" in summary["blockers"]
    assert "packet_raw_trace_capture_authorized_invalid:True" in summary["blockers"]
    assert "packet_raw_payload_capture_authorized_invalid:True" in summary["blockers"]


def test_fails_if_downstream_authorization_or_counts_are_nonzero(tmp_path):
    packet_path, matrix_path = copy_inputs(tmp_path)
    packet = load_json(packet_path)
    packet["candidate_generation_authorized"] = True
    packet["candidate_pool_ready"] = True
    packet["scorer_authorized"] = True
    packet["performance_evidence"] = True
    packet["huawei_acceptance_ready"] = True
    packet["provider_call_count"] = 1
    packet["source_collection_call_count"] = 1
    packet["candidate_call_count"] = 1
    packet["artifact_boundary_failure_count"] = 1
    write_json(packet_path, packet)

    summary = check(packet_path, matrix_path, artifact_boundary=False)
    assert summary["source_real_trace_approval_pending_fail_closed"] is False
    assert "packet_candidate_generation_authorized_invalid:True" in summary["blockers"]
    assert "packet_candidate_pool_ready_invalid:True" in summary["blockers"]
    assert "packet_scorer_authorized_invalid:True" in summary["blockers"]
    assert "packet_performance_evidence_invalid:True" in summary["blockers"]
    assert "packet_huawei_acceptance_ready_invalid:True" in summary["blockers"]
    assert "packet_count_not_zero:provider_call_count:1" in summary["blockers"]
    assert "packet_count_not_zero:source_collection_call_count:1" in summary["blockers"]
    assert "packet_count_not_zero:candidate_call_count:1" in summary["blockers"]
    assert "packet_count_not_zero:artifact_boundary_failure_count:1" in summary["blockers"]


def test_fails_if_no_leakage_or_forbidden_fields_are_missing_or_true(tmp_path):
    packet_path, matrix_path = copy_inputs(tmp_path)
    packet = load_json(packet_path)
    packet["no_leakage_required"]["gold_used"] = True
    packet["no_leakage_required"].pop("repair_output_used")
    packet["forbidden_fields"].remove("feedback")
    write_json(packet_path, packet)

    summary = check(packet_path, matrix_path, artifact_boundary=False)
    assert summary["source_real_trace_approval_pending_fail_closed"] is False
    assert "packet_no_leakage_field_not_false:gold_used" in summary["blockers"]
    assert "packet_no_leakage_field_not_false:repair_output_used" in summary["blockers"]
    assert "packet_forbidden_field_missing:feedback" in summary["blockers"]


def test_fails_if_raw_path_leaks_into_tracked_payload_paths(tmp_path):
    packet_path, matrix_path = copy_inputs(tmp_path)
    packet = load_json(packet_path)
    packet["tracked_raw_payload_paths"] = ["outputs/bfcl_runs/raw_trace.json"]
    write_json(packet_path, packet)

    summary = check(packet_path, matrix_path, artifact_boundary=False)
    assert summary["source_real_trace_approval_pending_fail_closed"] is False
    assert "packet_tracked_raw_payload_paths_present" in summary["blockers"]
    assert any(blocker.startswith("packet_raw_path_indicator:tracked_raw_payload_paths[0]") for blocker in summary["blockers"])


def test_fails_if_matrix_source_lane_is_not_pending(tmp_path):
    packet_path, matrix_path = copy_inputs(tmp_path)
    matrix = load_json(matrix_path)
    matrix["source_real_trace_approval_status"] = "approved"
    matrix["source_real_trace_authorized"] = True
    for lane in matrix["lanes"]:
        if lane["lane_id"] == "source_real_trace_approval":
            lane["current_status"] = "approved"
            lane["authorized"] = True
            break
    write_json(matrix_path, matrix)

    summary = check(packet_path, matrix_path, artifact_boundary=False)
    assert summary["source_real_trace_approval_pending_fail_closed"] is False
    assert "matrix_source_real_trace_approval_status_not_pending" in summary["blockers"]
    assert "matrix_source_real_trace_authorized_not_false" in summary["blockers"]
    assert "matrix_source_lane_status_not_pending" in summary["blockers"]
    assert "matrix_source_lane_authorized_not_false" in summary["blockers"]
