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

PROMPT_WITH_FILE_TOOL = """You are an expert in composing functions.
Here is a list of functions in json format that you can invoke.
[
  {
    "name": "cat",
    "description": "Display a file from the current directory.",
    "parameters": {
      "type": "dict",
      "properties": {
        "file_name": {"type": "string"}
      },
      "required": ["file_name"]
    }
  }
]"""


class MineFailuresTests(unittest.TestCase):
    def test_raises_when_trace_dir_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing_traces"
            with self.assertRaises(FileNotFoundError):
                mine_failures(str(missing))

    def test_raises_when_trace_dir_is_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_file = root / "trace.json"
            trace_file.write_text("{}", encoding="utf-8")

            with self.assertRaises(NotADirectoryError):
                mine_failures(str(trace_file))

    def test_mines_from_tool_schema_snapshot_without_prompt_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request": {"model": "demo-model"},
                        "request_original": {"model": "demo-model"},
                        "tool_schema_snapshot": {
                            "lookup_weather": {
                                "type": "dict",
                                "properties": {
                                    "city": {"type": "string"},
                                    "days": {"type": "int"},
                                },
                                "required": ["city"],
                            }
                        },
                        "raw_response": {
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": json.dumps(
                                            {
                                                "action": "lookup_weather",
                                                "action_input": {"city": "Shanghai", "days": "3"},
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

        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].error_type, "type_mismatch")
        self.assertEqual(failures[0].tool_name, "lookup_weather")
        self.assertEqual(failures[0].field_name, "days")
        self.assertEqual(failures[0].expected_type, "integer")

    def test_splits_prompt_backed_file_name_clarification_into_non_actionable_subfamily(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request": {
                            "model": "demo-model",
                            "messages": [{"role": "developer", "content": PROMPT_WITH_FILE_TOOL}],
                        },
                        "request_original": {
                            "model": "demo-model",
                            "input": [{"role": "developer", "content": PROMPT_WITH_FILE_TOOL}],
                        },
                        "raw_response": {
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": "Could you please provide the name of the file you'd like me to display?",
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
        self.assertEqual(failures[0].error_type, "clarification_no_tool")
        self.assertEqual(failures[0].request_predicates, ["tools_available"])

    def test_does_not_treat_unrelated_file_name_request_as_clarification(self) -> None:
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
                                        "content": "Could you please provide the name of the file you'd like me to display?",
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

    def test_splits_actionable_no_tool_decision_using_prior_explicit_literals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request": {
                            "model": "demo-model",
                            "messages": [
                                {"role": "user", "content": "Copy 'report.txt' into the backup directory."},
                                {"role": "developer", "content": PROMPT_WITH_FILE_TOOL},
                            ],
                        },
                        "request_original": {
                            "model": "demo-model",
                            "input": [
                                {"role": "user", "content": "Copy 'report.txt' into the backup directory."},
                                {"role": "developer", "content": PROMPT_WITH_FILE_TOOL},
                            ],
                        },
                        "raw_response": {
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": "I will prepare that copy now.",
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
        self.assertEqual(failures[0].error_type, "actionable_no_tool_decision")
        self.assertEqual(
            failures[0].request_predicates,
            ["tools_available", "prior_explicit_literals_present"],
        )
        self.assertEqual(failures[0].request_literals, ["report.txt"])

    def test_does_not_treat_arbitrary_quoted_string_as_actionable_literal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request": {
                            "model": "demo-model",
                            "messages": [
                                {"role": "user", "content": "Please handle \"that one\" for me."},
                                {"role": "developer", "content": PROMPT_WITH_FILE_TOOL},
                            ],
                        },
                        "request_original": {
                            "model": "demo-model",
                            "input": [
                                {"role": "user", "content": "Please handle \"that one\" for me."},
                                {"role": "developer", "content": PROMPT_WITH_FILE_TOOL},
                            ],
                        },
                        "raw_response": {
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": "I will take care of that now.",
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
        self.assertEqual(failures[0].request_literals, [])

    def test_splits_unsupported_no_tool(self) -> None:
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
                                        "content": "I can't directly complete that because there is no function available to do it.",
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
        self.assertEqual(failures[0].error_type, "unsupported_no_tool")
        self.assertEqual(failures[0].request_predicates, ["tools_available"])

    def test_ignores_validation_empty_tool_call_when_raw_has_json_action_block_without_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request": {"model": "demo-model"},
                        "request_original": {"model": "demo-model"},
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

    def test_ignores_validation_empty_tool_call_when_raw_is_clarification_without_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request": {"model": "demo-model"},
                        "request_original": {"model": "demo-model"},
                        "raw_response": {
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": "Could you please provide the city before I look up the weather?",
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

    def test_classifies_prompt_backed_unsupported_request(self) -> None:
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
                                        "content": "I can't directly complete that because there is no function available to do it.",
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
        self.assertEqual(failures[0].error_type, "unsupported_no_tool")

    def test_classifies_prompt_backed_malformed_output(self) -> None:
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
                                        "content": "<",
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
        self.assertEqual(failures[0].error_type, "malformed_output")

    def test_classifies_prompt_backed_hallucinated_completion(self) -> None:
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
                                        "content": "I've already initiated a tire pressure check. Once I have the results, I'll let you know.",
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
        self.assertEqual(failures[0].error_type, "hallucinated_completion")

    def test_splits_prompt_backed_clarification_request_into_non_actionable_subfamily(self) -> None:
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

        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].error_type, "clarification_no_tool")
        self.assertEqual(failures[0].request_predicates, ["tools_available"])

    def test_mines_redundant_clarification_when_file_name_already_exists_in_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request": {
                            "model": "demo-model",
                            "messages": [
                                {"role": "developer", "content": PROMPT_WITH_FILE_TOOL},
                                {"role": "user", "content": "Please display 'previous_report.pdf' from the current directory."},
                            ],
                        },
                        "request_original": {
                            "model": "demo-model",
                            "input": [
                                {"role": "user", "content": "Please display 'previous_report.pdf' from the current directory."}
                            ],
                        },
                        "raw_response": {
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": "Could you please provide the name of the file you'd like me to display?",
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
        self.assertEqual(failures[0].error_type, "redundant_clarification_request")
        self.assertEqual(failures[0].tool_name, "__none__")

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

    def test_mines_empty_completion_with_post_tool_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_path = root / "trace.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "request": {
                            "model": "demo-model",
                            "messages": [
                                {"role": "user", "content": "Create a ticket from plan.txt."},
                                {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
                                {"role": "tool", "tool_call_id": "c1", "content": json.dumps({"file_content": "Initial project plan details."})},
                            ],
                            "tools": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "create_ticket",
                                        "parameters": {
                                            "type": "object",
                                            "properties": {"title": {"type": "string"}},
                                            "required": ["title"],
                                        },
                                    },
                                }
                            ],
                        },
                        "request_original": {
                            "model": "demo-model",
                            "input": [
                                {"role": "user", "content": "Create a ticket from plan.txt."},
                                {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
                                {"role": "tool", "tool_call_id": "c1", "content": json.dumps({"file_content": "Initial project plan details."})},
                            ],
                        },
                        "raw_response": {
                            "choices": [
                                {
                                    "finish_reason": "stop",
                                    "message": {
                                        "role": "assistant",
                                        "content": None,
                                    }
                                }
                            ],
                            "usage": {"completion_tokens": 0},
                        },
                        "validation": {
                            "issues": [
                                {
                                    "kind": "empty_completion",
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
        self.assertEqual(failures[0].error_type, "empty_completion")
        self.assertEqual(failures[0].stage, "POST_TOOL")
        self.assertEqual(failures[0].failure_label, "(POST_TOOL,EMPTY_TOOL_CALL)")
        self.assertEqual(failures[0].request_predicates, ["tools_available", "prior_explicit_literals_present", "prior_tool_outputs_present"])

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
