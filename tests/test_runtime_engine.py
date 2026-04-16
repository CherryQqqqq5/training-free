from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest

if "yaml" not in sys.modules:
    sys.modules["yaml"] = types.SimpleNamespace(safe_load=lambda _: {})

from grc.runtime.engine import RuleEngine


class RuntimeEngineTests(unittest.TestCase):
    def test_json_action_block_is_parsed_into_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "city": {"type": "string"},
                                    "days": {"type": "integer"},
                                },
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "action": "lookup_weather",
                                    "action_input": {"city": "Shanghai", "days": 3},
                                }
                            ),
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(repairs, [])
        self.assertEqual(validation.issues, [])
        tool_calls = final_response["choices"][0]["message"]["tool_calls"]
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["function"]["name"], "lookup_weather")
        self.assertEqual(tool_calls[0]["function"]["arguments"], json.dumps({"city": "Shanghai", "days": 3}))

    def test_multiple_json_action_blocks_are_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lockDoors",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "unlock": {"type": "boolean"},
                                    "door": {"type": "array"},
                                },
                                "required": ["unlock", "door"],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "setHeadlights",
                            "parameters": {
                                "type": "object",
                                "properties": {"mode": {"type": "string"}},
                                "required": ["mode"],
                            },
                        },
                    },
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": (
                                '{\n  "action": "lockDoors",\n  "action_input": {\n    "unlock": true,\n'
                                '    "door": ["driver", "passenger"]\n  }\n}\n'
                                '{\n  "action": "setHeadlights",\n  "action_input": {\n    "mode": "on"\n  }\n}'
                            ),
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(repairs, [])
        self.assertEqual(validation.issues, [])
        tool_calls = final_response["choices"][0]["message"]["tool_calls"]
        self.assertEqual([call["function"]["name"] for call in tool_calls], ["lockDoors", "setHeadlights"])

    def test_clarification_request_is_not_marked_as_empty_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Could you please provide the city before I look up the weather?",
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(repairs, [])
        self.assertFalse(validation.fallback_applied)
        self.assertEqual([issue.kind for issue in validation.issues], ["clarification_request"])
        self.assertEqual(
            final_response["choices"][0]["message"]["content"],
            "Could you please provide the city before I look up the weather?",
        )

    def test_true_empty_tool_call_still_records_failure(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            request = {
                "model": "demo-model",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"],
                            },
                        },
                    }
                ],
            }
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                        }
                    }
                ]
            }

            _, _, validation = engine.apply_response(request, response)

        self.assertEqual([issue.kind for issue in validation.issues], ["empty_tool_call"])


if __name__ == "__main__":
    unittest.main()
