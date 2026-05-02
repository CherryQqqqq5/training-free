#!/usr/bin/env python3
"""Signed env-only client for BFCL live-shape telemetry.

The execution path is intentionally BFCL-shaped: it builds a synthetic Responses
request, exercises the repository's Responses->chat proxy conversion helpers,
runs the runtime engine request/response handling, converts chat output back to a
Responses envelope, and records compact decode/parser flags. It does not read or
persist BFCL case content, raw provider payloads, headers, traces, endpoint
values, or key values.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

try:
    import yaml
except Exception:  # pragma: no cover - repository validation has yaml.
    yaml = None

from grc.runtime.engine import RuleEngine  # noqa: E402
from grc.runtime.proxy import (  # noqa: E402
    _chat_response_to_responses_payload,
    _responses_input_to_messages,
    _responses_token_fields_to_chat_fields,
    _responses_tools_to_chat_tools,
)

SIGNED_IDS = ("web_search_base_0", "multi_turn_base_0")
SIGNED_MODEL = "gpt-4.1"
SIGNED_PROFILE = "novacode"
SIGNED_ENDPOINT_ENVS = ("CHUANGZHI_NOVACODE_ENDPOINT", "NOVACODE_ENDPOINT")
SIGNED_KEY_ENVS = ("CHUANGZHI_API_KEY", "NOVACODE_API_KEY")
RUNTIME_CONFIG = REPO_ROOT / "configs/runtime_bfcl_structured.yaml"
RULES_DIR = REPO_ROOT / "rules/baseline_empty"
TOOL_NAME = "synthetic_live_shape_telemetry_ping"

TelemetryOpener = Callable[[urllib.request.Request, float], Any]
TelemetryClient = Callable[[dict[str, Any]], list[dict[str, Any]]]


class LiveShapeTelemetryClientError(RuntimeError):
    """Fail-closed telemetry transport error with an auditable blocker string."""


def _first_present(env: Mapping[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = env.get(name)
        if value:
            return value
    return None


def _validate_endpoint(endpoint: str) -> None:
    lowered = endpoint.lower()
    if not lowered.startswith("https://"):
        raise LiveShapeTelemetryClientError("telemetry_endpoint_not_https")
    for marker in ("raw", "trace", "case_id", "gold", "expected", "reference", "scorer", "candidate"):
        if marker in lowered:
            raise LiveShapeTelemetryClientError("telemetry_endpoint_forbidden_indicator")


def _validate_request(request: dict[str, Any]) -> None:
    if request.get("run_ids") != list(SIGNED_IDS):
        raise LiveShapeTelemetryClientError(f"telemetry_run_ids_not_signed:{request.get('run_ids')!r}")
    if request.get("route_model") != SIGNED_MODEL:
        raise LiveShapeTelemetryClientError(f"telemetry_model_not_signed:{request.get('route_model')!r}")
    if request.get("active_profile") != SIGNED_PROFILE:
        raise LiveShapeTelemetryClientError(f"telemetry_profile_not_signed:{request.get('active_profile')!r}")
    if request.get("max_total_cases") != len(SIGNED_IDS):
        raise LiveShapeTelemetryClientError(f"telemetry_case_count_not_signed:{request.get('max_total_cases')!r}")
    if request.get("raw_persistence_authorized") is not False:
        raise LiveShapeTelemetryClientError("telemetry_raw_persistence_not_false")


def _runtime_policy(*, coercion_probe: bool = False) -> dict[str, Any]:
    policy: dict[str, Any] = {}
    if yaml is not None and RUNTIME_CONFIG.exists():
        data = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("runtime_policy"), dict):
            policy.update(data["runtime_policy"])
    if coercion_probe:
        policy["coerce_no_tool_response_to_empty_kinds"] = ["empty_tool_call"]
    return policy


def _engine(*, coercion_probe: bool = False) -> RuleEngine:
    return RuleEngine(str(RULES_DIR), runtime_policy=_runtime_policy(coercion_probe=coercion_probe))


def _responses_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "name": TOOL_NAME,
        "description": "Synthetic live-shape telemetry probe. No BFCL case content.",
        "parameters": {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
    }


def _responses_request(run_id: str) -> dict[str, Any]:
    return {
        "model": SIGNED_MODEL,
        "instructions": "Synthetic BFCL-shaped live telemetry. Use the tool when required.",
        "input": [
            {"role": "user", "content": f"Run synthetic live-shape telemetry for signed run label {run_id}."}
        ],
        "tools": [_responses_tool()],
        "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
        "max_output_tokens": 32,
    }


def _responses_to_chat_request(request_json: dict[str, Any]) -> dict[str, Any]:
    chat_request: dict[str, Any] = {
        "model": request_json.get("model"),
        "messages": _responses_input_to_messages(request_json.get("input"), instructions=request_json.get("instructions")),
    }
    chat_request.update(_responses_token_fields_to_chat_fields(request_json))
    chat_tools = _responses_tools_to_chat_tools(request_json.get("tools"))
    if chat_tools:
        chat_request["tools"] = chat_tools
        if isinstance(request_json.get("tool_choice"), (str, dict)):
            chat_request["tool_choice"] = request_json["tool_choice"]
    return chat_request


def _default_opener(request: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.urlopen(request, timeout=timeout)  # nosec B310 - endpoint is signed env-only.


def _post_chat(endpoint: str, api_key: str, payload: dict[str, Any], opener: TelemetryOpener) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, 30) as response:
            status = int(response.status)
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        body = exc.read().decode("utf-8", errors="replace")
    parsed = json.loads(body) if body else {}
    if not isinstance(parsed, dict):
        parsed = {}
    return status, parsed


def _message_from_response(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return {}
    first = choices[0]
    if not isinstance(first, dict):
        return {}
    message = first.get("message")
    return message if isinstance(message, dict) else {}


def _has_tool_call(message: dict[str, Any]) -> bool:
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list):
        return False
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        function = call.get("function")
        if isinstance(function, dict) and function.get("name") == TOOL_NAME:
            return True
    return False


def _has_text(message: dict[str, Any]) -> bool:
    content = message.get("content")
    return isinstance(content, str) and bool(content.strip())


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
        return False, _responses_has_function_call(payload)
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


def _content_empty(response: dict[str, Any]) -> bool:
    message = _message_from_response(response)
    return not _has_text(message)


def _shape_record(run_id: str, status: int, upstream_chat: dict[str, Any], *, coercion_probe: bool = False) -> dict[str, Any]:
    responses_request = _responses_request(run_id)
    chat_request = _responses_to_chat_request(responses_request)
    engine = _engine(coercion_probe=coercion_probe)
    engine_request, request_patches = engine.apply_request(chat_request)
    final_chat, repairs, _ = engine.apply_response(engine_request, upstream_chat, request_patches=request_patches)
    responses_payload = _chat_response_to_responses_payload(final_chat)
    bfcl_decode_exercised, bfcl_decode_nonempty = _bfcl_decode_nonempty(responses_payload)

    upstream_message = _message_from_response(upstream_chat)
    upstream_tool_call = _has_tool_call(upstream_message)
    upstream_text = _has_text(upstream_message)
    upstream_empty = not upstream_tool_call and not upstream_text and not bool(upstream_chat)
    final_has_tool = _has_tool_call(_message_from_response(final_chat))
    final_content_empty = _content_empty(final_chat)
    coerced = any(isinstance(repair, dict) and repair.get("kind") == "coerce_no_tool_text_to_empty" for repair in repairs)
    responses_has_call = _responses_has_function_call(responses_payload)
    responses_has_text = _responses_has_message_text(responses_payload)
    status_class = f"{int(status // 100)}xx" if isinstance(status, int) and status > 0 else "unknown"

    suspected = "not_reproduced_live_shape_path"
    if upstream_empty:
        suspected = "true_upstream_empty_response"
    elif upstream_text and coerced:
        suspected = "runtime_no_tool_text_to_empty_coercion"
    elif upstream_tool_call and not final_has_tool:
        suspected = "runtime_engine_dropped_tool_call"
    elif final_has_tool and not responses_has_call:
        suspected = "chat_to_responses_envelope_dropped_function_call"
    elif responses_has_call and not bfcl_decode_nonempty:
        suspected = "bfcl_or_openai_decode_dropped_function_call"
    elif bool(upstream_chat) and not upstream_tool_call and not upstream_text:
        suspected = "non_openai_compatible_response_shape"

    return {
        "run_id_label": run_id,
        "endpoint_path_label": "responses_to_chat_proxy",
        "request_shape_label": "responses_tools_single_function",
        "response_shape_label": "responses_function_call" if responses_has_call else ("responses_message_text" if responses_has_text else "responses_empty_or_malformed"),
        "status_code_class": status_class,
        "output_empty": not (responses_has_call or responses_has_text),
        "tool_call_present": responses_has_call,
        "parser_decode_path_label": "bfcl_or_openai_responses_decode" if bfcl_decode_exercised else "openai_responses_shape_decode",
        "token_forwarding_label": "max_output_tokens_forwarded_as_chat_max_tokens" if engine_request.get("max_tokens") == responses_request.get("max_output_tokens") else "token_forwarding_unexpected",
        "tool_choice_forwarding_label": "function_object" if isinstance(engine_request.get("tool_choice"), dict) else "unexpected",
        "instructions_forwarding_label": "developer_message_prepended" if engine_request.get("messages") and engine_request["messages"][0].get("role") in {"system", "developer"} else "instructions_missing",
        "engine_content_empty_label": "content_empty" if final_content_empty else "content_nonempty",
        "engine_coercion_label": "coerced_no_tool_text_to_empty" if coerced else "not_coerced",
        "upstream_returned_tool_call": upstream_tool_call,
        "upstream_returned_nonempty_text": upstream_text,
        "upstream_returned_true_empty": upstream_empty,
        "responses_to_chat_conversion_exercised": True,
        "runtime_engine_exercised": True,
        "engine_final_has_tool_calls": final_has_tool,
        "engine_final_content_empty": final_content_empty,
        "engine_coerced_nonempty_text_to_empty": coerced,
        "chat_to_responses_conversion_exercised": True,
        "responses_output_has_function_call": responses_has_call,
        "responses_output_has_message_text": responses_has_text,
        "bfcl_or_openai_decode_exercised": True,
        "bfcl_decode_execute_nonempty": bfcl_decode_nonempty,
        "suspected_failure_stage": suspected,
        "raw_text_persisted": False,
        "raw_body_persisted": False,
        "raw_payload_persisted": False,
        "raw_header_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
    }


def build_signed_live_shape_telemetry_client(
    request: dict[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    opener: TelemetryOpener | None = None,
) -> TelemetryClient:
    """Build the signed telemetry client for the approved two-ID BFCL-shaped gate."""

    _validate_request(request)
    source_env = os.environ if env is None else env
    endpoint = _first_present(source_env, SIGNED_ENDPOINT_ENVS)
    if not endpoint:
        raise LiveShapeTelemetryClientError("telemetry_endpoint_missing")
    _validate_endpoint(endpoint)
    api_key = _first_present(source_env, SIGNED_KEY_ENVS)
    if not api_key:
        raise LiveShapeTelemetryClientError("telemetry_api_key_missing")
    selected_opener = _default_opener if opener is None else opener

    def client(client_request: dict[str, Any]) -> list[dict[str, Any]]:
        _validate_request(client_request)
        records: list[dict[str, Any]] = []
        for run_id in SIGNED_IDS:
            responses_request = _responses_request(run_id)
            chat_request = _responses_to_chat_request(responses_request)
            engine_request, _ = _engine().apply_request(chat_request)
            status, response = _post_chat(endpoint, api_key, engine_request, selected_opener)
            records.append(_shape_record(run_id, status, response))
        return records

    return client
