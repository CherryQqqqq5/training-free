import json
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_provider_protocol_debug_preflight_packet import check
from scripts.run_rashe_provider_protocol_debug_preflight import build_plan

SCRIPT = Path("scripts/check_rashe_provider_protocol_debug_preflight_packet.py")
RUNNER = Path("scripts/run_rashe_provider_protocol_debug_preflight.py")
PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_protocol_debug_preflight_packet.json")


def copy_packet(tmp_path: Path) -> Path:
    packet = tmp_path / "packet.json"
    shutil.copy(PACKET, packet)
    return packet


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def test_protocol_debug_packet_checker_passes_current_packet():
    result = subprocess.run([sys.executable, str(SCRIPT), "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_provider_protocol_debug_preflight_packet_passed"] is True
    assert summary["approval_status"] == "prepared"
    assert summary["execution_authorized"] is False
    assert summary["provider_request_authorized"] is False
    assert summary["signed_model"] == "gpt-4.1"
    assert summary["fallback_allowed"] is False
    assert summary["source_diagnostic_execution_authorized"] is False
    assert summary["candidate_generation_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["variant_count"] == 5


def test_protocol_debug_runner_dry_run_and_plan_only_do_not_execute():
    for flag in ["--dry-run", "--plan-only"]:
        result = subprocess.run([sys.executable, str(RUNNER), flag, "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        summary = json.loads(result.stdout)
        assert summary["rashe_provider_protocol_debug_preflight_plan_passed"] is True
        assert summary["provider_request_executed"] is False
        assert summary["endpoint_value_read"] is False
        assert summary["api_key_value_read"] is False
        assert summary["source_input_read"] is False
        assert summary["diagnostic_written"] is False
        assert len(summary["variants"]) == 5
        for variant in summary["variants"]:
            assert variant["planned_only"] is True
            assert variant["provider_request_executed"] is False
            assert variant["raw_request_persisted"] is False
            assert variant["raw_response_persisted"] is False
            assert variant["source_input_read"] is False


def test_protocol_debug_execute_without_approval_fails_closed():
    result = subprocess.run([sys.executable, str(RUNNER), "--execute-debug", "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.returncode != 0
    summary = json.loads(result.stdout)
    assert "protocol_debug_execution_not_approved" in summary["blockers"]
    assert summary["provider_request_executed"] is False


def test_protocol_debug_packet_rejects_variant_drift(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["allowed_variants"].append("extra_variant")
    write_json(packet_path, packet)
    blockers = check(packet_path)["blockers"]
    assert "packet_allowed_variants_invalid:" in "\n".join(blockers)
    assert "packet_allowed_variants_count_invalid" in blockers


def test_protocol_debug_packet_rejects_gpt4o_fallback_and_downstream(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["fallback_allowed"] = True
    packet["gpt_4o_fallback_allowed"] = True
    packet["candidate_generation_authorized"] = True
    packet["scorer_authorized"] = True
    packet["performance_evidence"] = True
    packet["huawei_acceptance_ready"] = True
    write_json(packet_path, packet)
    blockers = check(packet_path)["blockers"]
    assert "packet_fallback_allowed_not_false:True" in blockers
    assert "packet_gpt_4o_fallback_allowed_not_false:True" in blockers
    assert "packet_candidate_generation_authorized_not_false:True" in blockers
    assert "packet_scorer_authorized_not_false:True" in blockers
    assert "packet_performance_evidence_not_false:True" in blockers
    assert "packet_huawei_acceptance_ready_not_false:True" in blockers


def test_protocol_debug_packet_rejects_source_input_and_raw_persistence(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["source_input_root_read_authorized"] = True
    packet["bfcl_source_input_authorized"] = True
    packet["raw_request_persisted"] = True
    packet["raw_response_persisted"] = True
    packet["notes"].append("endpoint=redacted")
    write_json(packet_path, packet)
    blockers = check(packet_path)["blockers"]
    assert "packet_source_input_root_read_authorized_not_false:True" in blockers
    assert "packet_bfcl_source_input_authorized_not_false:True" in blockers
    assert "packet_raw_request_persisted_not_false:True" in blockers
    assert "packet_raw_response_persisted_not_false:True" in blockers
    assert "packet_contains_forbidden_secret_or_endpoint_fragment:endpoint=" in blockers
