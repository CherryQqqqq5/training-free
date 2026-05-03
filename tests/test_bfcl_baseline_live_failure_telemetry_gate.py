from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_baseline_live_failure_telemetry_gate import (
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    check,
    validate_packet,
)
from scripts.run_bfcl_baseline_live_failure_telemetry import build_plan, execute_live_failure_telemetry


def _packet() -> dict:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def test_committed_pending_packet_passes_fail_closed_gate() -> None:
    summary = check(DEFAULT_PACKET)
    assert summary["bfcl_baseline_live_failure_telemetry_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["authorized"] is False
    assert summary["live_failure_telemetry_authorized"] is False
    assert summary["route_profile"] == "novacode"
    assert summary["route_model"] == "gpt-4.1"
    assert summary["compact_field_count"] == len(REQUIRED_COMPACT_FIELDS)
    assert summary["performance_evidence"] is False


def test_rejects_pending_packet_with_execution_flags_true() -> None:
    for key in (
        "authorized",
        "provider_call_authorized",
        "live_failure_telemetry_authorized",
        "bfcl_generate_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
    ):
        data = _packet()
        data[key] = True
        blockers = validate_packet(data)
        assert any(key in blocker for blocker in blockers)


def test_rejects_candidate_and_performance_flags() -> None:
    for key in (
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
        "scorer_feedback_used",
    ):
        data = _packet()
        data[key] = True
        blockers = validate_packet(data)
        assert any(key in blocker for blocker in blockers)


def test_rejects_route_fallback_openrouter_and_active_gpt52() -> None:
    for key, value in (
        ("route_profile", "openrouter"),
        ("route_model", "gpt-5.2"),
        ("fallback_allowed", True),
        ("gpt_4o_fallback_allowed", True),
        ("openrouter_allowed", True),
        ("gpt_5_2_active", True),
    ):
        data = copy.deepcopy(_packet())
        data[key] = value
        assert validate_packet(data)


def test_rejects_missing_or_extra_compact_fields() -> None:
    data = _packet()
    data["allowed_compact_fields"] = [field for field in REQUIRED_COMPACT_FIELDS if field != "failed_stage"]
    assert any("missing_required_compact_fields" in blocker or "stage_fields_missing" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["allowed_compact_fields"] = list(REQUIRED_COMPACT_FIELDS) + ["raw_logs"]
    assert any("extra_compact_fields" in blocker or "forbidden_compact_field" in blocker for blocker in validate_packet(data))


def test_rejects_raw_secret_content() -> None:
    data = _packet()
    data["raw_log_value"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["note"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))


def test_rejects_missing_stop_gates_and_one_attempt_policy() -> None:
    data = _packet()
    data["future_stop_gates"] = []
    assert any("future_stop_gates_missing" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["one_attempt_only"] = False
    assert any("one_attempt_only" in blocker for blocker in validate_packet(data))


def test_dry_run_does_not_read_env_or_execute_baseline() -> None:
    plan = build_plan(DEFAULT_PACKET)
    assert plan["blockers"] == []
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["baseline_command_executed"] is False
    assert plan["provider_call_started"] is False
    assert plan["bfcl_generate_started"] is False
    assert plan["bfcl_generate_completed"] is False
    assert plan["bfcl_evaluate_started"] is False
    assert plan["bfcl_evaluate_completed"] is False
    assert plan["scorer_started"] is False
    assert plan["scorer_completed"] is False
    assert plan["performance_evidence"] is False


def test_dry_run_includes_required_compact_schema() -> None:
    plan = build_plan(DEFAULT_PACKET)
    assert plan["compact_fields"] == REQUIRED_COMPACT_FIELDS
    assert "failed_stage" in plan["compact_fields"]
    assert "stage_failure_class" in plan["compact_fields"]
    assert "stop_gate_triggered" in plan["compact_fields"]


def test_execute_mode_pending_fails_closed_without_env_or_baseline(tmp_path: Path) -> None:
    summary = execute_live_failure_telemetry(DEFAULT_PACKET, tmp_path / "telemetry.json")
    assert "baseline_live_failure_telemetry_packet_not_approved" in summary["blockers"]
    assert "baseline_live_failure_telemetry_execution_not_enabled_in_gate_preparation" in summary["blockers"]
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
    assert summary["baseline_command_executed"] is False
    assert summary["provider_call_started"] is False
    assert summary["bfcl_generate_started"] is False
