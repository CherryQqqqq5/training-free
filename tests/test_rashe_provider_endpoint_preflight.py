import json
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


def args(**overrides):
    values = {"packet": PACKET, "dry_run": False, "plan_only": False, "execute_preflight": False}
    values.update(overrides)
    return Namespace(**values)


def ok_chat():
    return {"ok": True, "status": 200, "json": {"choices": [{"message": {"content": "ok"}}]}}


def ok_tool():
    return {"ok": True, "status": 200, "json": {"choices": [{"message": {"tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "synthetic_preflight_ping", "arguments": "{}"}}]}}]}}


def test_endpoint_preflight_packet_checker_passes_current_packet():
    result = subprocess.run([sys.executable, str(SCRIPT), "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_provider_endpoint_preflight_packet_passed"] is True
    assert summary["preflight_only"] is True
    assert summary["provider_request_authorized"] is True
    assert summary["provider_request_authorized_in_this_commit"] is True
    assert summary["provider_preflight_requires_second_review"] is True
    assert summary["actual_preflight_request_path_implemented"] is True
    assert summary["actual_preflight_executed_in_this_commit"] is False
    assert summary["endpoint_value_read_authorized"] is True
    assert summary["key_value_read_authorized"] is True
    assert summary["signed_primary_model"] == "gpt-4.1"
    assert summary["optional_capability_observation_model"] == "gpt-4o"
    assert summary["phase_b_execution_authorized"] is False
    assert summary["bfcl_source_diagnostic_authorized"] is False
    assert summary["candidate_generation_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False


def test_endpoint_preflight_packet_rejects_scope_and_route_drift(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["provider_request_authorized_in_this_commit"] = False
    packet["endpoint_value_read_authorized"] = False
    packet["key_value_read_authorized"] = False
    packet["phase_b_execution_authorized"] = True
    packet["provider_preflight_requires_second_review"] = False
    packet["signed_primary_model"] = "gpt-4o"
    packet["route_update_required_if_only_optional_model_supported"] = False
    packet["compact_diagnostic_payload_allowed_for_preflight"] = True
    write_json(packet_path, packet)

    blockers = check(packet_path)["blockers"]

    assert "packet_provider_request_authorized_in_this_commit_not_true:False" in blockers
    assert "packet_endpoint_value_read_authorized_not_true:False" in blockers
    assert "packet_key_value_read_authorized_not_true:False" in blockers
    assert "packet_phase_b_execution_authorized_not_false:True" in blockers
    assert "packet_provider_preflight_requires_second_review_not_true:False" in blockers
    assert "packet_signed_primary_model_invalid:'gpt-4o'" in blockers
    assert "packet_route_update_required_if_only_optional_model_supported_not_true:False" in blockers
    assert "packet_compact_diagnostic_payload_allowed_for_preflight_not_false:True" in blockers


def test_endpoint_preflight_packet_rejects_forbidden_raw_and_downstream_drift(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["bfcl_case_or_source_prompt_allowed"] = True
    packet["raw_tool_data_allowed"] = True
    packet["raw_payload_capture_authorized"] = True
    packet["candidate_generation_authorized"] = True
    packet["scorer_authorized"] = True
    packet["performance_evidence"] = True
    packet["forbidden_probe_content"].remove("case_id")
    packet["notes"].append("api_key=redacted")
    write_json(packet_path, packet)

    blockers = check(packet_path)["blockers"]

    assert "packet_bfcl_case_or_source_prompt_allowed_not_false:True" in blockers
    assert "packet_raw_tool_data_allowed_not_false:True" in blockers
    assert "packet_raw_payload_capture_authorized_not_false:True" in blockers
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
    summary = build_plan(args(plan_only=True), environ={})
    assert summary["rashe_provider_endpoint_preflight_plan_passed"] is True
    assert summary["endpoint_present"] is False
    assert summary["key_present"] is False
    assert summary["provider_request_executed"] is False
    assert summary["api_key_value_read"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["blockers"] == []


def test_endpoint_preflight_runner_requires_plan_or_dry_run():
    summary = build_plan(args(), environ={})
    assert summary["rashe_provider_endpoint_preflight_plan_passed"] is False
    assert "dry_run_or_plan_only_required" in summary["blockers"]


def test_execute_preflight_mock_success_prioritizes_gpt_5_2_and_tools_without_leakage():
    calls = []

    def fake_post(endpoint, key, payload):
        calls.append(payload)
        assert endpoint == SECRET
        assert key == KEY
        if "tools" in payload:
            return ok_tool()
        return ok_chat()

    summary = build_plan(args(execute_preflight=True), environ={"CHUANGZHI_NOVACODE_ENDPOINT": SECRET, "CHUANGZHI_API_KEY": KEY}, post_json=fake_post)
    encoded = json.dumps(summary, sort_keys=True)
    assert SECRET not in encoded
    assert KEY not in encoded
    assert summary["rashe_provider_endpoint_preflight_plan_passed"] is True
    assert summary["provider_request_executed"] is True
    assert summary["endpoint_value_read"] is True
    assert summary["api_key_value_read"] is True
    assert summary["auth_ok"] is True
    assert summary["model_gpt_4_1_available"] is True
    assert summary["optional_model_gpt_4o_observed"] is False
    assert summary["tool_calling_supported"] is True
    assert summary["tool_choice_supported"] is True
    assert summary["tool_calls_returned"] is True
    assert summary["raw_payload_persisted"] is False
    assert summary["raw_prompt_persisted"] is False
    assert [call["model"] for call in calls] == ["gpt-4.1", "gpt-4.1"]
    assert "tools" not in calls[0]
    assert calls[1]["tool_choice"]["function"]["name"] == "synthetic_preflight_ping"


def test_execute_preflight_mock_route_update_required_when_only_gpt_5_4_available():
    calls = []

    def fake_post(endpoint, key, payload):
        calls.append(payload["model"])
        if payload["model"] == "gpt-4o":
            return ok_chat()
        return {"ok": False, "status": 404}

    summary = build_plan(args(execute_preflight=True), environ={"CHUANGZHI_NOVACODE_ENDPOINT": SECRET, "CHUANGZHI_API_KEY": KEY}, post_json=fake_post)
    assert summary["rashe_provider_endpoint_preflight_plan_passed"] is False
    assert summary["provider_request_executed"] is True
    assert summary["model_gpt_4_1_available"] is False
    assert summary["optional_model_gpt_4o_observed"] is True
    assert summary["route_update_required"] is True
    assert summary["blocker"] == "route_update_required"
    assert "route_update_required" in summary["blockers"]
    assert calls == ["gpt-4.1", "gpt-4o"]


def test_execute_preflight_mock_tools_not_supported_blocker():
    def fake_post(endpoint, key, payload):
        return ok_chat()

    summary = build_plan(args(execute_preflight=True), environ={"NOVACODE_ENDPOINT": SECRET, "NOVACODE_API_KEY": KEY}, post_json=fake_post)
    assert summary["rashe_provider_endpoint_preflight_plan_passed"] is False
    assert summary["auth_ok"] is True
    assert summary["model_gpt_4_1_available"] is True
    assert summary["tool_calling_supported"] is False
    assert summary["tool_calls_returned"] is False
    assert summary["blocker"] == "tools_not_supported"
    assert "tools_not_supported" in summary["blockers"]


def test_execute_preflight_missing_or_invalid_env_fail_closed_before_request():
    called = False

    def fake_post(endpoint, key, payload):
        nonlocal called
        called = True
        return ok_chat()

    missing_endpoint = build_plan(args(execute_preflight=True), environ={"CHUANGZHI_API_KEY": KEY}, post_json=fake_post)
    assert missing_endpoint["blocker"] == "provider_endpoint_missing"
    assert missing_endpoint["provider_request_executed"] is False
    assert missing_endpoint["endpoint_value_read"] is False
    assert missing_endpoint["api_key_value_read"] is False

    not_https = build_plan(args(execute_preflight=True), environ={"CHUANGZHI_NOVACODE_ENDPOINT": "http://redacted.invalid", "CHUANGZHI_API_KEY": KEY}, post_json=fake_post)
    assert not_https["blocker"] == "provider_endpoint_not_https"
    assert not_https["provider_request_executed"] is False
    assert not_https["endpoint_value_read"] is True
    assert not_https["api_key_value_read"] is False

    missing_key = build_plan(args(execute_preflight=True), environ={"CHUANGZHI_NOVACODE_ENDPOINT": SECRET}, post_json=fake_post)
    assert missing_key["blocker"] == "provider_key_missing"
    assert missing_key["provider_request_executed"] is False
    assert missing_key["endpoint_value_read"] is True
    assert missing_key["api_key_value_read"] is False
    assert called is False
