from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_one_id_live_shape_telemetry_gate import ALLOWED_TELEMETRY_FIELDS, check, validate_packet
from scripts.run_bfcl_one_id_live_shape_telemetry import build_plan, execute_live_telemetry, main as runner_main


def _packet() -> dict[str, object]:
    return json.loads(Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_gate_packet.json").read_text(encoding="utf-8"))


def _assert_rejected(packet: dict[str, object], expected: str) -> None:
    blockers = validate_packet(packet)
    assert any(expected in blocker for blocker in blockers), blockers


def test_pending_fail_closed_packet_passes() -> None:
    summary = check()
    assert summary["bfcl_one_id_live_shape_telemetry_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["signed_run_ids"] == ["web_search_base_0"]
    assert summary["provider_request_authorized"] is False
    assert summary["bfcl_generate_authorized"] is False


def test_rejects_multiple_run_ids() -> None:
    packet = _packet()
    packet["signed_run_ids"] = ["web_search_base_0", "multi_turn_base_0"]
    packet["max_run_ids"] = 2
    _assert_rejected(packet, "signed_run_ids_invalid")
    _assert_rejected(packet, "too_many_run_ids")


def test_rejects_unapproved_run_id() -> None:
    packet = _packet()
    packet["signed_run_ids"] = ["multi_turn_base_0"]
    _assert_rejected(packet, "signed_run_ids_invalid")


def test_rejects_authorized_true_in_pending_packet() -> None:
    packet = _packet()
    packet["authorized"] = True
    packet["provider_request_authorized"] = True
    _assert_rejected(packet, "authorized_invalid_for_pending")
    _assert_rejected(packet, "provider_request_authorized_invalid_for_pending")


def test_rejects_evaluate_scorer_full_baseline_flags() -> None:
    packet = _packet()
    for key in ("bfcl_evaluate_authorized", "scorer_authorized", "full_baseline_authorized", "bfcl_baseline_authorized"):
        bad = copy.deepcopy(packet)
        bad[key] = True
        _assert_rejected(bad, f"{key}_not_false")


def test_rejects_candidate_activation_flags() -> None:
    packet = _packet()
    for key in ("candidate_runtime_activation_authorized", "candidate_generation_authorized", "candidate_jsonl_authorized", "candidate_pool_ready"):
        bad = copy.deepcopy(packet)
        bad[key] = True
        _assert_rejected(bad, f"{key}_not_false")


def test_rejects_performance_3pp_huawei_flags() -> None:
    packet = _packet()
    for key in ("performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready"):
        bad = copy.deepcopy(packet)
        bad[key] = True
        _assert_rejected(bad, f"{key}_not_false")


def test_rejects_route_drift_fallback_openrouter() -> None:
    packet = _packet()
    bad = copy.deepcopy(packet)
    bad["route_model"] = "gpt-4o"
    bad["gpt_4o_fallback_allowed"] = True
    bad["openrouter_allowed"] = True
    _assert_rejected(bad, "route_model_invalid")
    _assert_rejected(bad, "gpt_4o_fallback_allowed_not_false")
    _assert_rejected(bad, "openrouter_allowed_not_false")


def test_rejects_raw_field_names() -> None:
    packet = _packet()
    packet["allowed_telemetry_fields"] = list(ALLOWED_TELEMETRY_FIELDS) + ["raw_provider_response_body"]
    _assert_rejected(packet, "allowed_telemetry_fields_drift")
    _assert_rejected(packet, "forbidden_output_field")


def test_rejects_endpoint_key_literal() -> None:
    packet = _packet()
    packet["notes"] = "https" + "://example.invalid"
    _assert_rejected(packet, "endpoint_or_key_literal")


def test_dry_run_does_not_execute_provider_or_generate() -> None:
    plan = build_plan()
    assert plan["planned_run_id_count"] == 1
    assert plan["provider_request_executed"] is False
    assert plan["bfcl_generate_executed"] is False
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["scorer_executed"] is False
    assert plan["performance_evidence"] is False
    assert plan["blockers"] == []


def test_cli_dry_run_passes_strict_without_execution() -> None:
    assert runner_main(["--dry-run", "--compact", "--strict"]) == 0
    assert runner_main(["--plan-only", "--compact", "--strict"]) == 0


def test_execute_fails_closed_while_pending_without_env_read() -> None:
    summary = execute_live_telemetry()
    assert summary["provider_request_executed"] is False
    assert summary["bfcl_generate_executed"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
    assert summary["diagnostic_written"] is False
    assert summary["blockers"] == ["one_id_live_shape_telemetry_packet_not_approved"]


def test_dry_run_output_contains_only_compact_field_names() -> None:
    plan = build_plan()
    assert plan["telemetry_fields"] == ALLOWED_TELEMETRY_FIELDS
    assert not any(field.startswith("raw_") for field in plan["telemetry_fields"])
    assert "provider_response_has_nonempty_text" in plan["telemetry_fields"]
    assert "suspected_live_failure_stage" in plan["telemetry_fields"]


def test_approved_packet_would_allow_exactly_one_generate_only_telemetry_id() -> None:
    packet = _packet()
    packet["approval_status"] = "approved"
    packet["authorized"] = True
    packet["provider_request_authorized"] = True
    packet["bfcl_generate_authorized"] = True
    blockers = validate_packet(packet)
    assert blockers == []
    assert packet["signed_run_ids"] == ["web_search_base_0"]
    assert packet["bfcl_smoke_authorized"] is False
    assert packet["bfcl_evaluate_authorized"] is False
    assert packet["scorer_authorized"] is False
