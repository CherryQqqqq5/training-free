from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.build_bfcl_runner_request_shape_delta import build_report, detect_suspected_gaps
from scripts.check_bfcl_runner_request_shape_delta import validate_artifact, validate_packet


def test_delta_gate_no_provider_no_smoke_no_scorer_flags() -> None:
    report = build_report()
    assert report["provider_request_executed"] is False
    assert report["bfcl_smoke_executed"] is False
    assert report["scorer_executed"] is False
    assert report["full_baseline_executed"] is False
    assert report["candidate_runtime_activation_authorized"] is False
    assert report["performance_evidence"] is False
    assert validate_artifact(report) == []


def test_shape_artifact_rejects_raw_prompt_or_case_markers() -> None:
    report = build_report()
    report["telemetry_shape"]["unsafe"] = "raw prompt from case_id should never appear"
    blockers = validate_artifact(report)
    assert any("forbidden" in blocker for blocker in blockers)


def test_token_field_delta_detected() -> None:
    report = build_report()
    assert "bfcl_handler_missing_token_limit_vs_telemetry_max_output_tokens" in report["shape_deltas"]
    telemetry = copy.deepcopy(report["telemetry_shape"])
    runner = copy.deepcopy(report["bfcl_runner_shape"])
    runner["token_fields"]["max_output_tokens"] = telemetry["token_fields"]["max_output_tokens"]
    gaps = detect_suspected_gaps(telemetry, runner)
    assert "bfcl_handler_missing_token_limit_vs_telemetry_max_output_tokens" not in gaps


def test_stream_timeout_delta_detected() -> None:
    report = build_report()
    runner = report["bfcl_runner_shape"]
    telemetry = report["telemetry_shape"]
    assert runner["stream_flag"] != telemetry["stream_flag"]
    assert runner["timeout_bucket"] != telemetry["timeout_bucket"]


def test_handler_path_delta_detected() -> None:
    report = build_report()
    runner = report["bfcl_runner_shape"]
    telemetry = report["telemetry_shape"]
    assert runner["handler_class_label"] == "OpenAIResponsesHandler"
    assert runner["request_path_label"] != telemetry["request_path_label"]
    assert "bfcl_runner_proxy_invocation_mode_differs_from_telemetry_client_factory" in report["shape_deltas"]


def test_tool_choice_shape_delta_detected() -> None:
    report = build_report()
    assert report["bfcl_runner_shape"]["tool_choice_shape"] == "absent"
    assert report["telemetry_shape"]["tool_choice_shape"] == "function_object"
    assert "bfcl_handler_missing_tool_choice_vs_telemetry_function_object" in report["shape_deltas"]


def test_multiturn_history_shape_delta_detected() -> None:
    report = build_report()
    runner = report["bfcl_runner_shape"]
    assert runner["multi_turn_category_count"] >= 1
    assert runner["function_call_history_count"] == "possible_nonzero_for_multiturn"
    assert report["telemetry_shape"]["function_call_history_count"] == 0
    assert "bfcl_multiturn_history_shape_not_exercised_by_synthetic_telemetry" in report["shape_deltas"]


def test_runtime_text_to_empty_policy_recorded() -> None:
    report = build_report()
    policy = report["bfcl_runner_shape"]["runtime_config_policy_flags"]
    assert policy["text_to_empty_coercion_enabled"] is True
    assert policy["text_to_empty_coercion_kind_count"] >= 1
    assert policy["scorer_feedback_enabled"] is False


def test_suspected_gap_required() -> None:
    report = build_report()
    assert report["suspected_gap"]
    bad = copy.deepcopy(report)
    bad["suspected_gap"] = ""
    blockers = validate_artifact(bad)
    assert "artifact_suspected_gap_missing" in blockers


def test_packet_fail_closed_flags() -> None:
    packet = json.loads(Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_runner_request_shape_delta_packet.json").read_text())
    assert validate_packet(packet) == []
    packet["provider_request_authorized"] = True
    blockers = validate_packet(packet)
    assert any("provider_request_authorized" in blocker for blocker in blockers)
