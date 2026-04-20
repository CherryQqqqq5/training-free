from __future__ import annotations

from grc.utils.nl_tool_recovery import recover_high_confidence_tool_calls


def test_recover_high_confidence_tool_calls_supports_embedded_python_call() -> None:
    calls = recover_high_confidence_tool_calls(
        "I will call touch(file_name='report.txt') now."
    )
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "touch"
    assert calls[0]["function"]["arguments"]["file_name"] == "report.txt"


def test_recover_high_confidence_tool_calls_uses_single_tool_schema_with_labeled_fields() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "touch",
                "parameters": {
                    "type": "object",
                    "properties": {"file_name": {"type": "string"}},
                    "required": ["file_name"],
                },
            },
        }
    ]
    calls = recover_high_confidence_tool_calls(
        'Please create the file. file_name: "notes.txt"',
        tools,
    )
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "touch"
    assert calls[0]["function"]["arguments"]["file_name"] == "notes.txt"


def test_recover_high_confidence_tool_calls_requires_unambiguous_tool_choice() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "touch",
                "parameters": {
                    "type": "object",
                    "properties": {"file_name": {"type": "string"}},
                    "required": ["file_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mkdir",
                "parameters": {
                    "type": "object",
                    "properties": {"dir_name": {"type": "string"}},
                    "required": ["dir_name"],
                },
            },
        },
    ]
    calls = recover_high_confidence_tool_calls(
        'Please create it. file_name: "notes.txt"',
        tools,
    )
    assert calls == []
