#!/usr/bin/env python3
from __future__ import annotations

import json
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


def _patch_generate_with_backoff(handler_cls: type) -> None:
    original = handler_cls.generate_with_backoff

    def wrapped(self, **kwargs):  # type: ignore[no-untyped-def]
        patched = apply_bfcl_fc_request_policy(kwargs)
        patched = apply_bfcl_memory_request_policy(patched)
        self._grc_last_tools_payload = list(patched.get("tools", []))
        return original(self, **patched)

    handler_cls.generate_with_backoff = wrapped


def _patch_decode_execute(handler_cls: type) -> None:
    original = handler_cls.decode_execute

    def wrapped(self, result, has_tool_call_tag):  # type: ignore[no-untyped-def]
        if self.is_fc_model and isinstance(result, str):
            return _coerce_text_result_to_execution_list(
                result,
                getattr(self, "_grc_last_tools_payload", None),
            )
        return original(self, result, has_tool_call_tag)

    handler_cls.decode_execute = wrapped


_patch_generate_with_backoff(OpenAIResponsesHandler)
_patch_generate_with_backoff(OpenAICompletionsHandler)
_patch_decode_execute(OpenAIResponsesHandler)
_patch_decode_execute(OpenAICompletionsHandler)


if __name__ == "__main__":
    cli()
