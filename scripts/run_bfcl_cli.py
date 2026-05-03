#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from bfcl_eval.__main__ import cli  # noqa: E402
from bfcl_eval.model_handler.api_inference.openai_completion import (  # noqa: E402
    OpenAICompletionsHandler,
)
from bfcl_eval.model_handler.api_inference.openai_response import (  # noqa: E402
    OpenAIResponsesHandler,
)
from bfcl_eval.model_handler.utils import convert_to_function_call  # noqa: E402
from grc.utils.bfcl_request_policy import (  # noqa: E402
    apply_bfcl_fc_request_policy,
    apply_bfcl_memory_request_policy,
)
from grc.utils.nl_tool_recovery import recover_high_confidence_tool_calls  # noqa: E402




def _capture_event_path() -> Path | None:
    value = os.environ.get("GRC_BFCL_DECODE_SHAPE_CAPTURE_PATH")
    if not value:
        return None
    return Path(value)


def _json_parseable_shape(value: Any) -> tuple[str, bool | None]:
    if isinstance(value, str):
        try:
            json.loads(value)
        except Exception:
            return "json_string", False
        return "json_string", True
    if isinstance(value, dict):
        return "object", True
    if isinstance(value, list):
        return "array", True
    if value is None:
        return "missing", None
    return type(value).__name__, None


def _safe_count(value: Any) -> int:
    return len(value) if isinstance(value, (list, tuple)) else 0


def _write_capture_event(event: dict[str, Any]) -> None:
    path = _capture_event_path()
    if path is None:
        return
    allowed: dict[str, Any] = {}
    for key, value in event.items():
        if isinstance(value, (str, int, bool)) or value is None:
            allowed[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(allowed, sort_keys=True) + "\n")


def _response_function_call_shape(api_response: Any) -> dict[str, Any]:
    output = getattr(api_response, "output", [])
    items = [item for item in output if getattr(item, "type", None) == "function_call"] if isinstance(output, list) else []
    first = items[0] if items else None
    arguments = getattr(first, "arguments", None) if first is not None else None
    arguments_shape, arguments_parseable = _json_parseable_shape(arguments)
    has_name = hasattr(first, "name") if first is not None else False
    has_function = hasattr(first, "function") if first is not None else False
    return {
        "proxy_function_call_item_count": len(items),
        "proxy_function_call_has_call_id": bool(first is not None and hasattr(first, "call_id")),
        "proxy_function_call_has_id": bool(first is not None and hasattr(first, "id")),
        "proxy_function_call_has_name": bool(has_name),
        "proxy_function_call_has_arguments": bool(first is not None and hasattr(first, "arguments")),
        "proxy_function_call_has_status": bool(first is not None and hasattr(first, "status")),
        "proxy_name_field_placement_label": "top_level" if has_name else ("nested_function_object" if has_function else "missing"),
        "proxy_arguments_shape_label": arguments_shape,
        "proxy_arguments_json_parseable_bool": arguments_parseable,
        "proxy_status_shape_label": "present_string" if first is not None and isinstance(getattr(first, "status", None), str) else ("missing" if first is None or not hasattr(first, "status") else type(getattr(first, "status", None)).__name__),
        "proxy_call_id_source_label": "call_id" if first is not None and hasattr(first, "call_id") else ("id" if first is not None and hasattr(first, "id") else "missing"),
    }


def _patch_parse_query_response_fc(handler_cls: type) -> None:
    original = handler_cls._parse_query_response_FC

    def wrapped(self, api_response):  # type: ignore[no-untyped-def]
        event = {"event": "bfcl_parse", "bfcl_parse_called": True, "bfcl_parse_exception_class": "none"}
        event.update(_response_function_call_shape(api_response))
        try:
            parsed = original(self, api_response)
        except Exception as exc:
            event["bfcl_parse_exception_class"] = exc.__class__.__name__
            event["bfcl_parse_model_responses_count"] = 0
            event["bfcl_parse_model_responses_shape_label"] = "exception"
            _write_capture_event(event)
            raise
        model_responses = parsed.get("model_responses") if isinstance(parsed, dict) else None
        event["bfcl_parse_model_responses_count"] = _safe_count(model_responses)
        event["bfcl_parse_model_responses_shape_label"] = "list" if isinstance(model_responses, list) else type(model_responses).__name__
        _write_capture_event(event)
        return parsed

    handler_cls._parse_query_response_FC = wrapped


def _coerce_text_result_to_execution_list(result: str, tools_payload: list[dict[str, Any]] | None = None) -> list[str]:
    stripped = result.strip()
    if not stripped:
        return []

    try:
        parsed = json.loads(stripped)
    except Exception:
        parsed = None
    if isinstance(parsed, (dict, list)):
        return convert_to_function_call(parsed)

    text_tool_calls = recover_high_confidence_tool_calls(stripped, tools_payload)
    if text_tool_calls:
        normalized: list[dict[str, Any]] = []
        for call in text_tool_calls:
            fn = call.get("function", {})
            name = fn.get("name")
            if not isinstance(name, str) or not name:
                continue
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    continue
            if isinstance(args, dict):
                normalized.append({name: args})
        if normalized:
            return convert_to_function_call(normalized)

    return []


def _patch_generate_with_backoff(handler_cls: type, *, api_path: str) -> None:
    original = handler_cls.generate_with_backoff

    def wrapped(self, **kwargs):  # type: ignore[no-untyped-def]
        patched = apply_bfcl_fc_request_policy(kwargs, api_path=api_path)
        patched = apply_bfcl_memory_request_policy(patched)
        self._grc_last_tools_payload = list(patched.get("tools", []))
        return original(self, **patched)

    handler_cls.generate_with_backoff = wrapped


def _patch_decode_execute(handler_cls: type) -> None:
    original = handler_cls.decode_execute

    def wrapped(self, result, has_tool_call_tag):  # type: ignore[no-untyped-def]
        event = {
            "event": "bfcl_decode",
            "bfcl_decode_execute_called": True,
            "bfcl_decode_exception_class": "none",
            "bfcl_decode_execute_nonempty": False,
            "bfcl_decode_output_count": 0,
        }
        try:
            if self.is_fc_model and isinstance(result, str):
                decoded = _coerce_text_result_to_execution_list(
                    result,
                    getattr(self, "_grc_last_tools_payload", None),
                )
            else:
                decoded = original(self, result, has_tool_call_tag)
        except Exception as exc:
            event["bfcl_decode_exception_class"] = exc.__class__.__name__
            _write_capture_event(event)
            raise
        event["bfcl_decode_execute_nonempty"] = bool(decoded)
        event["bfcl_decode_output_count"] = _safe_count(decoded)
        _write_capture_event(event)
        return decoded

    handler_cls.decode_execute = wrapped


_patch_generate_with_backoff(OpenAIResponsesHandler, api_path="responses")
_patch_generate_with_backoff(OpenAICompletionsHandler, api_path="chat_completions")
_patch_parse_query_response_fc(OpenAIResponsesHandler)
_patch_decode_execute(OpenAIResponsesHandler)
_patch_decode_execute(OpenAICompletionsHandler)


if __name__ == "__main__":
    cli()
