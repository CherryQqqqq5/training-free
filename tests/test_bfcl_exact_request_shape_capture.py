from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.build_bfcl_exact_request_shape_capture import build_report
from scripts.check_bfcl_exact_request_shape_capture import validate_artifact, validate_packet


def test_capture_no_provider_no_smoke_no_scorer_flags() -> None:
    report = build_report()
    assert report["provider_request_executed"] is False
    assert report["bfcl_smoke_executed"] is False
    assert report["scorer_executed"] is False
    assert report["full_baseline_executed"] is False
    assert report["candidate_runtime_activation_authorized"] is False
    assert report["performance_evidence"] is False
    assert validate_artifact(report) == []


def test_rejects_unsigned_ids() -> None:
    report = build_report()
    report["records"][0]["run_id_label"] = "unsigned_0"
    blockers = validate_artifact(report)
    assert any("unsigned_run_id" in blocker for blocker in blockers)


def test_rejects_raw_prompt_or_case_content() -> None:
    report = build_report()
    report["records"][0]["unsafe_label"] = "raw prompt and provider payload must fail"
    blockers = validate_artifact(report)
    assert any("forbidden" in blocker for blocker in blockers)


def test_records_tool_choice_presence_and_shape() -> None:
    report = build_report()
    for record in report["records"]:
        assert record["tool_choice_presence"] == "present"
        assert record["tool_choice_shape"] == "required_string"
    assert report["missing_tool_choice_confirmed"] is False


def test_records_token_fields_presence() -> None:
    report = build_report()
    for record in report["records"]:
        assert record["token_fields_presence"]["max_output_tokens"] == "present"
        assert record["token_fields_presence"]["max_tokens"] == "missing"
    assert report["missing_token_limit_confirmed"] is False


def test_records_multiturn_history_shape() -> None:
    report = build_report()
    by_id = {record["run_id_label"]: record for record in report["records"]}
    multi = by_id["multi_turn_base_0"]
    assert multi["input_or_messages_shape"]["message_count_bucket"] == "one"
    assert multi["multiturn_history_present"] is False
    assert multi["suspected_exact_request_gap"] == "exact_request_tool_choice_required_for_multi_tool_not_telemetry_function_object"


def test_records_proxy_invocation_mode() -> None:
    report = build_report()
    for record in report["records"]:
        assert record["api_path_label"] == "responses"
        assert record["proxy_invocation_mode_label"] == "bfcl_runner_to_local_grc_proxy_v1_responses_no_provider_capture"
        assert record["handler_class_label"] == "OpenAIResponsesHandler"


def test_suspected_exact_request_gap_required() -> None:
    report = build_report()
    assert report["suspected_exact_request_gap"]
    bad = copy.deepcopy(report)
    bad["suspected_exact_request_gap"] = ""
    blockers = validate_artifact(bad)
    assert "artifact_suspected_exact_request_gap_missing" in blockers


def test_packet_fail_closed() -> None:
    packet = json.loads(Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_request_shape_capture_packet.json").read_text())
    assert validate_packet(packet) == []
    packet["provider_request_authorized"] = True
    blockers = validate_packet(packet)
    assert any("provider_request_authorized" in blocker for blocker in blockers)
