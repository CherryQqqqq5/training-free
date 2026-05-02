from __future__ import annotations

import json

from scripts.check_bfcl_tool_choice_normalization_patch_gate import validate_design, validate_packet, validate_result


def _packet() -> dict[str, object]:
    return {
        "artifact_kind": "bfcl_tool_choice_normalization_patch_gate_packet",
        "approval_status": "prepared",
        "authorized": False,
        "patch_authorized": False,
        "provider_request_authorized": False,
        "live_telemetry_authorized": False,
        "bfcl_generate_authorized": False,
        "bfcl_smoke_authorized": False,
        "bfcl_evaluate_authorized": False,
        "scorer_authorized": False,
        "full_baseline_authorized": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "gpt_4o_fallback_enabled": False,
        "gpt_5_2_active": False,
        "openrouter_enabled": False,
        "requested_patch_name": "bfcl_measurement_responses_to_chat_tool_choice_normalization",
        "requested_patch_kind": "proxy_normalization",
        "requested_target_scope": "bfcl_measurement_generate_path_only",
        "requested_condition": "tools_present_and_tool_choice_missing_or_none",
        "requested_normalized_tool_choice": "required",
    }


def _design() -> dict[str, object]:
    return {
        "artifact_kind": "bfcl_tool_choice_normalization_patch_design",
        "approval_status": "prepared",
        "patch_name": "bfcl_measurement_responses_to_chat_tool_choice_normalization",
        "patch_kind": "proxy_normalization",
        "target_scope": "bfcl_measurement_generate_path_only",
        "condition": "tools_present_and_tool_choice_missing_or_none",
        "normalized_tool_choice": "required",
        "forbidden_scope": ["candidate", "scorer", "baseline", "performance", "general_runtime_if_not_config_gated"],
        "rollback_plan": ["revert_future_behavior_patch_commit", "rerun_no_provider_tool_choice_debug_checker"],
        "offline_tests_required": [
            "missing_tool_choice_with_tools_normalizes_to_required_in_bfcl_measurement_path",
            "explicit_none_tool_choice_with_tools_normalizes_to_required_in_bfcl_measurement_path",
            "tools_absent_does_not_normalize",
            "explicit_required_or_function_object_is_preserved",
            "route_remains_novacode_gpt_4_1",
            "candidate_scorer_baseline_performance_flags_remain_false",
        ],
        "no_provider_required": True,
        "no_bfcl_generate_required": True,
        "no_performance_claim": True,
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "gpt_4o_fallback_enabled": False,
        "gpt_5_2_active": False,
        "openrouter_enabled": False,
        "patch_authorized": False,
        "provider_request_authorized": False,
        "live_telemetry_authorized": False,
        "bfcl_generate_authorized": False,
        "bfcl_smoke_authorized": False,
        "bfcl_evaluate_authorized": False,
        "scorer_authorized": False,
        "full_baseline_authorized": False,
        "candidate_runtime_activation_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
    }


def _result() -> dict[str, object]:
    return {
        "artifact_kind": "bfcl_tool_choice_normalization_patch_result",
        "approval_status": "completed",
        "patch_name": "bfcl_measurement_responses_to_chat_tool_choice_normalization",
        "patch_kind": "proxy_normalization",
        "target_scope": "bfcl_measurement_generate_path_only",
        "condition": "tools_present_and_tool_choice_missing_or_none",
        "normalized_tool_choice": "required",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "patch_authorized": True,
        "patch_completed": True,
        "provider_request_authorized": False,
        "live_telemetry_authorized": False,
        "bfcl_generate_authorized": False,
        "bfcl_smoke_authorized": False,
        "bfcl_evaluate_authorized": False,
        "scorer_authorized": False,
        "full_baseline_authorized": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "gpt_4o_fallback_enabled": False,
        "gpt_5_2_active": False,
        "openrouter_enabled": False,
        "code_paths_touched": ["src/grc/runtime/proxy.py", "configs/runtime_bfcl_structured.yaml"],
    }


def test_prepared_fail_closed_packet_and_design_pass() -> None:
    assert validate_packet(_packet()) == []
    assert validate_design(_design()) == []


def test_completed_patch_result_passes_without_execution_authorization() -> None:
    assert validate_result(_result()) == []


def test_rejects_authorized_patch_state_in_prepared_gate() -> None:
    packet = _packet()
    packet["patch_authorized"] = True
    assert any("packet_patch_authorized_not_false" in blocker for blocker in validate_packet(packet))
    design = _design()
    design["patch_authorized"] = True
    assert any("design_patch_authorized_not_false" in blocker for blocker in validate_design(design))


def test_rejects_broader_target_scope() -> None:
    design = _design()
    design["target_scope"] = "general_runtime"
    assert any("design_target_scope_invalid" in blocker for blocker in validate_design(design))
    packet = _packet()
    packet["requested_target_scope"] = "all_proxy_requests"
    assert any("packet_requested_target_scope_invalid" in blocker for blocker in validate_packet(packet))


def test_rejects_normalization_when_tools_absent() -> None:
    design = _design()
    design["condition"] = "tool_choice_missing_or_none"
    assert any("design_condition_invalid" in blocker for blocker in validate_design(design))
    packet = _packet()
    packet["requested_condition"] = "tools_absent_or_present"
    assert any("packet_requested_condition_invalid" in blocker for blocker in validate_packet(packet))


def test_rejects_normalized_value_other_than_required() -> None:
    design = _design()
    design["normalized_tool_choice"] = "auto"
    assert any("design_normalized_tool_choice_invalid" in blocker for blocker in validate_design(design))
    packet = _packet()
    packet["requested_normalized_tool_choice"] = "none"
    assert any("packet_requested_normalized_tool_choice_invalid" in blocker for blocker in validate_packet(packet))


def test_rejects_provider_bfcl_scorer_candidate_performance_authorization() -> None:
    for key in (
        "provider_request_authorized",
        "live_telemetry_authorized",
        "bfcl_generate_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "candidate_runtime_activation_authorized",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
    ):
        packet = _packet()
        packet[key] = True
        assert any(f"packet_{key}_not_false" in blocker for blocker in validate_packet(packet)), key
        if key in _design():
            design = _design()
            design[key] = True
            assert any(f"design_{key}_not_false" in blocker for blocker in validate_design(design)), key
        if key in _result():
            result = _result()
            result[key] = True
            assert any(f"result_{key}_not_false" in blocker for blocker in validate_result(result)), key


def test_rejects_route_drift_fallback_openrouter() -> None:
    packet = _packet()
    packet["route_model"] = "gpt-5.2"
    assert "packet_route_drift" in validate_packet(packet)
    for key in ("gpt_4o_fallback_enabled", "gpt_5_2_active", "openrouter_enabled"):
        design = _design()
        design[key] = True
        assert any(key in blocker for blocker in validate_design(design)), key


def test_rejects_raw_secret_material() -> None:
    design = _design()
    design["prompt_text"] = "redacted"
    design["rollback_plan"] = ["https" + "://example.invalid"]
    blockers = validate_design(design)
    assert any("forbidden_key" in blocker for blocker in blockers)
    assert any("forbidden_value" in blocker for blocker in blockers)


def test_validates_design_includes_rollback_and_offline_test_plan() -> None:
    design = _design()
    design["rollback_plan"] = []
    assert "design_rollback_plan_missing" in validate_design(design)
    design = _design()
    design["offline_tests_required"] = ["missing_tool_choice_with_tools_normalizes_to_required_in_bfcl_measurement_path"]
    assert "design_offline_tests_required_incomplete" in validate_design(design)


def test_result_requires_completed_patch_state_and_paths() -> None:
    result = _result()
    result["patch_completed"] = False
    assert any("result_patch_completed_not_true" in blocker for blocker in validate_result(result))
    result = _result()
    result["code_paths_touched"] = ["src/grc/runtime/proxy.py"]
    assert any("result_code_paths_touched_incomplete" in blocker for blocker in validate_result(result))


def test_design_serializes_without_secret_like_values() -> None:
    text = json.dumps(_design(), sort_keys=True).lower()
    for forbidden in ("sk-", "provider payload", "scorer diff", "candidate output"):
        assert forbidden not in text
    assert "performance_evidence" in text
