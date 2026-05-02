import json
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_provider_route_update_approved import check

SCRIPT = Path("scripts/check_rashe_provider_route_update_approved.py")
PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_route_update_approval_packet.json")


def copy_packet(tmp_path: Path) -> Path:
    packet = tmp_path / "route_packet.json"
    shutil.copy(PACKET, packet)
    return packet


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def test_route_update_checker_passes_current_packet():
    result = subprocess.run([sys.executable, str(SCRIPT), "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_provider_route_update_approved_passed"] is True
    assert summary["route_update_required"] is True
    assert summary["old_signed_model"] == "gpt-5.2"
    assert summary["old_signed_model_active"] is False
    assert summary["new_signed_model"] == "gpt-4.1"
    assert summary["gpt_4_1_fc_preflight_passed"] is True
    assert summary["gpt_4o_observed_supported"] is True
    assert summary["gpt_4o_fallback_allowed"] is False
    assert summary["phase_b_auto_authorized"] is False
    assert summary["candidate_generation_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False


def test_route_update_rejects_old_or_drifted_route(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["new_signed_model"] = "gpt-5.2"
    packet["old_signed_model_active"] = True
    write_json(packet_path, packet)
    blockers = check(packet_path)["blockers"]
    assert "packet_new_signed_model_invalid:'gpt-5.2'" in blockers
    assert "packet_old_signed_model_active_invalid:True" in blockers


def test_route_update_rejects_gpt4o_fallback_and_downstream_authorization(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["new_signed_model"] = "gpt-4o"
    packet["gpt_4o_fallback_allowed"] = True
    packet["fallback_allowed"] = True
    packet["phase_b_auto_authorized"] = True
    packet["candidate_generation_authorized"] = True
    packet["scorer_authorized"] = True
    packet["performance_evidence"] = True
    packet["huawei_acceptance_ready"] = True
    write_json(packet_path, packet)
    blockers = check(packet_path)["blockers"]
    assert "packet_new_signed_model_invalid:'gpt-4o'" in blockers
    assert "packet_gpt_4o_fallback_allowed_invalid:True" in blockers
    assert "packet_fallback_allowed_invalid:True" in blockers
    assert "packet_phase_b_auto_authorized_invalid:True" in blockers
    assert "packet_candidate_generation_authorized_invalid:True" in blockers
    assert "packet_scorer_authorized_invalid:True" in blockers
    assert "packet_performance_evidence_invalid:True" in blockers
    assert "packet_huawei_acceptance_ready_invalid:True" in blockers


def test_route_update_rejects_leakage_policy_drift(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["endpoint_policy"]["env_only"] = False
    packet["api_key_policy"]["value_committed"] = True
    packet["notes"].append("endpoint=https://redacted.invalid")
    write_json(packet_path, packet)
    blockers = check(packet_path)["blockers"]
    assert "packet_endpoint_env_only_not_true" in blockers
    assert "packet_api_key_value_committed_not_false:True" in blockers
    assert "packet_contains_forbidden_secret_or_endpoint_fragment:https://" in blockers
