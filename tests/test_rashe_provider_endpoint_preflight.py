import json
import os
import shutil
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

from scripts.check_rashe_provider_endpoint_preflight_packet import check
from scripts.run_rashe_provider_endpoint_preflight import build_plan

SCRIPT = Path("scripts/check_rashe_provider_endpoint_preflight_packet.py")
RUNNER = Path("scripts/run_rashe_provider_endpoint_preflight.py")
PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_endpoint_preflight_packet.json")
SECRET = "https://redacted.invalid/preflight"
KEY = "redacted-token-value"


def copy_packet(tmp_path: Path) -> Path:
    packet = tmp_path / "packet.json"
    shutil.copy(PACKET, packet)
    return packet


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def test_endpoint_preflight_packet_checker_passes_current_packet():
    result = subprocess.run([sys.executable, str(SCRIPT), "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_provider_endpoint_preflight_packet_passed"] is True
    assert summary["preflight_only"] is True
    assert summary["provider_request_authorized_in_this_commit"] is False
    assert summary["provider_preflight_requires_second_review"] is True
    assert summary["signed_primary_model"] == "gpt-5.2"
    assert summary["optional_capability_observation_model"] == "gpt-5.4"
    assert summary["phase_b_execution_authorized"] is False
    assert summary["candidate_generation_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False


def test_endpoint_preflight_packet_rejects_scope_and_route_drift(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["provider_request_authorized_in_this_commit"] = True
    packet["phase_b_execution_authorized"] = True
    packet["provider_preflight_requires_second_review"] = False
    packet["signed_primary_model"] = "gpt-5.4"
    packet["route_update_required_if_only_optional_model_supported"] = False
    packet["compact_diagnostic_payload_allowed_for_preflight"] = True
    write_json(packet_path, packet)

    blockers = check(packet_path)["blockers"]

    assert "packet_provider_request_authorized_in_this_commit_not_false:True" in blockers
    assert "packet_phase_b_execution_authorized_not_false:True" in blockers
    assert "packet_provider_preflight_requires_second_review_not_true:False" in blockers
    assert "packet_signed_primary_model_invalid:'gpt-5.4'" in blockers
    assert "packet_route_update_required_if_only_optional_model_supported_not_true:False" in blockers
    assert "packet_compact_diagnostic_payload_allowed_for_preflight_not_false:True" in blockers


def test_endpoint_preflight_packet_rejects_forbidden_raw_and_downstream_drift(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["bfcl_case_or_source_prompt_allowed"] = True
    packet["raw_tool_data_allowed"] = True
    packet["candidate_generation_authorized"] = True
    packet["scorer_authorized"] = True
    packet["performance_evidence"] = True
    packet["forbidden_probe_content"].remove("case_id")
    packet["notes"].append("api_key=redacted")
    write_json(packet_path, packet)

    blockers = check(packet_path)["blockers"]

    assert "packet_bfcl_case_or_source_prompt_allowed_not_false:True" in blockers
    assert "packet_raw_tool_data_allowed_not_false:True" in blockers
    assert "packet_candidate_generation_authorized_not_false:True" in blockers
    assert "packet_scorer_authorized_not_false:True" in blockers
    assert "packet_performance_evidence_not_false:True" in blockers
    assert "packet_forbidden_probe_content_missing:case_id" in blockers
    assert "packet_contains_forbidden_secret_or_endpoint_fragment:api_key=" in blockers


def test_endpoint_preflight_runner_dry_run_does_not_request_provider_or_write_diagnostics(monkeypatch):
    monkeypatch.setenv("CHUANGZHI_NOVACODE_ENDPOINT", SECRET)
    monkeypatch.setenv("CHUANGZHI_API_KEY", KEY)
    result = subprocess.run([sys.executable, str(RUNNER), "--dry-run", "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert SECRET not in result.stdout
    assert KEY not in result.stdout
    summary = json.loads(result.stdout)
    assert summary["rashe_provider_endpoint_preflight_plan_passed"] is True
    assert summary["endpoint_present"] is True
    assert summary["key_present"] is True
    assert summary["provider_request_executed"] is False
    assert summary["api_key_value_read"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["diagnostic_written"] is False
    assert summary["raw_payload_persisted"] is False
    assert summary["raw_prompt_persisted"] is False
    assert summary["candidate_generation_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False


def test_endpoint_preflight_runner_plan_only_accepts_absent_env_without_reading_values(monkeypatch):
    monkeypatch.delenv("CHUANGZHI_NOVACODE_ENDPOINT", raising=False)
    monkeypatch.delenv("NOVACODE_ENDPOINT", raising=False)
    monkeypatch.delenv("CHUANGZHI_API_KEY", raising=False)
    monkeypatch.delenv("NOVACODE_API_KEY", raising=False)
    args = Namespace(packet=PACKET, dry_run=False, plan_only=True)
    summary = build_plan(args, environ={})
    assert summary["rashe_provider_endpoint_preflight_plan_passed"] is True
    assert summary["endpoint_present"] is False
    assert summary["key_present"] is False
    assert summary["provider_request_executed"] is False
    assert summary["api_key_value_read"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["blockers"] == []


def test_endpoint_preflight_runner_requires_plan_or_dry_run():
    args = Namespace(packet=PACKET, dry_run=False, plan_only=False)
    summary = build_plan(args, environ={})
    assert summary["rashe_provider_endpoint_preflight_plan_passed"] is False
    assert "dry_run_or_plan_only_required" in summary["blockers"]
