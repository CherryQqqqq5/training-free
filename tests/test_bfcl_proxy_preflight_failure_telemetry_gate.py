from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_proxy_preflight_failure_telemetry_gate import (
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    check,
    validate_packet,
)
import scripts.run_bfcl_proxy_preflight_failure_telemetry as runner

build_plan = runner.build_plan
execute_proxy_preflight_telemetry = runner.execute_proxy_preflight_telemetry


def _packet() -> dict:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _pending_packet(tmp_path: Path) -> Path:
    data = _packet()
    data["approval_status"] = "pending"
    for key in (
        "authorized",
        "provider_request_authorized",
        "proxy_live_preflight_authorized",
        "bfcl_generate_authorized",
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
    path = tmp_path / "pending_proxy_preflight_telemetry_packet.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _approved_packet(tmp_path: Path) -> Path:
    data = _packet()
    data["approval_status"] = "approved"
    data["authorized"] = True
    data["proxy_live_preflight_authorized"] = True
    for key in (
        "provider_request_authorized",
        "bfcl_generate_authorized",
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
    path = tmp_path / "approved_proxy_preflight_telemetry_packet.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_committed_packet_passes_pending_fail_closed() -> None:
    summary = check(DEFAULT_PACKET)
    assert summary["bfcl_proxy_preflight_failure_telemetry_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["authorized"] is False
    assert summary["proxy_live_preflight_authorized"] is False
    assert summary["provider_request_authorized"] is False
    assert summary["bfcl_generate_authorized"] is False
    assert summary["compact_field_count"] == len(REQUIRED_COMPACT_FIELDS)
    assert summary["performance_evidence"] is False


def test_pending_packet_rejects_authorized_true(tmp_path: Path) -> None:
    data = json.loads(_pending_packet(tmp_path).read_text(encoding="utf-8"))
    data["authorized"] = True
    blockers = validate_packet(data)
    assert any("authorized_not_false" in blocker for blocker in blockers)
    data = json.loads(_pending_packet(tmp_path).read_text(encoding="utf-8"))
    data["proxy_live_preflight_authorized"] = True
    blockers = validate_packet(data)
    assert any("proxy_live_preflight_authorized_not_false" in blocker for blocker in blockers)


def test_approved_packet_lifecycle_allows_only_proxy_preflight(tmp_path: Path) -> None:
    summary = check(_approved_packet(tmp_path))
    assert summary["bfcl_proxy_preflight_failure_telemetry_gate_passed"] is True
    assert summary["authorized"] is True
    assert summary["proxy_live_preflight_authorized"] is True
    assert summary["provider_request_authorized"] is False
    assert summary["bfcl_generate_authorized"] is False


def test_rejects_provider_bfcl_scorer_baseline_flags(tmp_path: Path) -> None:
    base = json.loads(_pending_packet(tmp_path).read_text(encoding="utf-8"))
    for key in (
        "provider_request_authorized",
        "bfcl_generate_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
    ):
        data = copy.deepcopy(base)
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_rejects_candidate_and_performance_flags(tmp_path: Path) -> None:
    base = json.loads(_pending_packet(tmp_path).read_text(encoding="utf-8"))
    for key in (
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
    ):
        data = copy.deepcopy(base)
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_rejects_wrong_route_missing_fields_and_raw_material() -> None:
    data = _packet()
    data["route_model"] = "gpt-5.2"
    assert any("route" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["allowed_compact_fields"] = [field for field in REQUIRED_COMPACT_FIELDS if field != "provider_call_started"]
    blockers = validate_packet(data)
    assert any("missing_required_compact_fields" in blocker for blocker in blockers)
    assert any("required_preflight_field_missing" in blocker for blocker in blockers)
    data = _packet()
    data["allowed_compact_fields"] = list(REQUIRED_COMPACT_FIELDS) + ["raw_prompt"]
    blockers = validate_packet(data)
    assert any("extra_compact_fields" in blocker or "forbidden_compact_field" in blocker for blocker in blockers)
    data = _packet()
    data["endpoint_value"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["note"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))


def test_dry_run_does_not_source_env_read_secrets_or_execute_paths() -> None:
    plan = build_plan(DEFAULT_PACKET)
    assert plan["blockers"] == []
    assert plan["env_profile_sourced"] is False
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["preflight_command_executed"] is False
    assert plan["live_preflight_executed"] is False
    assert plan["provider_call_started"] is False
    assert plan["bfcl_generate_started"] is False
    assert plan["bfcl_evaluate_started"] is False
    assert plan["scorer_started"] is False
    assert plan["bfcl_generate_executed"] is False
    assert plan["bfcl_evaluate_executed"] is False
    assert plan["scorer_executed"] is False
    assert plan["full_baseline_executed"] is False
    assert plan["performance_evidence"] is False


def test_dry_run_includes_required_compact_schema() -> None:
    plan = build_plan(DEFAULT_PACKET)
    assert plan["compact_fields"] == REQUIRED_COMPACT_FIELDS
    assert "preflight_exact_exit_code_class" in plan["compact_fields"]
    assert "provider_call_started" in plan["compact_fields"]
    assert "suspected_proxy_preflight_failure_stage" in plan["compact_fields"]


def test_execute_with_pending_packet_fails_closed_before_env_provider_preflight_or_bfcl(tmp_path: Path) -> None:
    pending = _pending_packet(tmp_path)
    summary = execute_proxy_preflight_telemetry(pending, tmp_path / "telemetry.json")
    assert "proxy_preflight_telemetry_packet_not_approved" in summary["blockers"]
    assert summary["env_profile_sourced"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
    assert summary["preflight_command_executed"] is False
    assert summary["live_preflight_executed"] is False
    assert summary["provider_call_started"] is False
    assert summary["bfcl_generate_started"] is False
    assert summary["bfcl_evaluate_started"] is False
    assert summary["scorer_started"] is False
    assert summary["bfcl_generate_executed"] is False
    assert summary["bfcl_evaluate_executed"] is False
    assert summary["scorer_executed"] is False


def test_execute_with_pending_packet_rejects_preexisting_output_before_any_execution(tmp_path: Path) -> None:
    pending = _pending_packet(tmp_path)
    output = tmp_path / "telemetry.json"
    output.write_text("{}", encoding="utf-8")
    summary = execute_proxy_preflight_telemetry(pending, output)
    assert "output_artifact_exists" in summary["blockers"]
    assert summary["preflight_command_executed"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
