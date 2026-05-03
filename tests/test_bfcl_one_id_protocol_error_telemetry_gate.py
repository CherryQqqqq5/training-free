from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_one_id_protocol_error_telemetry_gate import (
    REQUIRED_COMPACT_FIELDS,
    SIGNED_ID,
    check,
    validate_packet,
)
from scripts.run_bfcl_one_id_protocol_error_telemetry import build_plan, execute_one_id_protocol_error_telemetry

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_protocol_error_telemetry_gate_packet.json")


def _packet() -> dict:
    return json.loads(PACKET.read_text(encoding="utf-8"))


def test_pending_packet_passes_fail_closed_gate() -> None:
    summary = check(PACKET)
    assert summary["bfcl_one_id_protocol_error_telemetry_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["provider_request_authorized"] is False
    assert summary["live_protocol_error_telemetry_authorized"] is False
    assert summary["bfcl_generate_authorized"] is False
    assert summary["signed_run_ids"] == [SIGNED_ID]
    assert summary["compact_field_count"] == len(REQUIRED_COMPACT_FIELDS)


def test_rejects_pending_authorized_true() -> None:
    data = _packet()
    data["authorized"] = True
    assert any("authorized_not_false" in blocker for blocker in validate_packet(data))


def test_rejects_wrong_or_multiple_ids() -> None:
    for ids in (["web_search_base_0"], [SIGNED_ID, "web_search_base_0"], []):
        data = _packet()
        data["signed_run_ids"] = list(ids)
        data["max_run_ids"] = len(ids)
        assert any("signed_run_ids_invalid" in blocker or "max_run_ids_invalid" in blocker for blocker in validate_packet(data))


def test_rejects_evaluate_scorer_full_baseline_flags() -> None:
    for key in ("bfcl_smoke_authorized", "bfcl_evaluate_authorized", "scorer_authorized", "full_baseline_authorized"):
        data = _packet()
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_rejects_candidate_performance_flags() -> None:
    for key in (
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
    ):
        data = _packet()
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_rejects_raw_fields_endpoints_secrets() -> None:
    data = _packet()
    data["allowed_compact_fields"] = list(REQUIRED_COMPACT_FIELDS) + ["raw_" + "provider_response_body"]
    assert any("forbidden_compact_field" in blocker or "extra_compact_fields" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["notes"] = "api " + "key " + "value"
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["notes"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))


def test_rejects_route_fallback_openrouter() -> None:
    for key, value in (("route_model", "gpt-5.2"), ("gpt_4o_fallback_allowed", True), ("openrouter_allowed", True), ("gpt_5_2_active", True)):
        data = copy.deepcopy(_packet())
        data[key] = value
        assert validate_packet(data)


def test_rejects_missing_protocol_error_stage_schema() -> None:
    data = _packet()
    data["allowed_compact_fields"] = [field for field in data["allowed_compact_fields"] if field != "suspected_protocol_error_stage"]
    assert any("suspected_protocol_error_stage_missing" in blocker or "missing_required_compact_fields" in blocker for blocker in validate_packet(data))


def test_dry_run_does_not_read_endpoint_key_or_execute_provider_or_bfcl() -> None:
    plan = build_plan(PACKET)
    assert plan["blockers"] == []
    assert plan["planned_run_ids"] == [SIGNED_ID]
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["provider_request_executed"] is False
    assert plan["live_protocol_error_telemetry_executed"] is False
    assert plan["bfcl_generate_executed"] is False
    assert plan["bfcl_smoke_executed"] is False
    assert plan["bfcl_evaluate_executed"] is False
    assert plan["scorer_executed"] is False
    assert plan["performance_evidence"] is False
    assert plan["compact_fields"] == REQUIRED_COMPACT_FIELDS


def test_pending_execute_fails_closed_without_endpoint_key_or_execution(tmp_path: Path) -> None:
    summary = execute_one_id_protocol_error_telemetry(PACKET, tmp_path / "protocol.json")
    assert "one_id_protocol_error_telemetry_packet_not_approved" in summary["blockers"]
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
    assert summary["provider_request_executed"] is False
    assert summary["bfcl_generate_executed"] is False
    assert not (tmp_path / "protocol.json").exists()
