from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest

_INJECTED_YAML_STUB = False
try:
    import yaml as _yaml  # noqa: F401
except ModuleNotFoundError:
    sys.modules["yaml"] = types.SimpleNamespace(safe_load=lambda _: {})
    _INJECTED_YAML_STUB = True

from grc.runtime.engine import RuleEngine
from grc.types import FallbackRoutingSpec, MatchSpec, PatchScope, Rule, RuleAction

if _INJECTED_YAML_STUB:
    sys.modules.pop("yaml", None)


class RuntimeEngineTests(unittest.TestCase):
    def test_hallucinated_completion_recovery_rule_overrides_record_only_default(self) -> None:
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(rules_dir)
            engine.rules = [
                Rule(
                    rule_id="rule_global_hallucinated_completion_v1",
                    trigger=MatchSpec(error_types=["hallucinated_completion"]),
                    scope=PatchScope(tool_names=[], patch_sites=["fallback_router"]),
                    action=RuleAction(
                        fallback_router=FallbackRoutingSpec(
                            strategy="assistant_message",
                            assistant_message="No tool call was emitted. Emit the required tool call before claiming progress.",
                            on_issue_kinds=["hallucinated_completion"],
                        )
                    ),
                )
            ]
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
                            "content": "I've already initiated a weather lookup. Once I have the results, I'll let you know.",
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(repairs, [])
        self.assertTrue(validation.fallback_applied)
        self.assertEqual([issue.kind for issue in validation.issues], ["hallucinated_completion"])
        self.assertEqual(
            final_response["choices"][0]["message"]["content"],
            "No tool call was emitted. Emit the required tool call before claiming progress.",
        )

    def test_hallucinated_completion_is_record_only_by_default(self) -> None:
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
                            "content": "I've already initiated a weather lookup. Once I have the results, I'll let you know.",
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(repairs, [])
        self.assertFalse(validation.fallback_applied)
        self.assertEqual([issue.kind for issue in validation.issues], ["hallucinated_completion"])
        self.assertEqual(
            final_response["choices"][0]["message"]["content"],
            "I've already initiated a weather lookup. Once I have the results, I'll let you know.",
        )

    def test_natural_language_termination_is_record_only_by_default(self) -> None:
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
                            "content": "Task is complete.",
                        }
                    }
                ]
            }

            final_response, repairs, validation = engine.apply_response(request, response)

        self.assertEqual(repairs, [])
        self.assertFalse(validation.fallback_applied)
        self.assertEqual([issue.kind for issue in validation.issues], ["natural_language_termination"])
        self.assertEqual(final_response["choices"][0]["message"]["content"], "Task is complete.")

    def test_engine_normalizes_tool_schema_types_from_request_tools(self) -> None:
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
                                "type": "dict",
                                "properties": {"days": {"type": "int"}},
                                "required": [],
                            },
                        },
                    }
                ],
            }

            schema_map = engine._tool_schema_map(request)

        self.assertEqual(schema_map["lookup_weather"]["type"], "object")
        self.assertEqual(schema_map["lookup_weather"]["properties"]["days"]["type"], "integer")

    def test_unsupported_request_is_not_marked_as_empty_tool_call(self) -> None:
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
                            "content": "I can't directly complete that because there is no function available to do it.",
                        }
                    }
                ]
            }

            _, _, validation = engine.apply_response(request, response)

        self.assertEqual([issue.kind for issue in validation.issues], ["unsupported_request"])

    def test_malformed_output_is_not_marked_as_empty_tool_call(self) -> None:
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
                            "content": "<",
                        }
                    }
                ]
            }

            _, _, validation = engine.apply_response(request, response)

        self.assertEqual([issue.kind for issue in validation.issues], ["malformed_output"])

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
