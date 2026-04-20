from __future__ import annotations

import json
import sys
import types
import unittest

_INJECTED_YAML_STUB = False
try:
    import yaml as _yaml  # noqa: F401
except ModuleNotFoundError:
    sys.modules["yaml"] = types.SimpleNamespace(safe_load=lambda _: {})
    _INJECTED_YAML_STUB = True

_INJECTED_FASTAPI_STUB = False
try:
    import fastapi as _fastapi  # noqa: F401
except ModuleNotFoundError:
    sys.modules["fastapi"] = types.SimpleNamespace(FastAPI=object, HTTPException=Exception, Request=object)
    sys.modules["fastapi.responses"] = types.SimpleNamespace(JSONResponse=object)
    _INJECTED_FASTAPI_STUB = True

_INJECTED_HTTPX_STUB = False
try:
    import httpx as _httpx  # noqa: F401
except ModuleNotFoundError:
    sys.modules["httpx"] = types.SimpleNamespace(AsyncClient=object)
    _INJECTED_HTTPX_STUB = True

from grc.runtime.proxy import _responses_input_to_messages

if _INJECTED_YAML_STUB:
    sys.modules.pop("yaml", None)
if _INJECTED_FASTAPI_STUB:
    sys.modules.pop("fastapi", None)
    sys.modules.pop("fastapi.responses", None)
if _INJECTED_HTTPX_STUB:
    sys.modules.pop("httpx", None)


class RuntimeProxyTests(unittest.TestCase):
    def test_responses_input_preserves_function_call_history(self) -> None:
        request_input = [
            {"role": "user", "content": "Unlock the driver door."},
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "I'll unlock it now."}],
            },
            {
                "type": "function_call",
                "id": "fc_1",
                "call_id": "call_1",
                "name": "lockDoors",
                "arguments": {"unlock": True, "door": ["driver"]},
            },
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": {"success": True},
            },
            {"role": "user", "content": "Now turn the headlights on."},
        ]

        messages = _responses_input_to_messages(request_input)

        self.assertEqual(messages[0], {"role": "user", "content": "Unlock the driver door."})
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], "I'll unlock it now.")
        self.assertEqual(
            messages[1]["tool_calls"],
            [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "lockDoors",
                        "arguments": json.dumps({"unlock": True, "door": ["driver"]}, ensure_ascii=False),
                    },
                }
            ],
        )
        self.assertEqual(
            messages[2],
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": json.dumps({"success": True}, ensure_ascii=False),
            },
        )
        self.assertEqual(messages[3], {"role": "user", "content": "Now turn the headlights on."})

    def test_responses_input_creates_assistant_message_for_function_call_without_text(self) -> None:
        request_input = [
            {
                "type": "function_call",
                "call_id": "call_2",
                "name": "lookup_weather",
                "arguments": {"city": "Shanghai"},
            },
            {
                "type": "function_call_output",
                "call_id": "call_2",
                "output": "Sunny",
            },
        ]

        messages = _responses_input_to_messages(request_input)

        self.assertEqual(messages[0]["role"], "assistant")
        self.assertEqual(messages[0]["content"], "")
        self.assertEqual(messages[0]["tool_calls"][0]["id"], "call_2")
        self.assertEqual(messages[0]["tool_calls"][0]["function"]["name"], "lookup_weather")
        self.assertEqual(messages[1], {"role": "tool", "tool_call_id": "call_2", "content": "Sunny"})

    def test_responses_input_merges_multiple_function_calls_into_one_assistant_message(self) -> None:
        request_input = [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "I'll perform both actions."}],
            },
            {
                "type": "function_call",
                "call_id": "call_a",
                "name": "lockDoors",
                "arguments": {"unlock": True, "door": ["driver"]},
            },
            {
                "type": "function_call",
                "call_id": "call_b",
                "name": "setHeadlights",
                "arguments": {"mode": "on"},
            },
        ]

        messages = _responses_input_to_messages(request_input)

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "assistant")
        self.assertEqual(messages[0]["content"], "I'll perform both actions.")
        self.assertEqual([call["id"] for call in messages[0]["tool_calls"]], ["call_a", "call_b"])


if __name__ == "__main__":
    unittest.main()
