from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_one_id_live_shape_telemetry_artifact import check as check_artifact, validate as validate_artifact
from scripts.check_bfcl_one_id_live_shape_telemetry_gate import ALLOWED_TELEMETRY_FIELDS, check, validate_packet
from scripts.run_bfcl_one_id_live_shape_telemetry import build_plan, execute_live_telemetry, main as runner_main

AFTER_PATCH_PACKET_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_after_tool_choice_patch_packet.json")
AFTER_PATCH_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_after_tool_choice_patch_compact.json")
PREVIOUS_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_compact.json")


def _packet() -> dict[str, object]:
    return json.loads(Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_gate_packet.json").read_text(encoding="utf-8"))


def _approved_packet_path(tmp_path: Path) -> Path:
    packet = _packet()
    packet["approval_status"] = "approved"
    packet["authorized"] = True
    packet["provider_request_authorized"] = True
    packet["bfcl_generate_authorized"] = True
    packet["live_shape_telemetry_authorized"] = True
    path = tmp_path / "approved_packet.json"
    path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _pending_packet_path(tmp_path: Path) -> Path:
    packet = _packet()
    packet["approval_status"] = "pending"
    packet["authorized"] = False
    packet["provider_request_authorized"] = False
    packet["bfcl_generate_authorized"] = False
    packet["live_shape_telemetry_authorized"] = False
    path = tmp_path / "pending_packet.json"
    path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    return path

def _assert_rejected(packet: dict[str, object], expected: str) -> None:
    blockers = validate_packet(packet)
    assert any(expected in blocker for blocker in blockers), blockers


def _record(stage: str) -> dict[str, object]:
    record: dict[str, object] = {
        "run_id": "web_search_base_0",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "local_proxy_endpoint_path_label": "bfcl_generate_local_proxy_responses_v1",
        "bfcl_handler_class_label": "openai_responses_handler",
        "bfcl_api_path_label": "responses",
        "request_shape_hash": "shape_hash_fixture",
        "request_message_count_bucket": "one_to_three",
        "request_has_instructions": True,
        "request_has_tools": True,
        "request_tool_count": 3,
        "request_tool_choice_shape": "required_string",
        "request_token_field_shape": "max_output_tokens",
        "provider_status_class": "2xx",
        "provider_response_empty_bool": False,
        "provider_response_has_choices": True,
        "provider_response_has_message": True,
        "provider_response_has_tool_calls": True,
        "provider_response_has_nonempty_text": False,
        "engine_apply_response_called": True,
        "engine_final_has_tool_calls": True,
        "engine_final_has_nonempty_text": False,
        "engine_final_content_empty": True,
        "engine_coerced_nonempty_text_to_empty": False,
        "proxy_responses_output_has_function_call": True,
        "proxy_responses_output_has_nonempty_text": False,
        "bfcl_parse_called": True,
        "bfcl_parse_model_response_empty": False,
        "bfcl_decode_execute_called": True,
        "bfcl_decode_execute_nonempty": True,
        "result_file_written": True,
        "result_file_contains_nonempty_shape": True,
        "compact_classifier_status": "generated",
        "protocol_exception_observed": False,
        "protocol_exception_converted_to_empty_model_response": False,
        "classifier_false_empty_for_nonempty_result": False,
        "suspected_live_failure_stage": stage,
    }
    if stage == "provider_true_empty":
        record.update(
            provider_response_empty_bool=True,
            provider_response_has_choices=True,
            provider_response_has_message=True,
            provider_response_has_tool_calls=False,
            engine_apply_response_called=False,
            engine_final_has_tool_calls=False,
            proxy_responses_output_has_function_call=False,
            bfcl_parse_called=False,
            bfcl_decode_execute_called=False,
            bfcl_decode_execute_nonempty=False,
            result_file_written=False,
            result_file_contains_nonempty_shape=False,
            compact_classifier_status="empty_model_response",
        )
    elif stage == "provider_protocol_error":
        record.update(
            provider_status_class="5xx",
            provider_response_empty_bool=False,
            provider_response_has_choices=False,
            provider_response_has_message=False,
            provider_response_has_tool_calls=False,
            protocol_exception_observed=True,
            engine_apply_response_called=False,
            engine_final_has_tool_calls=False,
            proxy_responses_output_has_function_call=False,
            bfcl_parse_called=False,
            bfcl_decode_execute_called=False,
            bfcl_decode_execute_nonempty=False,
            result_file_written=False,
            result_file_contains_nonempty_shape=False,
            compact_classifier_status="provider_protocol_error",
        )
    elif stage == "provider_text_no_tool":
        record.update(
            provider_response_has_tool_calls=False,
            provider_response_has_nonempty_text=True,
            engine_final_has_tool_calls=False,
            engine_final_has_nonempty_text=True,
            engine_final_content_empty=False,
            proxy_responses_output_has_function_call=False,
            proxy_responses_output_has_nonempty_text=True,
            bfcl_decode_execute_nonempty=False,
            result_file_contains_nonempty_shape=True,
            compact_classifier_status="no_tool_text",
        )
    elif stage == "proxy_engine_tool_loss":
        record.update(engine_final_has_tool_calls=False, proxy_responses_output_has_function_call=False, bfcl_decode_execute_nonempty=False, result_file_contains_nonempty_shape=False, compact_classifier_status="empty_model_response")
    elif stage == "engine_text_coercion":
        record.update(provider_response_has_tool_calls=False, provider_response_has_nonempty_text=True, engine_final_has_tool_calls=False, engine_final_content_empty=True, engine_coerced_nonempty_text_to_empty=True, proxy_responses_output_has_function_call=False, bfcl_decode_execute_nonempty=False, result_file_contains_nonempty_shape=False, compact_classifier_status="empty_model_response")
    elif stage == "responses_envelope_loss":
        record.update(proxy_responses_output_has_function_call=False, bfcl_decode_execute_nonempty=False, result_file_contains_nonempty_shape=False, compact_classifier_status="empty_model_response")
    elif stage == "bfcl_parse_decode_loss":
        record.update(bfcl_parse_model_response_empty=True, bfcl_decode_execute_nonempty=False, result_file_contains_nonempty_shape=False, compact_classifier_status="empty_model_response")
    elif stage == "materialization_classifier_loss":
        record.update(result_file_contains_nonempty_shape=False, classifier_false_empty_for_nonempty_result=True, compact_classifier_status="empty_model_response")
    elif stage == "protocol_exception":
        record.update(protocol_exception_observed=True, provider_status_class="protocol_exception", provider_response_has_choices=False, provider_response_has_message=False, provider_response_has_tool_calls=False, engine_apply_response_called=False, engine_final_has_tool_calls=False, proxy_responses_output_has_function_call=False, bfcl_parse_called=False, bfcl_decode_execute_called=False, bfcl_decode_execute_nonempty=False, result_file_written=False, result_file_contains_nonempty_shape=False, compact_classifier_status="protocol_exception")
    elif stage == "live_path_nonempty":
        pass
    else:
        raise ValueError(stage)
    return record


def _artifact(stage: str) -> dict[str, object]:
    return {
        "artifact_kind": "bfcl_one_id_live_shape_telemetry_compact",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "provider_request_executed": True,
        "bfcl_generate_executed": True,
        "bfcl_smoke_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "openrouter_allowed": False,
        "gpt_5_2_active": False,
        "run_ids": ["web_search_base_0"],
        "records": [_record(stage)],
    }


def test_approved_current_packet_passes() -> None:
    summary = check()
    assert summary["bfcl_one_id_live_shape_telemetry_gate_passed"] is True
    assert summary["approval_status"] == "approved"
    assert summary["signed_run_ids"] == ["web_search_base_0"]
    assert summary["provider_request_authorized"] is True
    assert summary["bfcl_generate_authorized"] is True
    assert summary["live_shape_telemetry_authorized"] is True

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
    packet["approval_status"] = "pending"
    packet["authorized"] = True
    packet["provider_request_authorized"] = True
    packet["bfcl_generate_authorized"] = True
    packet["live_shape_telemetry_authorized"] = True
    _assert_rejected(packet, "authorized_invalid_for_pending")
    _assert_rejected(packet, "provider_request_authorized_invalid_for_pending")
    _assert_rejected(packet, "bfcl_generate_authorized_invalid_for_pending")
    _assert_rejected(packet, "live_shape_telemetry_authorized_invalid_for_pending")

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


def test_execute_fails_closed_while_pending_without_env_read(tmp_path: Path) -> None:
    summary = execute_live_telemetry(packet_path=_pending_packet_path(tmp_path))
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
    assert "protocol_exception_observed" in plan["telemetry_fields"]
    assert "classifier_false_empty_for_nonempty_result" in plan["telemetry_fields"]
    assert "suspected_live_failure_stage" in plan["telemetry_fields"]


def test_approved_packet_would_allow_exactly_one_generate_only_telemetry_id() -> None:
    packet = _packet()
    packet["approval_status"] = "approved"
    packet["authorized"] = True
    packet["provider_request_authorized"] = True
    packet["bfcl_generate_authorized"] = True
    packet["live_shape_telemetry_authorized"] = True
    blockers = validate_packet(packet)
    assert blockers == []
    assert packet["signed_run_ids"] == ["web_search_base_0"]
    assert packet["bfcl_smoke_authorized"] is False
    assert packet["bfcl_evaluate_authorized"] is False
    assert packet["scorer_authorized"] is False


def test_fake_approved_packet_and_capture_produce_valid_compact_artifact(tmp_path: Path) -> None:
    packet_path = _approved_packet_path(tmp_path)
    out = tmp_path / "telemetry.json"

    def fake_capture(request: dict[str, object]) -> dict[str, object]:
        assert request["run_ids"] == ["web_search_base_0"]
        assert request["raw_persistence_authorized"] is False
        return _record("live_path_nonempty")

    summary = execute_live_telemetry(packet_path=packet_path, output_artifact=out, live_capture=fake_capture)
    assert summary["blockers"] == []
    assert summary["diagnostic_written"] is True
    assert check_artifact(out)["bfcl_one_id_live_shape_telemetry_artifact_passed"] is True


def test_artifact_checker_accepts_valid_compact_variants() -> None:
    for stage in (
        "provider_true_empty",
        "provider_protocol_error",
        "provider_text_no_tool",
        "proxy_engine_tool_loss",
        "engine_text_coercion",
        "responses_envelope_loss",
        "bfcl_parse_decode_loss",
        "materialization_classifier_loss",
        "protocol_exception",
        "live_path_nonempty",
    ):
        blockers = validate_artifact(_artifact(stage))
        assert blockers == [], (stage, blockers)


def test_http_4xx_5xx_trace_not_provider_true_empty() -> None:
    from scripts.bfcl_one_id_live_shape_telemetry_capture import (
        _derive_stage,
        _normalize_observed_record,
        _provider_observation_from_trace,
    )

    for status_code in (404, 500):
        record = _record("provider_true_empty")
        record.update(_provider_observation_from_trace({"status_code": status_code, "raw_response": {}}))
        normalized = _normalize_observed_record(record)
        assert normalized["provider_response_empty_bool"] is False
        assert normalized["protocol_exception_observed"] is True
        assert normalized["suspected_live_failure_stage"] == "provider_protocol_error"
        assert _derive_stage(normalized) == "provider_protocol_error"


def test_artifact_checker_rejects_non_2xx_provider_true_empty() -> None:
    data = _artifact("provider_true_empty")
    data["records"][0]["provider_status_class"] = "5xx"
    blockers = validate_artifact(data)
    assert any("provider_protocol_error_stage_mismatch" in blocker for blocker in blockers)


def test_valid_2xx_empty_response_can_be_provider_true_empty() -> None:
    data = _artifact("provider_true_empty")
    record = data["records"][0]
    assert record["provider_status_class"] == "2xx"
    assert record["provider_response_has_choices"] is True
    assert record["provider_response_has_message"] is True
    assert validate_artifact(data) == []


def test_protocol_exception_remains_protocol_exception_not_empty() -> None:
    from scripts.bfcl_one_id_live_shape_telemetry_capture import _normalize_observed_record, _provider_observation_from_trace

    record = _record("protocol_exception")
    record.update(_provider_observation_from_trace({"status_code": "protocol_exception", "raw_response": {}}))
    normalized = _normalize_observed_record(record)
    assert normalized["provider_response_empty_bool"] is False
    assert normalized["protocol_exception_observed"] is True
    assert normalized["suspected_live_failure_stage"] == "protocol_exception"
    data = _artifact("protocol_exception")
    data["records"][0].update(normalized)
    assert validate_artifact(data) == []


def test_artifact_checker_rejects_missing_protocol_exception_flags() -> None:
    data = _artifact("live_path_nonempty")
    del data["records"][0]["protocol_exception_observed"]
    blockers = validate_artifact(data)
    assert any("record_missing_fields" in blocker for blocker in blockers)


def test_artifact_checker_rejects_raw_fields_and_secret_literals() -> None:
    data = _artifact("live_path_nonempty")
    data["records"][0]["raw_provider_response_body"] = "redacted"
    data["records"][0]["request_shape_hash"] = "https" + "://example.invalid"
    blockers = validate_artifact(data)
    assert any("record_unknown_fields" in blocker or "forbidden_raw_or_secret_key" in blocker for blocker in blockers)
    assert any("endpoint_or_key_literal" in blocker for blocker in blockers)


def test_artifact_checker_rejects_multiple_or_wrong_ids() -> None:
    data = _artifact("live_path_nonempty")
    data["run_ids"] = ["web_search_base_0", "multi_turn_base_0"]
    data["records"][0]["run_id"] = "multi_turn_base_0"
    blockers = validate_artifact(data)
    assert any("run_ids_invalid" in blocker for blocker in blockers)
    assert any("record_run_id_invalid" in blocker for blocker in blockers)


def test_artifact_checker_rejects_scorer_candidate_performance_flags() -> None:
    for key in ("bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed", "candidate_runtime_activation_authorized", "performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready"):
        data = _artifact("live_path_nonempty")
        data[key] = True
        blockers = validate_artifact(data)
        assert any(f"{key}_not_false" in blocker for blocker in blockers), (key, blockers)


def test_artifact_checker_rejects_inconsistent_suspected_stage() -> None:
    data = _artifact("proxy_engine_tool_loss")
    data["records"][0]["suspected_live_failure_stage"] = "provider_true_empty"
    blockers = validate_artifact(data)
    assert any("proxy_engine_tool_loss_stage_mismatch" in blocker for blocker in blockers)


def test_artifact_checker_rejects_protocol_exception_converted_to_empty() -> None:
    data = _artifact("protocol_exception")
    data["records"][0]["protocol_exception_converted_to_empty_model_response"] = True
    blockers = validate_artifact(data)
    assert any("protocol_exception_converted_to_empty_forbidden" in blocker for blocker in blockers)


def test_signed_capture_factory_path_can_produce_valid_compact_artifact(tmp_path: Path) -> None:
    from scripts.bfcl_one_id_live_shape_telemetry_capture import build_signed_one_id_live_shape_capture

    packet_path = _approved_packet_path(tmp_path)
    out = tmp_path / "telemetry.json"

    def fake_executor(request: dict[str, object]) -> dict[str, object]:
        assert request["run_ids"] == ["web_search_base_0"]
        assert request["route_model"] == "gpt-4.1"
        return _record("live_path_nonempty")

    def factory(request: dict[str, object]):
        return build_signed_one_id_live_shape_capture(request, executor=fake_executor)

    summary = execute_live_telemetry(packet_path=packet_path, output_artifact=out, live_capture_factory=factory)
    assert summary["blockers"] == []
    assert summary["provider_request_executed"] is True
    assert summary["bfcl_generate_executed"] is True
    assert check_artifact(out)["bfcl_one_id_live_shape_telemetry_artifact_passed"] is True


def test_unsigned_capture_factory_cli_fails_before_secret_read() -> None:
    rc = runner_main(["--execute-live-telemetry", "--live-capture-factory", "tests.fake:build", "--compact", "--strict"])
    assert rc == 1


def test_signed_capture_factory_rejects_route_drift_extra_id_and_raw_flag() -> None:
    from scripts.bfcl_one_id_live_shape_telemetry_capture import build_signed_one_id_live_shape_capture

    base = {"run_ids": ["web_search_base_0"], "route_profile": "novacode", "route_model": "gpt-4.1", "generate_only": True, "raw_persistence_authorized": False}
    for update, expected in (
        ({"route_model": "gpt-5.2"}, "route_model_drift"),
        ({"run_ids": ["web_search_base_0", "multi_turn_base_0"]}, "run_ids_not_signed"),
        ({"raw_persistence_authorized": True}, "raw_persistence_not_false"),
    ):
        request = dict(base)
        request.update(update)
        try:
            build_signed_one_id_live_shape_capture(request, executor=lambda req: _record("live_path_nonempty"))
        except RuntimeError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("expected signed capture request rejection")


def test_execute_rejects_preexisting_output_before_capture_factory(tmp_path: Path) -> None:
    packet_path = _approved_packet_path(tmp_path)
    out = tmp_path / "telemetry.json"
    out.write_text("{}", encoding="utf-8")
    called = False

    def factory(request: dict[str, object]):
        nonlocal called
        called = True
        return lambda capture_request: _record("live_path_nonempty")

    summary = execute_live_telemetry(packet_path=packet_path, output_artifact=out, live_capture_factory=factory)
    assert summary["blockers"] == ["output_artifact_exists_without_clean_output"]
    assert called is False
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False


def test_signed_instrumented_capture_requires_stage_observations(tmp_path: Path) -> None:
    from scripts.bfcl_one_id_live_shape_telemetry_capture import build_signed_one_id_live_shape_capture

    packet_path = _approved_packet_path(tmp_path)

    def incomplete_executor(request: dict[str, object]) -> dict[str, object]:
        return {"run_id": "web_search_base_0"}

    def factory(request: dict[str, object]):
        return build_signed_one_id_live_shape_capture(request, executor=incomplete_executor)

    summary = execute_live_telemetry(packet_path=packet_path, output_artifact=tmp_path / "telemetry.json", live_capture_factory=factory)
    assert any(str(blocker).startswith("live_shape_stage_not_instrumented:") for blocker in summary["blockers"])
    assert summary["diagnostic_written"] is False


def test_empty_model_response_requires_observed_upstream_empty(tmp_path: Path) -> None:
    from scripts.bfcl_one_id_live_shape_telemetry_capture import build_signed_one_id_live_shape_capture

    packet_path = _approved_packet_path(tmp_path)

    def fake_executor(request: dict[str, object]) -> dict[str, object]:
        record = _record("provider_true_empty")
        record["provider_response_empty_bool"] = False
        return record

    def factory(request: dict[str, object]):
        return build_signed_one_id_live_shape_capture(request, executor=fake_executor)

    summary = execute_live_telemetry(packet_path=packet_path, output_artifact=tmp_path / "telemetry.json", live_capture_factory=factory)
    assert summary["blockers"] == ["live_shape_empty_model_response_without_observed_upstream_empty"]
    assert summary["diagnostic_written"] is False


def test_capture_temp_run_root_cleanup_on_success_and_failure(tmp_path: Path) -> None:
    from scripts.bfcl_one_id_live_shape_telemetry_capture import build_signed_one_id_live_shape_capture

    packet_path = _approved_packet_path(tmp_path)
    roots: list[Path] = []

    def success_executor(request: dict[str, object]) -> dict[str, object]:
        root = Path(str(request["run_root"]))
        roots.append(root)
        (root / "bfcl/result").mkdir(parents=True)
        (root / "proxy.log").write_text("compact-test-log", encoding="utf-8")
        return _record("live_path_nonempty")

    def success_factory(request: dict[str, object]):
        return build_signed_one_id_live_shape_capture(request, executor=success_executor)

    summary = execute_live_telemetry(packet_path=packet_path, output_artifact=tmp_path / "success.json", live_capture_factory=success_factory)
    assert summary["blockers"] == []
    assert roots and all(not root.exists() for root in roots)

    failure_roots: list[Path] = []

    def failure_executor(request: dict[str, object]) -> dict[str, object]:
        root = Path(str(request["run_root"]))
        failure_roots.append(root)
        (root / "traces").mkdir(parents=True)
        (root / "traces/trace.json").write_text("compact-test-trace", encoding="utf-8")
        raise RuntimeError("live_shape_stage_not_instrumented:provider_upstream_response")

    def failure_factory(request: dict[str, object]):
        return build_signed_one_id_live_shape_capture(request, executor=failure_executor)

    failed = execute_live_telemetry(packet_path=packet_path, output_artifact=tmp_path / "failure.json", live_capture_factory=failure_factory)
    assert failed["blockers"] == ["live_shape_stage_not_instrumented:provider_upstream_response"]
    assert failure_roots and all(not root.exists() for root in failure_roots)


def test_temporary_manifest_restores_or_removes(tmp_path: Path) -> None:
    from scripts.bfcl_one_id_live_shape_telemetry_capture import SIGNED_ID_MANIFEST, _temporary_one_id_manifest

    target = tmp_path / "test_case_ids_to_generate.json"
    with _temporary_one_id_manifest(target):
        assert json.loads(target.read_text(encoding="utf-8")) == SIGNED_ID_MANIFEST
    assert not target.exists()

    target.write_text('{"existing": ["id"]}\n', encoding="utf-8")
    with _temporary_one_id_manifest(target):
        assert json.loads(target.read_text(encoding="utf-8")) == SIGNED_ID_MANIFEST
    assert json.loads(target.read_text(encoding="utf-8")) == {"existing": ["id"]}


def _proxy_trace_tool_call() -> dict[str, object]:
    return {
        "request_endpoint": "/v1/responses",
        "request_original": {"instructions": "redacted", "input": [{"role": "user", "content": "redacted"}]},
        "request": {
            "messages": [{"role": "developer", "content": "redacted"}, {"role": "user", "content": "redacted"}],
            "tools": [{"type": "function", "function": {"name": "redacted", "parameters": {"type": "object"}}}],
            "tool_choice": "required",
            "max_tokens": 64,
        },
        "raw_response": {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "redacted", "arguments": "{}"}}],
                    }
                }
            ]
        },
        "final_chat_response": {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "redacted", "arguments": "{}"}}],
                    }
                }
            ]
        },
        "final_response": {
            "output": [{"type": "function_call", "id": "call_1", "call_id": "call_1", "name": "redacted", "arguments": "{}"}]
        },
        "validation": {"repair_kinds": []},
        "status_code": 200,
    }


def test_default_signed_capture_path_uses_stage_trace_and_result(monkeypatch, tmp_path: Path) -> None:
    import contextlib
    import subprocess
    import scripts.bfcl_one_id_live_shape_telemetry_capture as capture
    from scripts.bfcl_one_id_live_shape_telemetry_capture import build_signed_one_id_live_shape_capture

    packet_path = _approved_packet_path(tmp_path)
    roots: list[Path] = []
    trace_dirs: list[Path] = []

    class Proc:
        def terminate(self) -> None:
            pass

        def wait(self, timeout: int = 0) -> None:
            pass

        def kill(self) -> None:
            pass

    def fake_start_proxy(port: int, trace_dir: Path, runtime_config: Path, rules_dir: Path, log_path: Path) -> Proc:
        trace_dirs.append(trace_dir)
        trace_dir.mkdir(parents=True)
        (trace_dir / "trace.json").write_text(json.dumps(_proxy_trace_tool_call()), encoding="utf-8")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("synthetic compact proxy log", encoding="utf-8")
        return Proc()

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        result_dir = Path(command[command.index("--result-dir") + 1])
        roots.append(result_dir.parents[1])
        result_dir.mkdir(parents=True, exist_ok=True)
        (result_dir / "result.json").write_text(
            json.dumps(
                {
                    "id": "web_search_base_0",
                    "model_response": [{"function_call": True}],
                    "model_response_decoded": [{"function_call": True}],
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(capture, "_sync_fixture_env", lambda run_root, port: None)
    monkeypatch.setattr(capture, "_start_proxy", fake_start_proxy)
    monkeypatch.setattr(capture.subprocess, "run", fake_run)
    monkeypatch.setattr(capture, "_temporary_one_id_manifest", lambda: contextlib.nullcontext(tmp_path / "package_manifest.json"))

    request = {"run_ids": ["web_search_base_0"], "route_profile": "novacode", "route_model": "gpt-4.1", "generate_only": True, "raw_persistence_authorized": False}
    summary = execute_live_telemetry(
        packet_path=packet_path,
        output_artifact=tmp_path / "telemetry.json",
        live_capture_factory=lambda req: build_signed_one_id_live_shape_capture(req),
    )
    assert request["run_ids"] == ["web_search_base_0"]
    assert summary["blockers"] == []
    assert check_artifact(tmp_path / "telemetry.json")["bfcl_one_id_live_shape_telemetry_artifact_passed"] is True
    artifact = json.loads((tmp_path / "telemetry.json").read_text(encoding="utf-8"))
    record = artifact["records"][0]
    assert record["provider_response_has_tool_calls"] is True
    assert record["engine_apply_response_called"] is True
    assert record["proxy_responses_output_has_function_call"] is True
    assert record["bfcl_decode_execute_called"] is True
    assert record["bfcl_decode_execute_nonempty"] is True
    assert record["suspected_live_failure_stage"] == "live_path_nonempty"
    assert roots and all(not root.exists() for root in roots)
    assert trace_dirs and all(not trace_dir.exists() for trace_dir in trace_dirs)


def test_default_signed_capture_missing_provider_trace_fails_closed(monkeypatch, tmp_path: Path) -> None:
    import contextlib
    import subprocess
    import scripts.bfcl_one_id_live_shape_telemetry_capture as capture
    from scripts.bfcl_one_id_live_shape_telemetry_capture import build_signed_one_id_live_shape_capture

    packet_path = _approved_packet_path(tmp_path)

    class Proc:
        def terminate(self) -> None:
            pass

        def wait(self, timeout: int = 0) -> None:
            pass

        def kill(self) -> None:
            pass

    def fake_start_proxy(port: int, trace_dir: Path, runtime_config: Path, rules_dir: Path, log_path: Path) -> Proc:
        trace_dir.mkdir(parents=True)
        return Proc()

    monkeypatch.setattr(capture, "_sync_fixture_env", lambda run_root, port: None)
    monkeypatch.setattr(capture, "_start_proxy", fake_start_proxy)
    monkeypatch.setattr(capture.subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 0))
    monkeypatch.setattr(capture, "_temporary_one_id_manifest", lambda: contextlib.nullcontext(tmp_path / "package_manifest.json"))

    summary = execute_live_telemetry(
        packet_path=packet_path,
        output_artifact=tmp_path / "telemetry.json",
        live_capture_factory=lambda req: build_signed_one_id_live_shape_capture(req),
    )
    assert summary["blockers"] == ["live_shape_stage_not_instrumented:provider_upstream_response"]
    assert summary["diagnostic_written"] is False


def test_missing_non_provider_stage_uses_stage_label() -> None:
    from scripts.bfcl_one_id_live_shape_telemetry_capture import _normalize_observed_record

    record = _record("live_path_nonempty")
    record.pop("engine_apply_response_called")
    try:
        _normalize_observed_record(record)
    except RuntimeError as exc:
        assert str(exc) == "live_shape_stage_not_instrumented:runtime_engine_apply_response"
    else:
        raise AssertionError("expected missing runtime stage to fail closed")


def test_after_patch_packet_approved_scope_passes_without_broadening() -> None:
    summary = check(AFTER_PATCH_PACKET_PATH)
    assert summary["bfcl_one_id_live_shape_telemetry_gate_passed"] is True
    assert summary["approval_status"] == "approved"
    assert summary["signed_run_ids"] == ["web_search_base_0"]
    assert summary["provider_request_authorized"] is True
    assert summary["bfcl_generate_authorized"] is True
    assert summary["live_shape_telemetry_authorized"] is True


def test_after_patch_dry_run_plan_uses_new_output_and_no_execution() -> None:
    plan = build_plan(packet_path=AFTER_PATCH_PACKET_PATH, output_artifact=AFTER_PATCH_OUTPUT)
    assert plan["blockers"] == []
    assert plan["output_artifact_planned"] == str(AFTER_PATCH_OUTPUT)
    assert plan["provider_request_executed"] is False
    assert plan["bfcl_generate_executed"] is False
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False


def test_after_patch_packet_rejects_previous_output_mismatch() -> None:
    plan = build_plan(packet_path=AFTER_PATCH_PACKET_PATH, output_artifact=PREVIOUS_OUTPUT)
    assert any("output_artifact_mismatch_packet_scope" in blocker for blocker in plan["blockers"])


def test_previous_and_after_patch_artifacts_remain_valid() -> None:
    assert PREVIOUS_OUTPUT.exists()
    assert check_artifact(PREVIOUS_OUTPUT)["bfcl_one_id_live_shape_telemetry_artifact_passed"] is True
    assert AFTER_PATCH_OUTPUT.exists()
    after_patch_summary = check_artifact(AFTER_PATCH_OUTPUT)
    assert after_patch_summary["bfcl_one_id_live_shape_telemetry_artifact_passed"] is True
    assert after_patch_summary["run_ids"] == ["web_search_base_0"]


def test_after_patch_synthetic_artifact_path_accepted_by_checker(tmp_path: Path) -> None:
    artifact_path = tmp_path / AFTER_PATCH_OUTPUT.name
    artifact_path.write_text(json.dumps(_artifact("live_path_nonempty"), indent=2, sort_keys=True), encoding="utf-8")
    assert check_artifact(artifact_path)["bfcl_one_id_live_shape_telemetry_artifact_passed"] is True


def test_preexisting_output_rejected_before_capture(tmp_path: Path) -> None:
    packet_path = _approved_packet_path(tmp_path)
    out = tmp_path / AFTER_PATCH_OUTPUT.name
    out.write_text("{}", encoding="utf-8")

    def should_not_run(_: dict[str, object]) -> dict[str, object]:
        raise AssertionError("capture should not run when output exists")

    summary = execute_live_telemetry(packet_path=packet_path, output_artifact=out, live_capture=should_not_run)
    assert summary["provider_request_executed"] is False
    assert summary["bfcl_generate_executed"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
    assert summary["diagnostic_written"] is False
    assert summary["blockers"] == ["output_artifact_exists_without_clean_output"]
