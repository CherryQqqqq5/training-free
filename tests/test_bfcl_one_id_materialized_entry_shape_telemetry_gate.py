from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_one_id_materialized_entry_shape_telemetry_gate import (
    REQUIRED_COMPACT_FIELDS,
    SIGNED_ID,
    check,
    validate_packet,
)
from scripts.run_bfcl_one_id_materialized_entry_shape_telemetry import (
    build_plan,
    execute_live_materialized_entry_shape_telemetry,
)

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_materialized_entry_shape_telemetry_gate_packet.json")


def _packet() -> dict:
    return json.loads(PACKET.read_text(encoding="utf-8"))


def _write_packet(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_pending_packet_passes_fail_closed_gate() -> None:
    summary = check(PACKET)
    assert summary["bfcl_one_id_materialized_entry_shape_telemetry_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["provider_request_authorized"] is False
    assert summary["live_materialized_entry_shape_telemetry_authorized"] is False
    assert summary["bfcl_generate_authorized"] is False
    assert summary["signed_run_ids"] == [SIGNED_ID]
    assert summary["compact_field_count"] == len(REQUIRED_COMPACT_FIELDS)


def test_rejects_authorized_or_execution_flags() -> None:
    for key in (
        "authorized",
        "provider_request_authorized",
        "live_materialized_entry_shape_telemetry_authorized",
        "bfcl_generate_authorized",
        "bfcl_smoke_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
    ):
        data = _packet()
        data[key] = True
        assert any(f"{key}_not_false" in blocker for blocker in validate_packet(data)), key


def test_rejects_wrong_or_multiple_ids() -> None:
    for ids in (["web_search_base_0"], [SIGNED_ID, "web_search_base_0"], []):
        data = _packet()
        data["signed_run_ids"] = list(ids)
        data["max_run_ids"] = len(ids)
        assert any("signed_run_ids_invalid" in blocker or "max_run_ids_invalid" in blocker for blocker in validate_packet(data))


def test_rejects_candidate_and_performance_flags() -> None:
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
        assert any(f"{key}_not_false" in blocker for blocker in validate_packet(data)), key


def test_rejects_route_fallback_openrouter() -> None:
    for key, value in (("route_model", "gpt-5.2"), ("gpt_4o_fallback_allowed", True), ("openrouter_allowed", True), ("gpt_5_2_active", True)):
        data = copy.deepcopy(_packet())
        data[key] = value
        assert validate_packet(data)


def test_rejects_raw_field_names_and_path_fields() -> None:
    data = _packet()
    data["allowed_compact_fields"] = list(REQUIRED_COMPACT_FIELDS) + ["raw_" + "result_content"]
    assert any("forbidden_compact_field" in blocker or "extra_compact_fields" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["allowed_compact_fields"] = list(REQUIRED_COMPACT_FIELDS) + ["result_path"]
    assert any("forbidden_compact_field" in blocker or "extra_compact_fields" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["notes"] = "api " + "key value"
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["notes"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))


def test_rejects_missing_materialized_entry_schema_fields() -> None:
    for field in (
        "materialized_entry_shape_label",
        "materialized_entry_has_grc_decoded_execution_output_shape",
        "materialized_marker_shape_label",
        "materialized_marker_decoded_output_count_nonzero",
        "materialized_result_field_shape_label",
        "materialized_inference_log_present",
        "materialized_protocol_error_indicator_present",
        "classifier_input_shape_label",
        "suspected_materialized_entry_shape_stage",
    ):
        data = _packet()
        data["allowed_compact_fields"] = [item for item in data["allowed_compact_fields"] if item != field]
        assert any("missing_required_compact_fields" in blocker or "materialized_entry_schema_field_missing" in blocker for blocker in validate_packet(data)), field


def test_rejects_source_stage_or_source_artifact_drift() -> None:
    data = _packet()
    data["source_stage"] = "protocol_status_after_nonempty_decode"
    assert any("source_stage_invalid" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["source_artifact"] = "outputs/artifacts/stage1_bfcl_acceptance/other.json"
    assert any("source_artifact_invalid" in blocker for blocker in validate_packet(data))


def test_dry_run_does_not_read_endpoint_key_or_execute_provider_or_bfcl() -> None:
    plan = build_plan(PACKET)
    assert plan["blockers"] == []
    assert plan["planned_run_ids"] == [SIGNED_ID]
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["provider_request_executed"] is False
    assert plan["live_materialized_entry_shape_telemetry_executed"] is False
    assert plan["bfcl_generate_executed"] is False
    assert plan["bfcl_smoke_executed"] is False
    assert plan["bfcl_evaluate_executed"] is False
    assert plan["scorer_executed"] is False
    assert plan["performance_evidence"] is False
    assert plan["compact_fields"] == REQUIRED_COMPACT_FIELDS


def test_pending_execute_fails_closed_without_endpoint_key_or_execution(tmp_path: Path) -> None:
    summary = execute_live_materialized_entry_shape_telemetry(PACKET, tmp_path / "materialized.json")
    assert "one_id_materialized_entry_shape_telemetry_packet_not_approved" in summary["blockers"]
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
    assert summary["provider_request_executed"] is False
    assert summary["bfcl_generate_executed"] is False
    assert not (tmp_path / "materialized.json").exists()


def test_approved_fixture_still_fails_not_configured_before_execution(tmp_path: Path) -> None:
    data = copy.deepcopy(_packet())
    data["approval_status"] = "approved"
    data["authorized"] = True
    data["provider_request_authorized"] = True
    data["live_materialized_entry_shape_telemetry_authorized"] = True
    data["bfcl_generate_authorized"] = True
    packet = _write_packet(tmp_path, data)
    summary = execute_live_materialized_entry_shape_telemetry(packet, tmp_path / "materialized.json")
    assert "one_id_materialized_entry_shape_telemetry_live_execution_not_configured" in summary["blockers"]
    assert summary["provider_request_executed"] is False
    assert summary["bfcl_generate_executed"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
