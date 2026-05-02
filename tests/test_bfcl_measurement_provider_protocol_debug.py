import json
from pathlib import Path

from scripts.check_bfcl_measurement_provider_protocol_debug_artifact import validate_artifact
from scripts.check_bfcl_measurement_provider_protocol_debug_packet import check as check_packet
from scripts.check_bfcl_measurement_provider_protocol_debug_packet import validate as validate_packet
from scripts.run_bfcl_measurement_provider_protocol_debug import build_plan


PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_measurement_provider_protocol_debug_packet.json")


def load_packet() -> dict:
    return json.loads(PACKET.read_text())


def valid_record() -> dict:
    return {
        "variant": "synthetic_tool_call_required_guard",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
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


def valid_artifact() -> dict:
    return {
        "artifact_kind": "bfcl_measurement_provider_protocol_debug_compact",
        "provider_request_executed": False,
        "records": [valid_record()],
    }


def test_packet_passes_fixed_gpt_4_1_route():
    summary = check_packet(PACKET)
    assert summary["bfcl_measurement_provider_protocol_debug_packet_passed"] is True
    assert summary["route_model"] == "gpt-4.1"
    assert summary["protocol_debug_execution_authorized"] is False
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


def test_artifact_checker_accepts_compact_mock_artifact():
    assert validate_artifact(valid_artifact()) == []


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
