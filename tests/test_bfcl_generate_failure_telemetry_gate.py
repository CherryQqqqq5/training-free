from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_generate_failure_telemetry_gate import (
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    check,
    validate_packet,
)
from scripts.run_bfcl_generate_failure_telemetry import build_plan, execute_generate_failure_telemetry


def _packet() -> dict:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _pending_packet(tmp_path: Path) -> Path:
    data = _packet()
    data["approval_status"] = "pending"
    for key in (
        "authorized",
        "provider_request_authorized",
        "bfcl_generate_authorized",
        "bfcl_smoke_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
    ):
        data[key] = False
    path = tmp_path / "pending_generate_failure_telemetry_packet.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_committed_pending_packet_passes_fail_closed_gate() -> None:
    summary = check(DEFAULT_PACKET)
    assert summary["bfcl_generate_failure_telemetry_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["authorized"] is False
    assert summary["provider_request_authorized"] is False
    assert summary["bfcl_generate_authorized"] is False
    assert summary["route_profile"] == "novacode"
    assert summary["route_model"] == "gpt-4.1"
    assert summary["compact_field_count"] == len(REQUIRED_COMPACT_FIELDS)
    assert summary["performance_evidence"] is False


def test_rejects_pending_packet_with_authorized_true(tmp_path: Path) -> None:
    base = json.loads(_pending_packet(tmp_path).read_text(encoding="utf-8"))
    data = copy.deepcopy(base)
    data["authorized"] = True
    blockers = validate_packet(data)
    assert any("authorized_not_false" in blocker for blocker in blockers)


def test_rejects_provider_generate_evaluate_scorer_full_baseline_flags(tmp_path: Path) -> None:
    base = json.loads(_pending_packet(tmp_path).read_text(encoding="utf-8"))
    for key in (
        "provider_request_authorized",
        "bfcl_generate_authorized",
        "bfcl_smoke_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
    ):
        data = copy.deepcopy(base)
        data[key] = True
        blockers = validate_packet(data)
        assert any(key in blocker for blocker in blockers)


def test_rejects_candidate_and_performance_claim_flags(tmp_path: Path) -> None:
    base = json.loads(_pending_packet(tmp_path).read_text(encoding="utf-8"))
    for key in (
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
        "scorer_feedback_used",
    ):
        data = copy.deepcopy(base)
        data[key] = True
        blockers = validate_packet(data)
        assert any(key in blocker for blocker in blockers)


def test_rejects_route_fallback_openrouter_and_active_gpt52() -> None:
    for key, value in (
        ("route_profile", "other"),
        ("route_model", "gpt-5.2"),
        ("fallback_allowed", True),
        ("gpt_4o_fallback_allowed", True),
        ("openrouter_allowed", True),
        ("gpt_5_2_active", True),
    ):
        data = _packet()
        data[key] = value
        assert validate_packet(data)


def test_rejects_raw_field_names_and_endpoint_key_literal() -> None:
    data = _packet()
    data["allowed_compact_fields"] = list(REQUIRED_COMPACT_FIELDS) + ["raw_prompt"]
    assert any("extra_compact_fields" in blocker or "forbidden_compact_field" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["endpoint_value"] = "shape_only"
    assert any("forbidden_key" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["note"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))


def test_rejects_missing_required_compact_fields() -> None:
    data = _packet()
    data["allowed_compact_fields"] = [field for field in REQUIRED_COMPACT_FIELDS if field != "suspected_generate_failure_stage"]
    blockers = validate_packet(data)
    assert any("missing_required_compact_fields" in blocker for blocker in blockers)
    assert any("required_generate_stage_field_missing" in blocker for blocker in blockers)


def test_dry_run_does_not_source_env_read_secrets_or_execute_paths() -> None:
    plan = build_plan(DEFAULT_PACKET)
    assert plan["blockers"] == []
    assert plan["env_profile_sourced"] is False
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["baseline_command_executed"] is False
    assert plan["generate_stage_entered"] is False
    assert plan["provider_call_started"] is False
    assert plan["bfcl_generate_executed"] is False
    assert plan["bfcl_smoke_executed"] is False
    assert plan["bfcl_evaluate_executed"] is False
    assert plan["scorer_executed"] is False
    assert plan["full_baseline_executed"] is False
    assert plan["performance_evidence"] is False


def test_dry_run_includes_required_compact_field_schema() -> None:
    plan = build_plan(DEFAULT_PACKET)
    assert plan["compact_fields"] == REQUIRED_COMPACT_FIELDS
    assert "generate_exact_exit_code" in plan["compact_fields"]
    assert "bfcl_cli_exception_class" in plan["compact_fields"]
    assert "suspected_generate_failure_stage" in plan["compact_fields"]


def test_execute_with_pending_packet_fails_closed_before_env_provider_or_bfcl(tmp_path: Path) -> None:
    pending = _pending_packet(tmp_path)
    summary = execute_generate_failure_telemetry(pending, tmp_path / "telemetry.json")
    assert "generate_failure_telemetry_packet_not_approved" in summary["blockers"]
    assert summary["env_profile_sourced"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
    assert summary["baseline_command_executed"] is False
    assert summary["generate_stage_entered"] is False
    assert summary["provider_call_started"] is False
    assert summary["bfcl_generate_executed"] is False
    assert summary["bfcl_evaluate_executed"] is False
    assert summary["scorer_executed"] is False


def test_execute_with_pending_packet_rejects_preexisting_output_before_any_execution(tmp_path: Path) -> None:
    pending = _pending_packet(tmp_path)
    output = tmp_path / "telemetry.json"
    output.write_text("{}", encoding="utf-8")
    summary = execute_generate_failure_telemetry(pending, output)
    assert "output_artifact_exists" in summary["blockers"]
    assert summary["baseline_command_executed"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
