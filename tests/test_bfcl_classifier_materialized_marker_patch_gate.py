from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_classifier_materialized_marker_patch_gate import REQUIRED_CRITERIA, validate_packet

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_classifier_materialized_marker_patch_gate_packet.json")


def _packet() -> dict:
    return json.loads(PACKET.read_text(encoding="utf-8"))


def test_pending_packet_passes_fail_closed_gate() -> None:
    packet = _packet()
    assert validate_packet(packet) == []
    assert packet["approval_status"] == "pending"
    assert packet["behavior_patch_authorized"] is False


def test_pending_packet_rejects_behavior_patch_authorized_true() -> None:
    packet = _packet()
    packet["behavior_patch_authorized"] = True
    assert any("behavior_patch_authorized_not_false" in blocker for blocker in validate_packet(packet))


def test_rejects_provider_live_bfcl_scorer_baseline_flags() -> None:
    for key in (
        "provider_request_authorized",
        "live_telemetry_authorized",
        "bfcl_generate_authorized",
        "bfcl_smoke_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
    ):
        packet = _packet()
        packet[key] = True
        assert any(f"{key}_not_false" in blocker for blocker in validate_packet(packet)), key


def test_rejects_candidate_performance_flags() -> None:
    for key in (
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
    ):
        packet = _packet()
        packet[key] = True
        assert any(f"{key}_not_false" in blocker for blocker in validate_packet(packet)), key


def test_rejects_broader_scope_and_irrelevance_or_8id_claim() -> None:
    packet = _packet()
    packet["requested_target_scope"] = "general_runtime_classifier"
    assert any("requested_target_scope_invalid" in blocker for blocker in validate_packet(packet))
    packet = _packet()
    packet["requested_future_patch_scope"] = list(packet["requested_future_patch_scope"]) + ["change_provider_route_model"]
    assert any("patch_scope_broadened" in blocker for blocker in validate_packet(packet))
    packet = _packet()
    packet["requested_future_patch_scope"] = [item for item in packet["requested_future_patch_scope"] if item != "no_claim_or_fix_for_irrelevance_unknowns_or_broader_8id_readiness"]
    assert any("required_patch_scope_missing" in blocker for blocker in validate_packet(packet))


def test_requires_all_offline_acceptance_criteria() -> None:
    for criterion in REQUIRED_CRITERIA:
        packet = _packet()
        packet["offline_acceptance_criteria"] = [item for item in packet["offline_acceptance_criteria"] if item != criterion]
        assert any("offline_acceptance_criteria_missing" in blocker for blocker in validate_packet(packet)), criterion


def test_requires_marker_condition_and_error_preservation_scope() -> None:
    packet = _packet()
    packet["requested_behavior"] = "mark_every_nonempty_decode_generated"
    assert any("requested_behavior_invalid" in blocker for blocker in validate_packet(packet))
    packet = _packet()
    packet["requested_condition"] = "any_nonempty_decode"
    assert any("requested_condition_invalid" in blocker for blocker in validate_packet(packet))
    for required in (
        "explicit_handler_error_phrases_remain_protocol_error",
        "structured_error_exception_keys_remain_protocol_error",
        "protocol_error_indicators_remain_protocol_error",
        "true_empty_remains_empty",
        "missing_result_remains_missing",
        "prior_generated_marker_behavior_unchanged",
    ):
        packet = _packet()
        packet["requested_future_patch_scope"] = [item for item in packet["requested_future_patch_scope"] if item != required]
        assert any("required_patch_scope_missing" in blocker for blocker in validate_packet(packet)), required


def test_rejects_raw_secret_case_provider_scorer_fields() -> None:
    packet = _packet()
    packet["prompt_" + "text"] = "redacted"
    assert any("forbidden_key" in blocker for blocker in validate_packet(packet))
    packet = _packet()
    packet["notes"] = "api " + "key value"
    assert any("forbidden_value" in blocker for blocker in validate_packet(packet))
    packet = _packet()
    packet["candidate_" + "output_payload"] = "redacted"
    assert any("forbidden_key" in blocker for blocker in validate_packet(packet))


def test_rejects_route_fallback_openrouter() -> None:
    for key, value in (("route_model", "gpt-5.2"), ("gpt_4o_fallback_enabled", True), ("gpt_5_2_active", True), ("openrouter_enabled", True)):
        packet = copy.deepcopy(_packet())
        packet[key] = value
        assert validate_packet(packet)


def test_requires_gate_metadata_and_source_stage() -> None:
    packet = _packet()
    packet["requested_patch_kind"] = "materialization_writer_change"
    assert any("requested_patch_kind_invalid" in blocker for blocker in validate_packet(packet))
    packet = _packet()
    packet["source_stage"] = "unknown_compact_status_after_decode"
    assert any("source_stage_invalid" in blocker for blocker in validate_packet(packet))
    packet = _packet()
    packet["source_telemetry_artifact"] = "outputs/artifacts/stage1_bfcl_acceptance/other.json"
    assert any("source_telemetry_artifact_invalid" in blocker for blocker in validate_packet(packet))


def test_rejects_patch_authorization_or_materialization_writer_change() -> None:
    packet = _packet()
    packet["authorized"] = True
    assert any("authorized_not_false" in blocker for blocker in validate_packet(packet))
    packet = _packet()
    packet["forbidden_patch_scope"] = [item for item in packet["forbidden_patch_scope"] if item != "materialization_writer_change"]
    assert any("forbidden_patch_scope_missing" in blocker for blocker in validate_packet(packet))
