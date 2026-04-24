from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

_INJECTED_YAML_STUB = False
try:
    import yaml as _yaml  # noqa: F401
except ModuleNotFoundError:
    sys.modules["yaml"] = types.SimpleNamespace(
        safe_dump=lambda data, **_: json.dumps(data, ensure_ascii=False, indent=2),
        safe_load=json.loads,
    )
    _INJECTED_YAML_STUB = True

from scripts.build_next_action_smoke_report import evaluate_cases, load_cases, render_markdown

if _INJECTED_YAML_STUB:
    sys.modules.pop("yaml", None)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "phase2_next_action_smoke"


class NextActionSmokeTests(unittest.TestCase):
    def test_all_next_action_smoke_cases_pass(self) -> None:
        summary = evaluate_cases(load_cases(FIXTURES_DIR))

        self.assertEqual(summary["case_count"], 20)
        self.assertEqual(summary["passed_count"], 20)
        self.assertGreaterEqual(summary["expected_activation_rate"], 0.8)
        self.assertEqual(summary["selected_tool_match_count"], 15)
        self.assertEqual(summary["stop_allowed_false_positive_count"], 0)
        self.assertEqual(summary["family_summary"]["stop_allowed"]["actual_activate"], 0)
        for family in ["find_to_cat", "path_sensitive_action", "explicit_literal_arg"]:
            self.assertEqual(summary["family_summary"][family]["actual_activate"], 5)

    def test_smoke_report_can_render_json_and_markdown(self) -> None:
        summary = evaluate_cases(load_cases(FIXTURES_DIR))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            json_path = root / "summary.json"
            md_path = root / "summary.md"
            json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            md_path.write_text(render_markdown(summary), encoding="utf-8")

            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = md_path.read_text(encoding="utf-8")

        self.assertEqual(loaded["blocked_reason_distribution"], {"activated": 15, "no_policy_candidate": 5})
        self.assertIn("arg_binding_match_count", loaded)
        self.assertIn("## Family Summary", markdown)
        self.assertIn("## Blocked Reasons", markdown)
        self.assertIn("| stop_allowed | 5 | 5 | 0 | 0 |", markdown)
        self.assertIn("Arg binding matches", markdown)

    def test_compiler_generated_report_counts_arg_binding_matches(self) -> None:
        summary = evaluate_cases(load_cases(FIXTURES_DIR), compiler_generated=True)

        self.assertEqual(summary["mode"], "compiler_generated")
        self.assertEqual(summary["case_count"], 20)
        self.assertEqual(summary["passed_count"], 20)
        self.assertEqual(summary["action_candidate_count"], 15)
        self.assertGreaterEqual(summary["arg_binding_present_count"], 15)
        self.assertEqual(summary["selected_tool_match_count"], 15)
        self.assertGreaterEqual(summary["arg_binding_match_count"], 15)
        self.assertEqual(summary["stop_allowed_false_positive_count"], 0)


if __name__ == "__main__":
    unittest.main()
