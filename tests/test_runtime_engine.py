from __future__ import annotations

import sys
import tempfile
import types
import unittest

if "yaml" not in sys.modules:
    sys.modules["yaml"] = types.SimpleNamespace(safe_load=lambda _: {})

from grc.runtime.engine import RuleEngine


class RuntimeEngineTests(unittest.TestCase):
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
