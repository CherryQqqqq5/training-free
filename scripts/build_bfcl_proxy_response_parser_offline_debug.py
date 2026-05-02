#!/usr/bin/env python3
"""Build sanitized offline BFCL proxy response-parser debug evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from grc.runtime.engine import RuleEngine  # noqa: E402
from grc.runtime.proxy import (  # noqa: E402
    _chat_response_to_responses_payload,
    _responses_input_to_messages,
    _responses_tools_to_chat_tools,
)

DEFAULT_JSON = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_response_parser_offline_debug.json")
DEFAULT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_response_parser_offline_debug.md")
RUNTIME_CONFIG = Path("configs/runtime_bfcl_structured.yaml")
RULES_DIR = Path("rules/baseline_empty")

TOY_USER_MESSAGE = "Call lookup_weather for Paris."
TOY_INSTRUCTIONS = "Use the available function when a function is required."
TOY_FUNCTION_NAME = "lookup_weather"
TOY_ARGUMENTS = {"city": "Paris"}


def build_responses_request() -> dict[str, Any]:
    return {
        "model": "gpt-4.1",
        "instructions": TOY_INSTRUCTIONS,
        "input": [{"role": "user", "content": TOY_USER_MESSAGE}],
        "tools": [
            {
                "type": "function",
                "name": TOY_FUNCTION_NAME,
                "description": "Synthetic weather lookup.",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                    "additionalProperties": False,
                },
            }
        ],
        "tool_choice": {"type": "function", "function": {"name": TOY_FUNCTION_NAME}},
    }


def build_chat_request_from_responses(request: dict[str, Any]) -> dict[str, Any]:
    chat_request: dict[str, Any] = {
        "model": request.get("model"),
        "messages": _responses_input_to_messages(request.get("input")),
    }
    chat_tools = _responses_tools_to_chat_tools(request.get("tools"))
    if chat_tools:
        chat_request["tools"] = chat_tools
    if isinstance(request.get("tool_choice"), (str, dict)):
        chat_request["tool_choice"] = request["tool_choice"]
    return chat_request


def tool_choice_shape(value: Any) -> str:
    if isinstance(value, dict) and value.get("type") == "function":
        return "function_object"
    if value == "required":
        return "required_string"
    if value == "auto":
        return "auto_string"
    if value is None:
        return "absent"
    return "other"


def chat_tool_call_response() -> dict[str, Any]:
    return {
        "id": "synthetic_chat_tool_call",
        "model": "gpt-4.1",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_synthetic_1",
                            "type": "function",
                            "function": {
                                "name": TOY_FUNCTION_NAME,
                                "arguments": json.dumps(TOY_ARGUMENTS, sort_keys=True),
                            },
                        }
                    ],
                }
            }
        ],
    }


def chat_text_response() -> dict[str, Any]:
    return {
        "id": "synthetic_chat_text",
        "model": "gpt-4.1",
        "choices": [{"message": {"role": "assistant", "content": "Synthetic non-tool completion.", "tool_calls": []}}],
    }


def chat_empty_response() -> dict[str, Any]:
    return {
        "id": "synthetic_chat_empty",
        "model": "gpt-4.1",
        "choices": [{"message": {"role": "assistant", "content": "", "tool_calls": []}}],
    }


def _load_runtime_policy() -> dict[str, Any]:
    data = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    policy = data.get("runtime_policy")
    return policy if isinstance(policy, dict) else {}


def _message_content_empty(response: dict[str, Any]) -> bool:
    choices = response.get("choices") if isinstance(response.get("choices"), list) else []
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    return not bool(str(message.get("content") or "").strip())


def _message_has_tool_calls(response: dict[str, Any]) -> bool:
    choices = response.get("choices") if isinstance(response.get("choices"), list) else []
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    return bool(message.get("tool_calls"))


def _responses_output_has_function_call(payload: dict[str, Any]) -> bool:
    output = payload.get("output") if isinstance(payload.get("output"), list) else []
    return any(isinstance(item, dict) and item.get("type") == "function_call" for item in output)


def _responses_output_has_message_text(payload: dict[str, Any]) -> bool:
    output = payload.get("output") if isinstance(payload.get("output"), list) else []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content") if isinstance(item.get("content"), list) else []
        for chunk in content:
            if isinstance(chunk, dict) and str(chunk.get("text") or "").strip():
                return True
    return False


def _bfcl_decode_execute_nonempty(payload: dict[str, Any]) -> tuple[bool, bool]:
    try:
        from bfcl_eval.model_handler.utils import convert_to_function_call
    except Exception:
        return False, False
    output = payload.get("output") if isinstance(payload.get("output"), list) else []
    normalized: list[dict[str, Any]] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "function_call":
            continue
        name = item.get("name")
        arguments = item.get("arguments")
        if isinstance(name, str) and name:
            normalized.append({name: arguments if isinstance(arguments, str) else json.dumps(arguments or {}, sort_keys=True)})
    if not normalized:
        return True, False
    try:
        decoded = convert_to_function_call(normalized)
    except Exception:
        return True, False
    return True, bool(decoded)


def build_report() -> dict[str, Any]:
    responses_request = build_responses_request()
    chat_request = build_chat_request_from_responses(responses_request)
    messages = chat_request.get("messages") if isinstance(chat_request.get("messages"), list) else []
    tools = chat_request.get("tools") if isinstance(chat_request.get("tools"), list) else []

    engine = RuleEngine(str(RULES_DIR), runtime_policy=_load_runtime_policy())
    final_tool_response, _, _ = engine.apply_response(chat_request, chat_tool_call_response(), request_patches=[])
    final_text_response, text_repairs, _ = engine.apply_response(chat_request, chat_text_response(), request_patches=[])
    final_empty_response, _, _ = engine.apply_response(chat_request, chat_empty_response(), request_patches=[])
    responses_payload = _chat_response_to_responses_payload(final_tool_response)
    bfcl_import_available, bfcl_nonempty = _bfcl_decode_execute_nonempty(responses_payload)

    instructions_preserved = any(
        isinstance(message, dict)
        and message.get("role") in {"system", "developer"}
        and bool(str(message.get("content") or "").strip())
        for message in messages
    )
    engine_coerced_text = any(
        isinstance(repair, dict) and repair.get("kind") == "coerce_no_tool_text_to_empty" for repair in text_repairs
    )
    suspected = "not_reproduced_offline"
    if not instructions_preserved:
        suspected = "responses_instructions_input_conversion_loss"
    elif not tools:
        suspected = "tool_choice_tools_conversion_loss"
    elif not _message_has_tool_calls(final_tool_response):
        suspected = "chat_to_responses_payload_shape_loss"
    elif engine_coerced_text:
        suspected = "engine_no_tool_text_to_empty_coercion"
    elif _responses_output_has_function_call(responses_payload) and not bfcl_nonempty:
        suspected = "bfcl_responses_parser_decode_mismatch"

    true_empty_distinguished = _message_content_empty(final_empty_response) and not _message_has_tool_calls(final_empty_response)

    return {
        "has_instructions": bool(responses_request.get("instructions")),
        "instructions_preserved_to_chat_messages": instructions_preserved,
        "input_message_count": len(messages),
        "tools_count": len(tools),
        "tool_choice_shape": tool_choice_shape(chat_request.get("tool_choice")),
        "raw_chat_has_tool_calls": _message_has_tool_calls(chat_tool_call_response()),
        "raw_chat_has_nonempty_text": not _message_content_empty(chat_text_response()),
        "engine_final_has_tool_calls": _message_has_tool_calls(final_tool_response),
        "engine_final_content_empty": _message_content_empty(final_tool_response),
        "engine_coerced_nonempty_text_to_empty": engine_coerced_text,
        "responses_output_has_function_call": _responses_output_has_function_call(responses_payload),
        "responses_output_has_message_text": _responses_output_has_message_text(responses_payload),
        "bfcl_decode_execute_nonempty": bfcl_nonempty,
        "bfcl_handler_import_available": bfcl_import_available,
        "true_empty_response_distinguished": true_empty_distinguished,
        "provider_request_executed": False,
        "bfcl_smoke_executed": False,
        "bfcl_scorer_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "raw_prompt_persisted": False,
        "raw_provider_payload_persisted": False,
        "raw_trace_persisted": False,
        "suspected_failure_stage": suspected,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# BFCL Proxy Response Parser Offline Debug",
        "",
        "Status: offline synthetic shape-level artifact only. No provider request, BFCL smoke, scorer, candidate activation, performance, +3pp, or Huawei path was run or authorized.",
        "",
        f"- has_instructions: `{str(report['has_instructions']).lower()}`",
        f"- instructions_preserved_to_chat_messages: `{str(report['instructions_preserved_to_chat_messages']).lower()}`",
        f"- tools_count: `{report['tools_count']}`",
        f"- tool_choice_shape: `{report['tool_choice_shape']}`",
        f"- engine_coerced_nonempty_text_to_empty: `{str(report['engine_coerced_nonempty_text_to_empty']).lower()}`",
        f"- responses_output_has_function_call: `{str(report['responses_output_has_function_call']).lower()}`",
        f"- bfcl_decode_execute_nonempty: `{str(report['bfcl_decode_execute_nonempty']).lower()}`",
        f"- suspected_failure_stage: `{report['suspected_failure_stage']}`",
        "",
        "This artifact stores only booleans, counts, and enum labels from synthetic toy fixtures. It intentionally omits raw prompt text, raw model output text, function arguments, provider payloads, headers, logs, traces, BFCL case content, gold/reference/expected values, scorer diffs, endpoint/key values, and candidate output.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(args.md_output, report)
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
