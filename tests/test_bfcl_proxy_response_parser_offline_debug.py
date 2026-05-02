from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_bfcl_proxy_response_parser_offline_debug import (
    _load_runtime_policy,
    _message_content_empty,
    _message_has_tool_calls,
    _responses_output_has_function_call,
    build_chat_request_from_responses,
    build_report,
    build_responses_request,
    chat_empty_response,
    chat_text_response,
    chat_tool_call_response,
)
from grc.runtime.engine import RuleEngine
from grc.runtime.proxy import _chat_response_to_responses_payload, _responses_tools_to_chat_tools
from scripts.check_bfcl_proxy_response_parser_debug_packet import check as check_packet


def _engine() -> RuleEngine:
    return RuleEngine("rules/baseline_empty", runtime_policy=_load_runtime_policy())


def test_responses_instructions_preserved_to_chat_request() -> None:
    report = build_report()
    assert report["has_instructions"] is True
    assert report["input_message_count"] == 1
    if report["instructions_preserved_to_chat_messages"] is False:
        assert report["suspected_failure_stage"] == "responses_instructions_input_conversion_loss"


def test_responses_tools_and_tool_choice_preserved() -> None:
    request = build_responses_request()
    chat_request = build_chat_request_from_responses(request)
    assert len(_responses_tools_to_chat_tools(request["tools"])) == 1
    assert len(chat_request["tools"]) == 1
    assert chat_request["tool_choice"]["type"] == "function"
    assert build_report()["tool_choice_shape"] == "function_object"


def test_chat_tool_call_survives_engine_and_responses_conversion() -> None:
    chat_request = build_chat_request_from_responses(build_responses_request())
    final_response, repairs, _ = _engine().apply_response(chat_request, chat_tool_call_response(), request_patches=[])
    responses_payload = _chat_response_to_responses_payload(final_response)
    assert _message_has_tool_calls(final_response) is True
    assert _responses_output_has_function_call(responses_payload) is True
    assert not any(isinstance(repair, dict) and repair.get("kind") == "coerce_no_tool_text_to_empty" for repair in repairs)


def test_no_tool_text_is_attributed_not_silent_empty() -> None:
    chat_request = build_chat_request_from_responses(build_responses_request())
    final_response, repairs, validation = _engine().apply_response(chat_request, chat_text_response(), request_patches=[])
    coerced = any(isinstance(repair, dict) and repair.get("kind") == "coerce_no_tool_text_to_empty" for repair in repairs)
    assert _message_content_empty(chat_text_response()) is False
    assert coerced or _message_content_empty(final_response) is False
    assert validation.issues or coerced or _message_content_empty(final_response) is False


def test_true_empty_response_is_distinguishable() -> None:
    chat_request = build_chat_request_from_responses(build_responses_request())
    final_response, repairs, validation = _engine().apply_response(chat_request, chat_empty_response(), request_patches=[])
    assert _message_content_empty(final_response) is True
    assert _message_has_tool_calls(final_response) is False
    assert build_report()["true_empty_response_distinguished"] is True
    assert validation.issues or repairs == []


def test_responses_payload_decodes_to_bfcl_nonempty_tool_call() -> None:
    report = build_report()
    if not report["bfcl_handler_import_available"]:
        pytest.skip("BFCL handler import unavailable in this environment")
    assert report["responses_output_has_function_call"] is True
    assert report["bfcl_decode_execute_nonempty"] is True


def test_no_provider_no_bfcl_smoke_no_scorer_flags(tmp_path: Path) -> None:
    packet_summary = check_packet()
    assert packet_summary["bfcl_proxy_response_parser_debug_packet_passed"] is True
    report = build_report()
    assert report["provider_request_executed"] is False
    assert report["bfcl_smoke_executed"] is False
    assert report["bfcl_scorer_executed"] is False
    assert report["candidate_runtime_activation_authorized"] is False
    assert report["performance_evidence"] is False
    encoded = json.dumps(report, sort_keys=True)
    assert "Call lookup_weather for Paris" not in encoded
    assert "Synthetic non-tool completion" not in encoded
    assert "sk-" not in encoded
    assert "http://" not in encoded
    assert "https://" not in encoded
