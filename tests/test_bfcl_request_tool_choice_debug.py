from __future__ import annotations

import copy
import json

from scripts.build_bfcl_request_tool_choice_debug import build_report
from scripts.check_bfcl_request_tool_choice_debug import validate_artifact, validate_packet


def _packet() -> dict[str, object]:
    return {
        "artifact_kind": "bfcl_request_tool_choice_debug_packet",
        "approval_status": "prepared",
        "authorized": False,
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
        "signed_run_ids": ["web_search_base_0"],
        "compact_only": True,
    }


def test_detects_original_tool_choice_none_when_tools_present() -> None:
    report = build_report()
    record = report["records"][0]
    assert record["run_id"] == "web_search_base_0"
    assert record["tools_present"] is True
    assert record["original_tool_choice_shape"] == "none"
    assert record["proxy_forwarded_tool_choice_shape"] == "none"
    assert report["tool_choice_none_with_tools_present_confirmed"] is True
    assert report["suspected_failure_stage"] == "tool_choice_none_with_tools_present_confirmed"


def test_detects_proposed_required_shape() -> None:
    record = build_report()["records"][0]
    assert record["expected_tool_choice_shape_if_fixed"] == "required_string"
    assert record["proposed_proxy_forwarded_tool_choice_shape"] == "required_string"
    assert record["proposed_proxy_forwarded_tools_count_bucket"] == "two"


def test_rejects_raw_prompt_case_secret_material() -> None:
    report = build_report()
    report["records"][0]["prompt_text"] = "redacted"
    report["records"][0]["request_token_field_shape"] = "https" + "://example.invalid"
    blockers = validate_artifact(report)
    assert any("forbidden_key" in blocker for blocker in blockers)
    assert any("forbidden_value" in blocker for blocker in blockers)


def test_rejects_provider_generate_evaluate_scorer_flags() -> None:
    for key in ("provider_request_executed", "live_telemetry_executed", "bfcl_generate_executed", "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed"):
        report = build_report()
        report[key] = True
        blockers = validate_artifact(report)
        assert any(f"artifact_{key}_not_false" in blocker for blocker in blockers), (key, blockers)


def test_rejects_wrong_id_multiple_ids() -> None:
    report = build_report()
    report["signed_run_ids"] = ["web_search_base_0", "multi_turn_base_0"]
    report["records"][0]["run_id"] = "multi_turn_base_0"
    blockers = validate_artifact(report)
    assert any("artifact_signed_run_ids_invalid" in blocker for blocker in blockers)
    assert any("run_id_invalid" in blocker for blocker in blockers)


def test_validates_patch_surface_label_and_candidate_patch_kind() -> None:
    report = build_report()
    record = report["records"][0]
    assert record["patch_surface_label"] == "bfcl_measurement_responses_to_chat_tool_choice_normalization"
    assert record["candidate_patch_kind"] == "proxy_normalization"
    assert validate_artifact(report) == []
    dirty = copy.deepcopy(report)
    dirty["records"][0]["candidate_patch_kind"] = "broad_runtime_patch"
    assert any("candidate_patch_kind_invalid" in blocker for blocker in validate_artifact(dirty))
    dirty = copy.deepcopy(report)
    dirty["records"][0]["patch_surface_label"] = "broad_runtime"
    assert any("patch_surface_label_invalid" in blocker for blocker in validate_artifact(dirty))


def test_does_not_claim_performance_or_measurement_evidence() -> None:
    report = build_report()
    for key in ("performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready"):
        assert report[key] is False
    packet = _packet()
    assert validate_packet(packet) == []
    packet["performance_evidence"] = True
    assert any("performance_evidence_not_false" in blocker for blocker in validate_packet(packet))


def test_packet_rejects_authorization_expansion() -> None:
    for key in ("provider_request_authorized", "live_telemetry_authorized", "bfcl_generate_authorized", "bfcl_evaluate_authorized", "scorer_authorized", "candidate_runtime_activation_authorized"):
        packet = _packet()
        packet[key] = True
        blockers = validate_packet(packet)
        assert any(f"packet_{key}_not_false" in blocker for blocker in blockers), (key, blockers)


def test_artifact_serializes_without_forbidden_strings() -> None:
    text = json.dumps(build_report(), sort_keys=True).lower()
    for forbidden in ("sk-", "provider payload", "scorer diff", "gold/reference/expected", "candidate output"):
        assert forbidden not in text
