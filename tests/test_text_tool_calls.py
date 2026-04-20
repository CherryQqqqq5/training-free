from __future__ import annotations

import unittest

from grc.utils.text_tool_calls import parse_text_tool_calls


class TextToolCallsTests(unittest.TestCase):
    def test_parse_text_tool_calls_supports_bare_python_style_call(self) -> None:
        calls = parse_text_tool_calls("touch(file_name='report.txt')")

        self.assertEqual(
            calls,
            [
                {
                    "id": "textcall_0",
                    "type": "function",
                    "function": {
                        "name": "touch",
                        "arguments": {"file_name": "report.txt"},
                    },
                }
            ],
        )

    def test_parse_text_tool_calls_supports_multiple_python_style_calls(self) -> None:
        calls = parse_text_tool_calls("cd(folder='workspace')\ntouch(file_name='notes.md')")

        self.assertEqual(
            calls,
            [
                {
                    "id": "textcall_0",
                    "type": "function",
                    "function": {
                        "name": "cd",
                        "arguments": {"folder": "workspace"},
                    },
                },
                {
                    "id": "textcall_1",
                    "type": "function",
                    "function": {
                        "name": "touch",
                        "arguments": {"file_name": "notes.md"},
                    },
                },
            ],
        )

    def test_parse_text_tool_calls_ignores_prose_wrapped_calls(self) -> None:
        calls = parse_text_tool_calls("I will call touch(file_name='report.txt') now.")

        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
