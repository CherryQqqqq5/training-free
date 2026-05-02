import copy
import json
import subprocess
import sys
from pathlib import Path

from scripts.build_bfcl_proxy_runtime_adapter_shape_diff import build_report
from scripts.check_bfcl_proxy_runtime_adapter_debug_packet import check as check_packet
from scripts.check_bfcl_proxy_runtime_adapter_debug_packet import validate as validate_packet
from scripts.check_bfcl_proxy_runtime_adapter_shape_diff import validate as validate_shape_diff

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_runtime_adapter_debug_packet.json")
BUILD_SCRIPT = Path("scripts/build_bfcl_proxy_runtime_adapter_shape_diff.py")
CHECK_PACKET_SCRIPT = Path("scripts/check_bfcl_proxy_runtime_adapter_debug_packet.py")
CHECK_SHAPE_SCRIPT = Path("scripts/check_bfcl_proxy_runtime_adapter_shape_diff.py")


def load_packet() -> dict:
    return json.loads(PACKET.read_text())


def run_json(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.stdout, result.stderr
    return result, json.loads(result.stdout)


def test_packet_passes_prepared_fail_closed_state():
    summary = check_packet(PACKET)
    assert summary["bfcl_proxy_runtime_adapter_debug_packet_passed"] is True
    assert summary["approval_status"] == "prepared"
    assert summary["route_model"] == "gpt-4.1"
    assert summary["provider_request_authorized"] is False
    assert summary["bfcl_smoke_authorized"] is False


def test_packet_rejects_route_drift_and_fallbacks():
    packet = load_packet()
    packet["route_model"] = "gpt-5.2"
    packet["gpt_4o_fallback_allowed"] = True
    packet["openrouter_allowed"] = True
    blockers = "\n".join(validate_packet(packet))
    assert "proxy_adapter_debug_packet_route_model_invalid:'gpt-5.2'" in blockers
    assert "proxy_adapter_debug_packet_gpt_4o_fallback_allowed_not_false:True" in blockers
    assert "proxy_adapter_debug_packet_openrouter_allowed_not_false:True" in blockers


def test_packet_rejects_execution_candidate_scorer_and_performance_flags():
    packet = load_packet()
    packet["provider_request_authorized"] = True
    packet["bfcl_smoke_authorized"] = True
    packet["candidate_runtime_activation_authorized"] = True
    packet["candidate_jsonl_authorized"] = True
    packet["candidate_pool_ready"] = True
    packet["bfcl_scorer_authorized"] = True
    packet["performance_evidence"] = True
    packet["sota_3pp_claim_ready"] = True
    packet["huawei_acceptance_ready"] = True
    blockers = "\n".join(validate_packet(packet))
    assert "proxy_adapter_debug_packet_provider_request_authorized_not_false:True" in blockers
    assert "proxy_adapter_debug_packet_bfcl_smoke_authorized_not_false:True" in blockers
    assert "proxy_adapter_debug_packet_candidate_runtime_activation_authorized_not_false:True" in blockers
    assert "proxy_adapter_debug_packet_candidate_jsonl_authorized_not_false:True" in blockers
    assert "proxy_adapter_debug_packet_candidate_pool_ready_not_false:True" in blockers
    assert "proxy_adapter_debug_packet_bfcl_scorer_authorized_not_false:True" in blockers
    assert "proxy_adapter_debug_packet_performance_evidence_not_false:True" in blockers
    assert "proxy_adapter_debug_packet_sota_3pp_claim_ready_not_false:True" in blockers
    assert "proxy_adapter_debug_packet_huawei_acceptance_ready_not_false:True" in blockers


def test_packet_rejects_raw_persistence_endpoint_key_and_scope_drift():
    packet = load_packet()
    packet["raw_request_persistence_authorized"] = True
    packet["raw_response_persistence_authorized"] = True
    packet["endpoint_url"] = "https" + "://example.invalid/v1"
    packet["api_key"] = "sk-" + "E" * 24
    packet["reviewed_run_ids_by_category"]["web_search_base"].append("web_search_base_1")
    blockers = "\n".join(validate_packet(packet))
    assert "proxy_adapter_debug_packet_raw_request_persistence_authorized_not_false:True" in blockers
    assert "proxy_adapter_debug_packet_raw_response_persistence_authorized_not_false:True" in blockers
    assert "proxy_adapter_debug_packet_endpoint_literal_forbidden:endpoint_url" in blockers
    assert "proxy_adapter_debug_packet_key_literal_forbidden:api_key" in blockers
    assert "proxy_adapter_debug_packet_reviewed_run_ids_drift" in blockers
    assert "proxy_adapter_debug_packet_run_id_count_invalid:9" in blockers
    assert "proxy_adapter_debug_packet_run_id_count_exceeds_8:9" in blockers


def test_builder_and_checkers_pass_without_provider_or_bfcl_execution():
    packet_result, packet_summary = run_json([sys.executable, str(CHECK_PACKET_SCRIPT), "--compact", "--strict"])
    assert packet_result.returncode == 0, packet_result.stdout + packet_result.stderr
    assert packet_summary["bfcl_proxy_runtime_adapter_debug_packet_passed"] is True

    build_result, build_summary = run_json([sys.executable, str(BUILD_SCRIPT), "--compact", "--strict"])
    assert build_result.returncode == 0, build_result.stdout + build_result.stderr
    assert build_summary["bfcl_proxy_runtime_adapter_shape_diff_passed"] is True
    assert build_summary["provider_request_executed"] is False
    assert build_summary["bfcl_smoke_executed"] is False
    assert build_summary["scorer_executed"] is False
    assert build_summary["candidate_runtime_activation_authorized"] is False

    check_result, check_summary = run_json([sys.executable, str(CHECK_SHAPE_SCRIPT), "--compact", "--strict"])
    assert check_result.returncode == 0, check_result.stdout + check_result.stderr
    assert check_summary["bfcl_proxy_runtime_adapter_shape_diff_passed"] is True
    assert check_summary["shape_diff_high_level_conclusion"] == "bfcl_proxy_runtime_adapter_envelope_aligned_to_synthetic_contract_shape_without_execution"


def test_shape_diff_records_only_sanitized_structure():
    report = build_report()
    encoded = json.dumps(report, sort_keys=True).lower()
    for forbidden in [
        "return exactly one tool call",
        "run the synthetic protocol check",
        "provider payload value",
        "case_id value",
        "gold value",
        "expected value",
        "reference value",
        "scorer diff value",
        "candidate output value",
    ]:
        assert forbidden not in encoded
    assert report["shape_fields_only"] is True
    assert report["successful_synthetic_provider_contract_shape"]["content_length_buckets"] == ["short", "short"]
    assert "tool_schema_structural_hash" in report["successful_synthetic_provider_contract_shape"]
    assert report["adapter_risk_labels"] == []
    assert "schema_local_additional_properties_false_enforced" in report["adapter_alignment_labels"]
    assert "path_specific_token_policy_chat_max_tokens_responses_max_output_tokens" in report["adapter_alignment_labels"]
    token_policy = report["bfcl_proxy_runtime_planned_shape"]["token_field_presence"]
    assert token_policy["chat_completions"] == {"max_tokens": True, "max_completion_tokens": False, "max_output_tokens": False}
    assert token_policy["responses"] == {"max_tokens": False, "max_completion_tokens": False, "max_output_tokens": True}


def test_shape_diff_rejects_route_fallback_and_openrouter_drift():
    report = build_report()
    report["route_model"] = "gpt-5.2"
    report["bfcl_proxy_runtime_planned_shape"]["route_model"] = "gpt-5.2"
    report["gpt_4o_fallback_allowed"] = True
    report["openrouter_allowed"] = True
    blockers = "\n".join(validate_shape_diff(report))
    assert "proxy_adapter_shape_diff_route_model_invalid:'gpt-5.2'" in blockers
    assert "proxy_adapter_shape_diff_route_model_drift" in blockers
    assert "proxy_adapter_shape_diff_gpt_4o_fallback_allowed_not_false:True" in blockers
    assert "proxy_adapter_shape_diff_openrouter_allowed_not_false:True" in blockers


def test_shape_diff_rejects_unreviewed_ids_and_more_than_eight_scope():
    report = build_report()
    report["reviewed_run_id_references"] = copy.deepcopy(report["reviewed_run_id_references"])
    report["reviewed_run_id_references"]["web_search_base"].append("web_search_base_1")
    blockers = "\n".join(validate_shape_diff(report))
    assert "proxy_adapter_shape_diff_reviewed_run_ids_drift" in blockers
    assert "proxy_adapter_shape_diff_run_id_count_invalid:9" in blockers
    assert "proxy_adapter_shape_diff_run_id_count_exceeds_8:9" in blockers


def test_shape_diff_rejects_raw_persistence_and_sensitive_value_fragments():
    report = build_report()
    report["raw_prompt_persisted"] = True
    report["candidate_runtime_activation_authorized"] = True
    report["leaked_shape_value"] = "provider payload value"
    report["endpoint_debug"] = "https" + "://example.invalid/v1"
    report["key_debug"] = "sk-" + "F" * 24
    blockers = "\n".join(validate_shape_diff(report))
    assert "proxy_adapter_shape_diff_raw_prompt_persisted_not_false:True" in blockers
    assert "proxy_adapter_shape_diff_candidate_runtime_activation_authorized_not_false:True" in blockers
    assert "proxy_adapter_shape_diff_forbidden_value_fragment:provider payload value" in blockers
    assert "proxy_adapter_shape_diff_endpoint_literal_forbidden:endpoint_debug" in blockers
    assert "proxy_adapter_shape_diff_key_literal_forbidden:key_debug" in blockers


def test_shape_diff_rejects_missing_parser_tool_calls():
    report = build_report()
    report["bfcl_proxy_runtime_planned_shape"] = copy.deepcopy(report["bfcl_proxy_runtime_planned_shape"])
    report["bfcl_proxy_runtime_planned_shape"]["parser_expected_response_keys"] = ["choices", "message"]
    blockers = validate_shape_diff(report)
    assert "proxy_adapter_shape_diff_proxy_parser_expected_tool_calls_missing" in blockers


def test_shape_diff_rejects_regressed_alignment_fields():
    report = build_report()
    report["bfcl_proxy_runtime_planned_shape"] = copy.deepcopy(report["bfcl_proxy_runtime_planned_shape"])
    report["bfcl_proxy_runtime_planned_shape"]["tool_choice_mode"] = "required_string"
    report["bfcl_proxy_runtime_planned_shape"]["tool_schema_structural_flags"]["additional_properties_false"] = False
    report["bfcl_proxy_runtime_planned_shape"]["token_field_presence"] = {"max_tokens": "unknown", "max_completion_tokens": "unknown"}
    report["adapter_risk_labels"] = ["proxy_adapter_token_field_unknown_until_capture"]
    blockers = "\n".join(validate_shape_diff(report))
    assert "proxy_adapter_shape_diff_proxy_tool_choice_mode_invalid:'required_string'" in blockers
    assert "proxy_adapter_shape_diff_proxy_additional_properties_false_not_true:False" in blockers
    assert "proxy_adapter_shape_diff_proxy_token_field_presence_invalid" in blockers
    assert "proxy_adapter_shape_diff_adapter_risk_labels_not_empty" in blockers
