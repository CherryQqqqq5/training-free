import json
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_source_real_trace_approved import APPROVED_CATEGORIES, FAILURE_BUCKETS, check

SCRIPT = Path("scripts/check_rashe_source_real_trace_approved.py")
PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_real_trace_approval_packet.json")
SCHEMA = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json")


def copy_inputs(tmp_path: Path) -> tuple[Path, Path]:
    packet = tmp_path / "packet.json"
    schema = tmp_path / "schema.json"
    shutil.copy(PACKET, packet)
    shutil.copy(SCHEMA, schema)
    return packet, schema


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_source_real_trace_approved_checker_compact_passes_current_artifacts():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_source_real_trace_approved_passed"] is True
    assert summary["approval_status"] == "approved"
    assert summary["authorized"] is True
    assert summary["source_collection_authorized"] is True
    assert summary["provider_calls_authorized"] is True
    assert summary["provider_profile"] == "Chuangzhi/Novacode"
    assert summary["provider_model"] == "gpt-4.1"
    assert summary["approved_source_categories"] == list(APPROVED_CATEGORIES)
    assert summary["candidate_generation_authorized"] is False
    assert summary["candidate_pool_ready"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["huawei_acceptance_ready"] is False
    assert summary["candidate_call_count"] == 0
    assert summary["scorer_call_count"] == 0
    assert summary["raw_payload_tracked_count"] == 0
    assert summary["forbidden_field_violation_count"] == 0
    assert summary["artifact_boundary_passed"] is True


def test_fails_if_source_approval_not_signed(tmp_path):
    packet_path, schema_path = copy_inputs(tmp_path)
    packet = load_json(packet_path)
    packet["approval_status"] = "pending"
    packet["authorized"] = False
    packet["source_collection_authorized"] = False
    write_json(packet_path, packet)

    summary = check(packet_path, schema_path, artifact_boundary=False)
    assert summary["rashe_source_real_trace_approved_passed"] is False
    assert "packet_approval_status_invalid:'pending'" in summary["blockers"]
    assert "packet_authorized_invalid:False" in summary["blockers"]
    assert "packet_source_collection_authorized_invalid:False" in summary["blockers"]


def test_fails_if_downstream_or_raw_capture_is_authorized(tmp_path):
    packet_path, schema_path = copy_inputs(tmp_path)
    packet = load_json(packet_path)
    packet["raw_trace_capture_authorized"] = True
    packet["raw_payload_capture_authorized"] = True
    packet["candidate_generation_authorized"] = True
    packet["candidate_pool_ready"] = True
    packet["scorer_authorized"] = True
    packet["performance_evidence"] = True
    packet["huawei_acceptance_ready"] = True
    write_json(packet_path, packet)

    summary = check(packet_path, schema_path, artifact_boundary=False)
    assert summary["rashe_source_real_trace_approved_passed"] is False
    for field in [
        "raw_trace_capture_authorized",
        "raw_payload_capture_authorized",
        "candidate_generation_authorized",
        "candidate_pool_ready",
        "scorer_authorized",
        "performance_evidence",
        "huawei_acceptance_ready",
    ]:
        assert any(field in blocker for blocker in summary["blockers"])


def test_fails_if_forbidden_counts_or_no_leakage_are_nonzero(tmp_path):
    packet_path, schema_path = copy_inputs(tmp_path)
    packet = load_json(packet_path)
    packet["candidate_call_count"] = 1
    packet["scorer_call_count"] = 1
    packet["raw_payload_tracked_count"] = 1
    packet["forbidden_field_violation_count"] = 1
    packet["no_leakage_required"]["gold_used"] = True
    packet["tracked_raw_payload_paths"] = ["outputs/bfcl_runs/raw.json"]
    write_json(packet_path, packet)

    summary = check(packet_path, schema_path, artifact_boundary=False)
    assert summary["rashe_source_real_trace_approved_passed"] is False
    assert "packet_candidate_call_count_not_zero:1" in summary["blockers"]
    assert "packet_scorer_call_count_not_zero:1" in summary["blockers"]
    assert "packet_raw_payload_tracked_count_not_zero:1" in summary["blockers"]
    assert "packet_forbidden_field_violation_count_not_zero:1" in summary["blockers"]
    assert "packet_no_leakage_field_not_false:gold_used" in summary["blockers"]
    assert "packet_tracked_raw_payload_paths_present" in summary["blockers"]


def test_compact_diagnostic_schema_contains_categories_buckets_and_fail_closed_flags():
    schema = load_json(SCHEMA)
    assert schema["properties"]["category"]["enum"] == list(APPROVED_CATEGORIES)
    assert set(schema["properties"]["failure_bucket_counts"]["required"]) == set(FAILURE_BUCKETS)
    assert schema["properties"]["raw_payload_tracked_count"]["const"] == 0
    assert schema["properties"]["forbidden_field_violation_count"]["const"] == 0
    assert schema["properties"]["candidate_generation_authorized"]["const"] is False
    assert schema["properties"]["scorer_authorized"]["const"] is False
    assert schema["properties"]["performance_evidence"]["const"] is False
