from __future__ import annotations

import json

import pytest

from scripts.build_bfcl_client_proxy_conformance_debug import build_report
from scripts.check_bfcl_client_proxy_conformance_debug import check as check_conformance


def _records() -> list[dict[str, object]]:
    return build_report()["records"]


def _responses_records() -> list[dict[str, object]]:
    return [record for record in _records() if record["proxy_endpoint_tested"] == "responses"]


def test_real_proxy_responses_path_preserves_instructions() -> None:
    assert any(record["instructions_preserved"] is True for record in _responses_records())
    assert all(record["input_message_count_bucket"] != "zero" for record in _responses_records())


def test_real_proxy_responses_path_preserves_tools_and_tool_choice() -> None:
    records = _responses_records()
    assert records
    assert all(record["tools_count"] == 1 for record in records)
    assert all(record["fake_upstream_seen_tools"] is True for record in records)
    assert all(record["fake_upstream_seen_tool_choice"] is True for record in records)


def test_responses_tool_choice_normalized_for_chat_upstream() -> None:
    assert all(record["tool_choice_forwarded_shape"] == "function_object" for record in _responses_records())


def test_max_output_tokens_forwarded_to_chat_max_tokens_or_recorded_if_not_forwarded() -> None:
    shapes = {record["token_field_forwarded_shape"] for record in _responses_records()}
    assert shapes == {"max_output_tokens_forwarded_as_chat_max_tokens"}


def test_fake_upstream_chat_tool_call_survives_proxy_to_responses_output() -> None:
    tool_records = [record for record in _responses_records() if record["fake_upstream_returned_tool_call"] is True]
    assert tool_records
    assert all(record["engine_final_has_tool_calls"] is True for record in tool_records)
    assert all(record["responses_output_has_function_call"] is True for record in tool_records)


def test_nonempty_text_no_tool_not_classified_as_provider_empty() -> None:
    text_records = [record for record in _responses_records() if record["fake_upstream_returned_nonempty_text"] is True]
    assert text_records
    assert any(record["responses_output_has_message_text"] is True for record in text_records)


def test_runtime_coercion_of_nonempty_text_is_detected() -> None:
    assert any(record["engine_coerced_nonempty_text_to_empty"] is True for record in _responses_records())


def test_true_empty_response_is_distinguished() -> None:
    assert any(record["true_empty_distinguished_from_coerced_empty"] is True for record in _responses_records())


def test_bfcl_decode_execute_nonempty_when_handler_available() -> None:
    tool_records = [record for record in _responses_records() if record["responses_output_has_function_call"] is True]
    assert tool_records
    for record in tool_records:
        if record["bfcl_handler_import_available"]:
            assert record["bfcl_decode_execute_nonempty"] is True
        else:
            pytest.skip("BFCL handler import unavailable")


def test_no_provider_no_bfcl_smoke_no_scorer_flags() -> None:
    report = build_report()
    assert report["provider_request_executed"] is False
    assert report["bfcl_smoke_executed"] is False
    assert report["scorer_executed"] is False
    assert report["full_baseline_executed"] is False
    assert report["candidate_runtime_activation_authorized"] is False
    assert report["performance_evidence"] is False
    assert report["sota_3pp_claim_ready"] is False
    assert report["huawei_acceptance_ready"] is False
    summary = check_conformance()
    assert summary["bfcl_client_proxy_conformance_debug_passed"] is True
    encoded = json.dumps(report, sort_keys=True)
    assert "Call lookup_weather for Paris" not in encoded
    assert "Synthetic non-tool completion" not in encoded
    assert "sk-" not in encoded
    assert "http://" not in encoded
    assert "https://" not in encoded
