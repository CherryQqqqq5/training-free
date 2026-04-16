from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from grc.compiler.mine import mine_failures


PROMPT_WITH_FUNCTIONS = """You are an expert in composing functions.
Here is a list of functions in json format that you can invoke.
[
  {
    "name": "lookup_weather",
    "description": "Lookup weather by city.",
    "parameters": {
      "type": "dict",
      "properties": {
        "city": {"type": "string"},
        "days": {"type": "integer"}
      },
      "required": ["city"]
    }
  }
]"""


class MineFailuresTests(unittest.TestCase):
    def test_mines_no_failure_for_json_action_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request": {
                            "model": "demo-model",
                            "messages": [{"role": "developer", "content": PROMPT_WITH_FUNCTIONS}],
                        },
                        "request_original": {
                            "model": "demo-model",
                            "input": [{"role": "developer", "content": PROMPT_WITH_FUNCTIONS}],
                        },
                        "raw_response": {
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
                        },
                        "validation": {"issues": []},
                    }
                ),
                encoding="utf-8",
            )

            failures = mine_failures(str(root))

        self.assertEqual(failures, [])

    def test_ignores_prompt_backed_clarification_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request": {
                            "model": "demo-model",
                            "messages": [{"role": "developer", "content": PROMPT_WITH_FUNCTIONS}],
                        },
                        "request_original": {
                            "model": "demo-model",
                            "input": [{"role": "developer", "content": PROMPT_WITH_FUNCTIONS}],
                        },
                        "raw_response": {
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": "Could you please provide the city information before I look up the weather?",
                                    }
                                }
                            ]
                        },
                        "validation": {
                            "issues": [
                                {
                                    "kind": "empty_tool_call",
                                    "tool_name": None,
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            failures = mine_failures(str(root))

        self.assertEqual(failures, [])

    def test_dedupes_validation_issue_when_raw_implies_same_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request": {
                            "model": "demo-model",
                            "messages": [{"role": "developer", "content": PROMPT_WITH_FUNCTIONS}],
                        },
                        "request_original": {
                            "model": "demo-model",
                            "input": [{"role": "developer", "content": PROMPT_WITH_FUNCTIONS}],
                        },
                        "raw_response": {
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": "[]",
                                    }
                                }
                            ]
                        },
                        "validation": {
                            "issues": [
                                {
                                    "kind": "empty_tool_call",
                                    "tool_name": None,
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            failures = mine_failures(str(root))

        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].error_type, "empty_tool_call")
        self.assertIsNone(failures[0].category)

    def test_mines_responses_prompt_backed_empty_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request": {
                            "model": "demo-model",
                            "messages": [{"role": "developer", "content": PROMPT_WITH_FUNCTIONS}],
                        },
                        "request_original": {
                            "model": "demo-model",
                            "input": [{"role": "developer", "content": PROMPT_WITH_FUNCTIONS}],
                        },
                        "raw_response": {
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": "[]",
                                    }
                                }
                            ]
                        },
                        "validation": {"issues": []},
                    }
                ),
                encoding="utf-8",
            )

            failures = mine_failures(str(root))

        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].error_type, "empty_tool_call")
        self.assertEqual(failures[0].tool_name, "__none__")

    def test_mines_responses_prompt_backed_type_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request": {
                            "model": "demo-model",
                            "messages": [{"role": "developer", "content": PROMPT_WITH_FUNCTIONS}],
                        },
                        "request_original": {
                            "model": "demo-model",
                            "input": [{"role": "developer", "content": PROMPT_WITH_FUNCTIONS}],
                        },
                        "raw_response": {
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": '[lookup_weather(city="Shanghai", days="3")]',
                                    }
                                }
                            ]
                        },
                        "validation": {"issues": []},
                    }
                ),
                encoding="utf-8",
            )

            failures = mine_failures(str(root))

        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].error_type, "type_mismatch")
        self.assertEqual(failures[0].tool_name, "lookup_weather")
        self.assertEqual(failures[0].field_name, "days")
        self.assertEqual(failures[0].expected_type, "integer")


if __name__ == "__main__":
    unittest.main()
