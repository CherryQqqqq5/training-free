from __future__ import annotations

import json
from pathlib import Path

from scripts.check_bfcl_live_shape_telemetry_artifact import check as check_artifact
from scripts.check_bfcl_live_shape_telemetry_packet import check as check_packet
from scripts.run_bfcl_live_shape_telemetry import build_plan, main as run_main


def _clean_artifact() -> dict[str, object]:
    record = {
        "run_id_label": "web_search_base_0",
        "endpoint_path_label": "responses",
        "request_shape_label": "responses_tools_single_function",
        "response_shape_label": "responses_function_call",
        "status_code_class": "2xx",
        "output_empty": False,
        "tool_call_present": True,
        "parser_decode_path_label": "bfcl_responses_fc_decode",
        "token_forwarding_label": "max_output_tokens_forwarded_as_chat_max_tokens",
        "tool_choice_forwarding_label": "function_object",
        "instructions_forwarding_label": "developer_message_prepended",
        "engine_content_empty_label": "content_empty_with_tool_call",
        "engine_coercion_label": "not_coerced",
        "raw_text_persisted": False,
        "raw_body_persisted": False,
        "raw_payload_persisted": False,
        "raw_header_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
    }
    return {
        "artifact_kind": "bfcl_live_shape_telemetry_compact",
        "active_profile": "novacode",
        "route_model": "gpt-4.1",
        "provider_request_executed": False,
        "bfcl_smoke_executed": False,
        "bfcl_scorer_executed": False,
        "candidate_runtime_activation_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "openrouter_allowed": False,
        "run_ids": ["web_search_base_0", "multi_turn_base_0"],
        "records": [record, {**record, "run_id_label": "multi_turn_base_0", "output_empty": True, "tool_call_present": False}],
    }


def test_packet_checker_passes_prepared_fail_closed_packet() -> None:
    summary = check_packet()
    assert summary["bfcl_live_shape_telemetry_packet_passed"] is True
    assert summary["planned_run_ids"] == ["web_search_base_0", "multi_turn_base_0"]
    assert summary["live_shape_telemetry_execution_authorized"] is False


def test_runner_dry_run_plan_reads_no_endpoint_or_key_and_calls_no_provider() -> None:
    plan = build_plan()
    assert plan["provider_request_executed"] is False
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["bfcl_smoke_executed"] is False
    assert plan["planned_run_id_count"] == 2


def test_runner_execute_mode_fails_closed_without_approval() -> None:
    assert run_main(["--execute-telemetry", "--compact", "--strict"]) == 1


def test_artifact_checker_accepts_clean_mock_artifact(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.json"
    path.write_text(json.dumps(_clean_artifact(), indent=2), encoding="utf-8")
    summary = check_artifact(path)
    assert summary["bfcl_live_shape_telemetry_artifact_passed"] is True


def test_artifact_checker_rejects_raw_and_secret_literals(tmp_path: Path) -> None:
    data = _clean_artifact()
    data["records"][0]["raw_payload_persisted"] = True
    data["records"][0]["response_shape_label"] = "https://example.invalid/raw-prompt"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    summary = check_artifact(path)
    assert summary["bfcl_live_shape_telemetry_artifact_passed"] is False
    assert summary["blockers"]


def test_artifact_checker_rejects_route_drift_and_too_many_ids(tmp_path: Path) -> None:
    data = _clean_artifact()
    data["route_model"] = "gpt-4o"
    data["gpt_4o_fallback_allowed"] = True
    data["run_ids"] = ["web_search_base_0", "multi_turn_base_0", "extra"]
    path = tmp_path / "bad_route.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    summary = check_artifact(path)
    assert summary["bfcl_live_shape_telemetry_artifact_passed"] is False
    assert any("route" in blocker or "too_many" in blocker for blocker in summary["blockers"])
