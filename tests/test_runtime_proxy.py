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

from grc.runtime.proxy import (
    _responses_input_to_messages,
    _responses_token_fields_to_chat_fields,
    _responses_tool_choice_to_chat_tool_choice,
    _responses_tools_to_chat_tools,
)

if _INJECTED_YAML_STUB:
    sys.modules.pop("yaml", None)
if _INJECTED_FASTAPI_STUB:
    sys.modules.pop("fastapi", None)
    sys.modules.pop("fastapi.responses", None)
if _INJECTED_HTTPX_STUB:
    sys.modules.pop("httpx", None)


class RuntimeProxyTests(unittest.TestCase):

    def test_responses_instructions_prepend_developer_message(self) -> None:
        messages = _responses_input_to_messages(
            [{"role": "user", "content": "Use a tool."}],
            instructions="Always preserve tool-call instructions.",
        )

        self.assertEqual(messages[0], {"role": "developer", "content": "Always preserve tool-call instructions."})
        self.assertEqual(messages[1], {"role": "user", "content": "Use a tool."})


    def test_responses_max_output_tokens_forwarded_as_chat_max_tokens(self) -> None:
        self.assertEqual(
            _responses_token_fields_to_chat_fields({"max_output_tokens": 128}),
            {"max_tokens": 128},
        )
        self.assertEqual(
            _responses_token_fields_to_chat_fields({"max_tokens": 64, "max_output_tokens": 128}),
            {"max_tokens": 64},
        )


    def test_bfcl_measurement_responses_tool_choice_missing_normalizes_to_required(self) -> None:
        chat_tools = _responses_tools_to_chat_tools([
            {"type": "function", "name": "lookup_weather", "parameters": {"type": "object", "properties": {}}},
            {"type": "function", "name": "lookup_time", "parameters": {"type": "object", "properties": {}}},
        ])

        self.assertEqual(
            _responses_tool_choice_to_chat_tool_choice(
                None,
                chat_tools,
                normalize_missing_none_to_required=True,
            ),
            "required",
        )

    def test_bfcl_measurement_responses_tool_choice_none_normalizes_to_required(self) -> None:
        chat_tools = _responses_tools_to_chat_tools([
            {"type": "function", "name": "lookup_weather", "parameters": {"type": "object", "properties": {}}},
        ])

        self.assertEqual(
            _responses_tool_choice_to_chat_tool_choice(
                "none",
                chat_tools,
                normalize_missing_none_to_required=True,
            ),
            "required",
        )

    def test_responses_tool_choice_not_injected_when_tools_absent(self) -> None:
        self.assertIsNone(
            _responses_tool_choice_to_chat_tool_choice(
                None,
                [],
                normalize_missing_none_to_required=True,
            )
        )

    def test_responses_tool_choice_default_behavior_does_not_force_required(self) -> None:
        chat_tools = _responses_tools_to_chat_tools([
            {"type": "function", "name": "lookup_weather", "parameters": {"type": "object", "properties": {}}},
        ])

        self.assertIsNone(_responses_tool_choice_to_chat_tool_choice(None, chat_tools))
        self.assertEqual(_responses_tool_choice_to_chat_tool_choice("none", chat_tools), "none")

    def test_responses_explicit_tool_choice_preserved(self) -> None:
        chat_tools = _responses_tools_to_chat_tools([
            {"type": "function", "name": "lookup_weather", "parameters": {"type": "object", "properties": {}}},
        ])
        function_object = {"type": "function", "function": {"name": "lookup_weather"}}

        self.assertEqual(
            _responses_tool_choice_to_chat_tool_choice(
                "required",
                chat_tools,
                normalize_missing_none_to_required=True,
            ),
            "required",
        )
        self.assertIs(
            _responses_tool_choice_to_chat_tool_choice(
                function_object,
                chat_tools,
                normalize_missing_none_to_required=True,
            ),
            function_object,
        )

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
