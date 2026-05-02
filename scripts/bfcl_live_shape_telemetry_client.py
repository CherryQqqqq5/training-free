#!/usr/bin/env python3
"""Signed env-only client for BFCL live-shape telemetry.

This module is import-safe: it does not read endpoint or key values on import.
Endpoint/key values are read only when the signed factory is constructed during
an approved ``--execute-telemetry`` path. The returned client persists no raw
request/response/header/body/log/trace data and returns compact shape records
only.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping

SIGNED_IDS = ("web_search_base_0", "multi_turn_base_0")
SIGNED_MODEL = "gpt-4.1"
SIGNED_PROFILE = "novacode"
SIGNED_ENDPOINT_ENVS = ("CHUANGZHI_NOVACODE_ENDPOINT", "NOVACODE_ENDPOINT")
SIGNED_KEY_ENVS = ("CHUANGZHI_API_KEY", "NOVACODE_API_KEY")
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


def _build_payload(run_id: str) -> dict[str, Any]:
    return {
        "model": SIGNED_MODEL,
        "messages": [
            {"role": "system", "content": "Synthetic live-shape telemetry only. Return the required tool call."},
            {"role": "user", "content": f"Run the synthetic live-shape telemetry probe for signed label {run_id}."},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": TOOL_NAME,
                    "description": "Synthetic live-shape telemetry probe. No BFCL case content.",
                    "parameters": {
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                        "required": ["ok"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
        "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
        "temperature": 0,
        "max_tokens": 32,
    }


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


def _shape_record(run_id: str, status: int, response: dict[str, Any]) -> dict[str, Any]:
    message = _message_from_response(response)
    has_tool = _has_tool_call(message)
    has_text = _has_text(message)
    status_class = f"{int(status // 100)}xx" if isinstance(status, int) and status > 0 else "unknown"
    if has_tool:
        response_shape = "chat_tool_call"
        parser_path = "chat_tool_calls"
        content_empty = "content_empty_with_tool_call" if not has_text else "content_nonempty_with_tool_call"
    elif has_text:
        response_shape = "chat_text_no_tool"
        parser_path = "chat_no_tool_text"
        content_empty = "content_nonempty_text"
    elif response:
        response_shape = "chat_nonempty_no_message"
        parser_path = "non_openai_compatible_response_shape"
        content_empty = "content_empty_no_tool"
    else:
        response_shape = "empty_response"
        parser_path = "empty_model_response"
        content_empty = "content_empty_no_tool"
    return {
        "run_id_label": run_id,
        "endpoint_path_label": "chat_completions",
        "request_shape_label": "chat_tools_single_function",
        "response_shape_label": response_shape,
        "status_code_class": status_class,
        "output_empty": not (has_tool or has_text),
        "tool_call_present": has_tool,
        "parser_decode_path_label": parser_path,
        "token_forwarding_label": "chat_max_tokens",
        "tool_choice_forwarding_label": "function_object",
        "instructions_forwarding_label": "system_message",
        "engine_content_empty_label": content_empty,
        "engine_coercion_label": "not_coerced",
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
    """Build the signed telemetry client for the approved two-ID gate."""

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
            status, response = _post_chat(endpoint, api_key, _build_payload(run_id), selected_opener)
            records.append(_shape_record(run_id, status, response))
        return records

    return client
