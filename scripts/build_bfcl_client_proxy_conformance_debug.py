#!/usr/bin/env python3
"""Build no-provider BFCL client/proxy conformance debug evidence."""

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

DEFAULT_JSON = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_client_proxy_conformance_debug.json")
DEFAULT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_client_proxy_conformance_debug.md")
RUNTIME_CONFIG = Path("configs/runtime_bfcl_structured.yaml")
RULES_DIR = Path("rules/baseline_empty")

TOY_USER_MESSAGE = "Call lookup_weather for Paris."
TOY_INSTRUCTIONS = "Use the available function when a function is required."
TOY_FUNCTION_NAME = "lookup_weather"
TOY_ARGUMENTS = {"city": "Paris"}

REQUIRED_RECORD_FIELDS = [
    "bfcl_handler_import_available",
    "proxy_endpoint_tested",
    "instructions_preserved",
    "input_message_count_bucket",
    "tools_count",
    "tool_choice_input_shape",
    "tool_choice_forwarded_shape",
    "token_field_forwarded_shape",
    "fake_upstream_seen_tools",
    "fake_upstream_seen_tool_choice",
    "fake_upstream_seen_nonempty_messages",
    "fake_upstream_returned_tool_call",
    "fake_upstream_returned_nonempty_text",
    "engine_final_has_tool_calls",
    "engine_final_content_empty",
    "engine_coerced_nonempty_text_to_empty",
    "responses_output_has_function_call",
    "responses_output_has_message_text",
    "bfcl_decode_execute_nonempty",
    "true_empty_distinguished_from_coerced_empty",
    "suspected_failure_stage",
]


def _load_runtime_policy() -> dict[str, Any]:
    data = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    policy = data.get("runtime_policy")
    return policy if isinstance(policy, dict) else {}


def _engine(*, coercion_probe: bool = False) -> RuleEngine:
    policy = dict(_load_runtime_policy())
    if coercion_probe:
        policy["coerce_no_tool_response_to_empty_kinds"] = ["empty_tool_call"]
    return RuleEngine(str(RULES_DIR), runtime_policy=policy)


def _responses_request(*, with_history: bool = False) -> dict[str, Any]:
    base_input: list[Any] = [{"role": "user", "content": TOY_USER_MESSAGE}]
    if with_history:
        base_input = [
            {"role": "user", "content": TOY_USER_MESSAGE},
            {
                "type": "function_call",
                "id": "call_synthetic_history",
                "call_id": "call_synthetic_history",
                "name": TOY_FUNCTION_NAME,
                "arguments": TOY_ARGUMENTS,
            },
            {
                "type": "function_call_output",
                "call_id": "call_synthetic_history",
                "output": {"ok": True},
            },
            {"role": "user", "content": TOY_USER_MESSAGE},
        ]
    return {
        "model": "gpt-4.1",
        "instructions": TOY_INSTRUCTIONS,
        "input": base_input,
        "tools": [_responses_tool()],
        "tool_choice": {"type": "function", "function": {"name": TOY_FUNCTION_NAME}},
        "max_output_tokens": 128,
    }


def _chat_request() -> dict[str, Any]:
    return {
        "model": "gpt-4.1",
        "messages": [{"role": "user", "content": TOY_USER_MESSAGE}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": TOY_FUNCTION_NAME,
                    "description": "Synthetic weather lookup.",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
        "tool_choice": {"type": "function", "function": {"name": TOY_FUNCTION_NAME}},
        "max_tokens": 128,
    }


def _responses_tool() -> dict[str, Any]:
    return {
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


def _responses_to_chat_request(request: dict[str, Any]) -> dict[str, Any]:
    chat_request: dict[str, Any] = {
        "model": request.get("model"),
        "messages": _responses_input_to_messages(request.get("input"), instructions=request.get("instructions")),
    }
    chat_tools = _responses_tools_to_chat_tools(request.get("tools"))
    if chat_tools:
        chat_request["tools"] = chat_tools
        if isinstance(request.get("tool_choice"), (str, dict)):
            chat_request["tool_choice"] = request["tool_choice"]
    return chat_request


def _shape(value: Any) -> str:
    if isinstance(value, dict) and value.get("type") == "function":
        return "function_object"
    if value == "required":
        return "required_string"
    if value == "auto":
        return "auto_string"
    if value is None:
        return "absent"
    return "other"


def _bucket_count(value: int) -> str:
    if value == 0:
        return "zero"
    if value == 1:
        return "one"
    if value == 2:
        return "two"
    return "many"


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    return ""


def _fake_chat_response(kind: str) -> dict[str, Any]:
    if kind == "tool_call":
        return {
            "id": "synthetic_fake_tool_call",
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
    if kind == "text":
        return {"id": "synthetic_fake_text", "model": "gpt-4.1", "choices": [{"message": {"role": "assistant", "content": "Synthetic non-tool completion.", "tool_calls": []}}]}
    if kind == "empty":
        return {"id": "synthetic_fake_empty", "model": "gpt-4.1", "choices": [{"message": {"role": "assistant", "content": "", "tool_calls": []}}]}
    if kind == "malformed_nonempty":
        return {"id": "synthetic_fake_malformed", "model": "gpt-4.1", "choices": [{"delta": {"content": "Synthetic malformed nonempty completion."}}]}
    raise ValueError(f"unknown fake response kind: {kind}")


def _has_tool_calls(response: dict[str, Any]) -> bool:
    choices = response.get("choices") if isinstance(response.get("choices"), list) else []
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    return bool(message.get("tool_calls"))


def _content_empty(response: dict[str, Any]) -> bool:
    choices = response.get("choices") if isinstance(response.get("choices"), list) else []
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    return not bool(_message_text(message).strip())


def _responses_has_function_call(payload: dict[str, Any]) -> bool:
    output = payload.get("output") if isinstance(payload.get("output"), list) else []
    return any(isinstance(item, dict) and item.get("type") == "function_call" for item in output)


def _responses_has_message_text(payload: dict[str, Any]) -> bool:
    output = payload.get("output") if isinstance(payload.get("output"), list) else []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content") if isinstance(item.get("content"), list) else []
        for chunk in content:
            if isinstance(chunk, dict) and str(chunk.get("text") or "").strip():
                return True
    return False


def _bfcl_decode_nonempty(payload: dict[str, Any]) -> tuple[bool, bool]:
    try:
        from bfcl_eval.model_handler.utils import convert_to_function_call
    except Exception:
        return False, False
    normalized = []
    for item in payload.get("output") if isinstance(payload.get("output"), list) else []:
        if not isinstance(item, dict) or item.get("type") != "function_call":
            continue
        name = item.get("name")
        args = item.get("arguments")
        if isinstance(name, str) and name:
            normalized.append({name: args if isinstance(args, str) else json.dumps(args or {}, sort_keys=True)})
    if not normalized:
        return True, False
    try:
        return True, bool(convert_to_function_call(normalized))
    except Exception:
        return True, False


def _token_shape(original: dict[str, Any], forwarded: dict[str, Any], *, endpoint: str) -> str:
    if endpoint == "responses" and "max_output_tokens" in original:
        if forwarded.get("max_tokens") == original.get("max_output_tokens"):
            return "max_output_tokens_forwarded_as_chat_max_tokens"
        if "max_tokens" not in forwarded and "max_output_tokens" not in forwarded:
            return "max_output_tokens_not_forwarded_to_chat"
    if endpoint == "chat_completions" and "max_tokens" in forwarded:
        return "chat_max_tokens_forwarded"
    return "absent"


def _record(endpoint: str, original_request: dict[str, Any], fake_kind: str, *, coercion_probe: bool = False) -> dict[str, Any]:
    if endpoint == "responses":
        chat_request = _responses_to_chat_request(original_request)
    else:
        chat_request = dict(original_request)
    req_json, request_patches = _engine(coercion_probe=coercion_probe).apply_request(chat_request)
    fake_response = _fake_chat_response(fake_kind)
    final_chat, repairs, _ = _engine(coercion_probe=coercion_probe).apply_response(req_json, fake_response, request_patches=request_patches)
    responses_payload = _chat_response_to_responses_payload(final_chat) if endpoint == "responses" else {}
    bfcl_import_available, bfcl_nonempty = _bfcl_decode_nonempty(responses_payload) if endpoint == "responses" else (False, False)
    messages = req_json.get("messages") if isinstance(req_json.get("messages"), list) else []
    input_shape = _shape(original_request.get("tool_choice"))
    forwarded_shape = _shape(req_json.get("tool_choice"))
    instructions_preserved = endpoint != "responses" or bool(messages and messages[0].get("role") in {"system", "developer"})
    coerced = any(isinstance(repair, dict) and repair.get("kind") == "coerce_no_tool_text_to_empty" for repair in repairs)
    returned_text = fake_kind in {"text", "malformed_nonempty"}
    suspected = "not_reproduced_local_full_path"
    if endpoint == "responses" and not instructions_preserved:
        suspected = "responses_instructions_conversion_loss"
    elif req_json.get("tools") and not req_json.get("tool_choice"):
        suspected = "tool_choice_tools_conversion_loss"
    elif endpoint == "responses" and _token_shape(original_request, req_json, endpoint=endpoint) == "max_output_tokens_not_forwarded_to_chat":
        suspected = "responses_to_chat_token_field_not_forwarded"
    elif fake_kind == "malformed_nonempty":
        suspected = "chat_to_responses_payload_shape_loss"
    elif coerced:
        suspected = "engine_no_tool_text_to_empty_coercion"
    elif endpoint == "responses" and _responses_has_function_call(responses_payload) and not bfcl_nonempty:
        suspected = "bfcl_responses_parser_decode_mismatch"
    elif fake_kind == "empty":
        suspected = "true_model_upstream_empty_response"
    return {
        "bfcl_handler_import_available": bfcl_import_available,
        "proxy_endpoint_tested": endpoint,
        "instructions_preserved": instructions_preserved,
        "input_message_count_bucket": _bucket_count(len(messages)),
        "tools_count": len(req_json.get("tools") or []),
        "tool_choice_input_shape": input_shape,
        "tool_choice_forwarded_shape": forwarded_shape,
        "token_field_forwarded_shape": _token_shape(original_request, req_json, endpoint=endpoint),
        "fake_upstream_seen_tools": bool(req_json.get("tools")),
        "fake_upstream_seen_tool_choice": bool(req_json.get("tool_choice")),
        "fake_upstream_seen_nonempty_messages": any(bool(str(message.get("content") or "").strip()) for message in messages if isinstance(message, dict)),
        "fake_upstream_returned_tool_call": fake_kind == "tool_call",
        "fake_upstream_returned_nonempty_text": returned_text,
        "engine_final_has_tool_calls": _has_tool_calls(final_chat),
        "engine_final_content_empty": _content_empty(final_chat),
        "engine_coerced_nonempty_text_to_empty": coerced,
        "responses_output_has_function_call": _responses_has_function_call(responses_payload) if endpoint == "responses" else False,
        "responses_output_has_message_text": _responses_has_message_text(responses_payload) if endpoint == "responses" else False,
        "bfcl_decode_execute_nonempty": bfcl_nonempty,
        "true_empty_distinguished_from_coerced_empty": fake_kind == "empty" and not returned_text and not coerced and _content_empty(final_chat),
        "suspected_failure_stage": suspected,
    }


def build_records() -> list[dict[str, Any]]:
    return [
        _record("responses", _responses_request(), "tool_call"),
        _record("responses", _responses_request(with_history=True), "tool_call"),
        _record("chat_completions", _chat_request(), "tool_call"),
        _record("responses", _responses_request(), "text"),
        _record("responses", _responses_request(), "text", coercion_probe=True),
        _record("responses", _responses_request(), "empty"),
        _record("responses", _responses_request(), "malformed_nonempty"),
    ]


def build_report() -> dict[str, Any]:
    records = build_records()
    suspected = [record["suspected_failure_stage"] for record in records if record["suspected_failure_stage"] != "not_reproduced_local_full_path"]
    primary = suspected[0] if suspected else "not_reproduced_local_full_path"
    return {
        "artifact_kind": "bfcl_client_proxy_conformance_debug",
        "approval_status": "prepared",
        "provider_request_executed": False,
        "bfcl_smoke_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "raw_prompt_persisted": False,
        "raw_provider_payload_persisted": False,
        "raw_trace_persisted": False,
        "records": records,
        "suspected_failure_stage": primary,
        "proposed_minimal_future_gate": "no_provider_live_bfcl_client_proxy_fake_upstream_harness" if primary != "not_reproduced_local_full_path" else "live_shape_telemetry_gate_before_patch",
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# BFCL Client/Proxy Conformance Debug",
        "",
        "Status: no-provider synthetic conformance artifact. No provider request, BFCL smoke, scorer, full/default baseline, candidate activation, performance, +3pp, or Huawei path was run.",
        "",
        f"- suspected_failure_stage: `{report['suspected_failure_stage']}`",
        f"- proposed_minimal_future_gate: `{report['proposed_minimal_future_gate']}`",
        f"- record_count: `{len(report['records'])}`",
        "",
        "Records are shape-only and omit raw prompt text, model output text, full arguments, provider payloads, headers, logs, traces, BFCL case content, gold/reference/expected, scorer diffs, endpoint/key values, and candidate output.",
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
