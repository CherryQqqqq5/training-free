import json
from pathlib import Path

from scripts.check_bfcl_measurement_provider_protocol_debug_artifact import validate_artifact
from scripts.check_bfcl_measurement_provider_protocol_debug_packet import check as check_packet
from scripts.check_bfcl_measurement_provider_protocol_debug_packet import validate as validate_packet
from scripts.run_bfcl_measurement_provider_protocol_debug import build_plan, execute_debug


PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_measurement_provider_protocol_debug_packet.json")


def load_packet() -> dict:
    return json.loads(PACKET.read_text())


def valid_record() -> dict:
    return {
        "variant": "synthetic_pre_bfcl_protocol_debug",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "http_status_class": 2,
        "auth_ok": True,
        "model_available": True,
        "tool_calls_returned": True,
        "raw_provider_payload_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
        "raw_prompt_persisted": False,
        "source_input_read": False,
        "diagnostic_written": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "scorer_feedback_tuning_enabled": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "response_contract": {
            "empty_model_response": False,
            "tool_call_required": True,
            "tool_call_present": True,
            "openai_compatible_response_shape": True,
        },
    }


def valid_artifact(executed: bool = True) -> dict:
    return {
        "artifact_kind": "bfcl_measurement_provider_protocol_debug_compact",
        "provider_request_executed": executed,
        "provider_request_count": 1 if executed else 0,
        "endpoint_present": executed,
        "endpoint_value_read": executed,
        "api_key_present": executed,
        "api_key_value_read": executed,
        "raw_request_persisted": False,
        "raw_response_persisted": False,
        "raw_header_persisted": False,
        "raw_body_persisted": False,
        "records": [valid_record()],
        "blockers": [],
        "bfcl_measurement_provider_protocol_debug_passed": True,
    }


def mock_response() -> dict:
    return {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {"type": "function", "function": {"name": "synthetic_measurement_protocol_ping", "arguments": "{}"}}
                    ]
                }
            }
        ]
    }


def test_packet_passes_fixed_gpt_4_1_route_and_execution_authorization():
    summary = check_packet(PACKET)
    assert summary["bfcl_measurement_provider_protocol_debug_packet_passed"] is True
    assert summary["route_model"] == "gpt-4.1"
    assert summary["protocol_debug_execution_authorized"] is True
    assert summary["provider_request_authorized"] is True
    assert summary["scorer_authorized"] is False


def test_packet_rejects_gpt_4o_fallback():
    packet = load_packet()
    packet["gpt_4o_fallback_allowed"] = True
    assert "protocol_debug_packet_gpt_4o_fallback_allowed_not_false:True" in validate_packet(packet)


def test_packet_rejects_active_gpt_5_2():
    packet = load_packet()
    packet["route_model"] = "gpt-5.2"
    assert "protocol_debug_packet_route_model_invalid:'gpt-5.2'" in validate_packet(packet)


def test_packet_rejects_candidate_activation():
    packet = load_packet()
    packet["candidate_runtime_activation_authorized"] = True
    assert "protocol_debug_packet_candidate_runtime_activation_authorized_not_false:True" in validate_packet(packet)


def test_packet_rejects_raw_persistence_allowed():
    packet = load_packet()
    packet["raw_provider_payload_persistence_authorized"] = True
    assert "protocol_debug_packet_raw_provider_payload_persistence_authorized_not_false:True" in validate_packet(packet)


def test_packet_rejects_endpoint_and_key_literals():
    packet = load_packet()
    packet["endpoint_url"] = "https" + "://example.invalid/v1"
    packet["api_key"] = "sk-" + "C" * 24
    blockers = "\n".join(validate_packet(packet))
    assert "protocol_debug_packet_endpoint_literal_forbidden:endpoint_url" in blockers
    assert "protocol_debug_packet_key_literal_forbidden:api_key" in blockers


def test_packet_rejects_scorer_performance_claim_flags():
    packet = load_packet()
    packet["scorer_authorized"] = True
    packet["performance_evidence"] = True
    packet["sota_3pp_claim_ready"] = True
    packet["huawei_acceptance_ready"] = True
    blockers = "\n".join(validate_packet(packet))
    assert "protocol_debug_packet_scorer_authorized_not_false:True" in blockers
    assert "protocol_debug_packet_performance_evidence_not_false:True" in blockers
    assert "protocol_debug_packet_sota_3pp_claim_ready_not_false:True" in blockers
    assert "protocol_debug_packet_huawei_acceptance_ready_not_false:True" in blockers


def test_runner_dry_run_plan_does_not_read_endpoint_key_or_call_provider():
    plan = build_plan(PACKET)
    assert plan["bfcl_measurement_provider_protocol_debug_plan_passed"] is True
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["provider_request_executed"] is False
    assert plan["bfcl_full_eval_executed"] is False


def test_execute_mode_is_gated_by_packet_approval(tmp_path):
    packet = load_packet()
    packet["provider_request_authorized"] = False
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet))
    summary = execute_debug(packet=packet_path, env={})
    assert summary["provider_request_executed"] is False
    assert "protocol_debug_packet_provider_request_authorized_not_true:False" in summary["blockers"]


def test_env_only_provider_execution_path_mocked_without_value_output():
    calls = []

    def transport(endpoint, key, payload):
        calls.append((endpoint, key, payload))
        return 200, mock_response()

    summary = execute_debug(
        env={"CHUANGZHI_NOVACODE_ENDPOINT": "https://unit.test/v1/chat/completions", "CHUANGZHI_API_KEY": "unit-secret"},
        transport=transport,
    )
    rendered = json.dumps(summary)
    assert summary["bfcl_measurement_provider_protocol_debug_passed"] is True
    assert summary["provider_request_executed"] is True
    assert summary["endpoint_value_read"] is True
    assert summary["api_key_value_read"] is True
    assert len(calls) == 1
    assert "unit-secret" not in rendered
    assert "unit.test" not in rendered
    assert "Return exactly one tool call" not in rendered


def test_execute_mode_missing_endpoint_or_key_fails_closed():
    no_endpoint = execute_debug(env={"CHUANGZHI_API_KEY": "unit-secret"}, transport=lambda *_: (200, mock_response()))
    assert "provider_endpoint_missing" in no_endpoint["blockers"]
    assert no_endpoint["provider_request_executed"] is False
    no_key = execute_debug(env={"CHUANGZHI_NOVACODE_ENDPOINT": "https://unit.test/v1/chat/completions"}, transport=lambda *_: (200, mock_response()))
    assert "provider_key_missing" in no_key["blockers"]
    assert no_key["provider_request_executed"] is False


def test_execute_mode_rejects_gpt_4o_route_drift_in_artifact():
    artifact = valid_artifact()
    artifact["records"][0]["route_model"] = "gpt-4o"
    artifact["records"][0]["gpt_4o_fallback_allowed"] = True
    blockers = "\n".join(validate_artifact(artifact))
    assert "record_0_route_model_invalid:'gpt-4o'" in blockers
    assert "record_0_fallback_not_false" in blockers


def test_artifact_checker_accepts_compact_mock_executed_artifact():
    assert validate_artifact(valid_artifact(executed=True)) == []


def test_artifact_checker_rejects_empty_response():
    artifact = valid_artifact()
    artifact["records"][0]["response_contract"]["empty_model_response"] = True
    assert "record_0_empty_model_response" in validate_artifact(artifact)


def test_artifact_checker_rejects_missing_tool_call():
    artifact = valid_artifact()
    artifact["records"][0]["response_contract"]["tool_call_present"] = False
    assert "record_0_missing_required_tool_call" in validate_artifact(artifact)


def test_artifact_checker_rejects_non_openai_response_shape():
    artifact = valid_artifact()
    artifact["records"][0]["response_contract"]["openai_compatible_response_shape"] = False
    assert "record_0_non_openai_compatible_response_shape" in validate_artifact(artifact)


def test_artifact_checker_rejects_raw_persistence_and_candidate_activation():
    artifact = valid_artifact()
    artifact["records"][0]["raw_provider_payload_persisted"] = True
    artifact["records"][0]["candidate_runtime_activation_authorized"] = True
    blockers = "\n".join(validate_artifact(artifact))
    assert "record_0_raw_provider_payload_persisted_not_false:True" in blockers
    assert "record_0_candidate_runtime_activation_authorized_not_false:True" in blockers


def test_artifact_checker_rejects_endpoint_and_key_literals():
    artifact = valid_artifact()
    artifact["endpoint_debug"] = "https" + "://example.invalid/v1"
    artifact["key_debug"] = "sk-" + "D" * 24
    blockers = "\n".join(validate_artifact(artifact))
    assert "protocol_debug_artifact_endpoint_literal_forbidden" in blockers
    assert "protocol_debug_artifact_key_literal_forbidden" in blockers
