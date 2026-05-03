from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_live_decode_exception_shape_capture_gate import REQUIRED_COMPACT_FIELDS, check, validate_packet
from scripts.run_bfcl_live_decode_exception_shape_capture import build_plan, execute_live_shape_capture

PACKET_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_live_decode_exception_shape_capture_gate_packet.json")


def _packet() -> dict:
    return json.loads(PACKET_PATH.read_text(encoding="utf-8"))


def test_committed_pending_packet_passes_fail_closed() -> None:
    summary = check(PACKET_PATH)
    assert summary["bfcl_live_decode_exception_shape_capture_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["signed_run_ids"] == ["web_search_base_0"]
    assert summary["compact_field_count"] == len(REQUIRED_COMPACT_FIELDS)


def test_rejects_pending_packet_with_authorized_true() -> None:
    data = _packet()
    data["authorized"] = True
    assert any("authorized_not_false" in blocker for blocker in validate_packet(data))


def test_rejects_multiple_ids() -> None:
    data = _packet()
    data["signed_run_ids"] = ["web_search_base_0", "multi_turn_base_0"]
    assert any("signed_run_ids_invalid" in blocker for blocker in validate_packet(data))


def test_rejects_non_web_search_base_id() -> None:
    data = _packet()
    data["signed_run_ids"] = ["multi_turn_base_0"]
    assert any("signed_run_ids_invalid" in blocker for blocker in validate_packet(data))


def test_rejects_evaluate_scorer_full_baseline_authorization() -> None:
    for key in ("bfcl_evaluate_authorized", "scorer_authorized", "full_baseline_authorized"):
        data = _packet()
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_rejects_candidate_activation_jsonl_pool_authorization() -> None:
    for key in ("candidate_runtime_activation_authorized", "candidate_jsonl_authorized", "candidate_pool_ready"):
        data = _packet()
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_rejects_performance_3pp_huawei_claims() -> None:
    for key in ("performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready"):
        data = _packet()
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_rejects_raw_field_names() -> None:
    data = _packet()
    data["allowed_compact_fields"] = list(REQUIRED_COMPACT_FIELDS) + ["raw_provider_response_body"]
    assert any("extra_compact_fields" in blocker or "forbidden_compact_field" in blocker for blocker in validate_packet(data))


def test_rejects_endpoint_key_literal() -> None:
    data = _packet()
    data["notes"] = "api key value"
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))


def test_rejects_missing_parse_decode_exception_fields() -> None:
    for field in ("bfcl_parse_exception_class", "bfcl_decode_exception_class", "suspected_live_decode_failure_stage"):
        data = _packet()
        data["allowed_compact_fields"] = [item for item in data["allowed_compact_fields"] if item != field]
        assert any("missing_required_compact_fields" in blocker or "suspected_live_decode_failure_stage_missing" in blocker for blocker in validate_packet(data))


def test_dry_run_does_not_execute_provider_or_bfcl_generate() -> None:
    plan = build_plan(PACKET_PATH)
    assert plan["blockers"] == []
    assert plan["provider_request_executed"] is False
    assert plan["live_shape_capture_executed"] is False
    assert plan["bfcl_generate_executed"] is False
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False


def test_dry_run_includes_required_compact_field_schema() -> None:
    plan = build_plan(PACKET_PATH)
    assert plan["compact_fields"] == REQUIRED_COMPACT_FIELDS
    assert "bfcl_parse_exception_class" in plan["compact_fields"]
    assert "bfcl_decode_exception_class" in plan["compact_fields"]
    assert "suspected_live_decode_failure_stage" in plan["compact_fields"]


def test_execute_mode_pending_fails_closed_without_execution() -> None:
    summary = execute_live_shape_capture(PACKET_PATH)
    assert "live_decode_exception_shape_capture_packet_not_approved" in summary["blockers"]
    assert summary["provider_request_executed"] is False
    assert summary["bfcl_generate_executed"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False


def test_route_fallback_openrouter_rejected() -> None:
    for key, value in (("route_model", "gpt-5.2"), ("gpt_4o_fallback_allowed", True), ("openrouter_allowed", True), ("gpt_5_2_active", True)):
        data = copy.deepcopy(_packet())
        data[key] = value
        blockers = validate_packet(data)
        assert blockers
