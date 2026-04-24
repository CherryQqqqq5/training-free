from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_phase2_target_subset import (
    build_case_report,
    rules_have_ctspc_actions,
    select_case_ids,
    summarize_case_report,
    write_test_case_ids,
)


class Phase2TargetSubsetTests(unittest.TestCase):
    def test_select_case_ids_prefers_failed_path_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            score = root / "bfcl" / "score" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_param_score.json"
            score.parent.mkdir(parents=True)
            score.write_text(
                "\n".join(
                    [
                        json.dumps({"accuracy": 0.0}),
                        json.dumps(
                            {
                                "id": "multi_turn_miss_param_2",
                                "valid": True,
                                "prompt": {"question": [[{"role": "user", "content": "read file report.txt"}]]},
                            }
                        ),
                        json.dumps(
                            {
                                "id": "multi_turn_miss_param_1",
                                "valid": False,
                                "prompt": {"question": [[{"role": "user", "content": "find matches then cat file"}]]},
                            }
                        ),
                        json.dumps(
                            {
                                "id": "multi_turn_miss_param_3",
                                "valid": False,
                                "prompt": {"question": [[{"role": "user", "content": "say hello"}]]},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            selected = select_case_ids(root, "multi_turn_miss_param", 2)

        self.assertEqual(selected, ["multi_turn_miss_param_1", "multi_turn_miss_param_2"])

    def test_write_test_case_ids_uses_category_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            path = Path(tmp_raw) / "test_case_ids_to_generate.json"
            write_test_case_ids(path, "multi_turn_miss_param", ["multi_turn_miss_param_7"])
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["multi_turn_miss_param"], ["multi_turn_miss_param_7"])

    def test_rules_have_ctspc_actions_detects_action_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            rule = root / "rule.yaml"
            rule.write_text(
                """
rules:
  - rule_id: r1
    action:
      decision_policy:
        recommended_tools: [cat]
        action_candidates:
          - tool: cat
            args: {file_name: notes.txt}
""",
                encoding="utf-8",
            )
            empty = root / "empty.yaml"
            empty.write_text("rules:\n  - rule_id: r2\n    action:\n      decision_policy: {}\n", encoding="utf-8")

            self.assertTrue(rules_have_ctspc_actions(rule))
            self.assertFalse(rules_have_ctspc_actions(empty))

    def test_build_case_report_joins_scores_and_trace_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            baseline = root / "baseline"
            candidate = root / "candidate"
            for run, valid in ((baseline, False), (candidate, True)):
                score = run / "bfcl" / "score" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_param_score.json"
                score.parent.mkdir(parents=True)
                score.write_text(
                    json.dumps({"accuracy": 0.0}) + "\n" + json.dumps({"id": "multi_turn_miss_param_1", "valid": valid}) + "\n",
                    encoding="utf-8",
                )
            result = candidate / "bfcl" / "result" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_param_result.json"
            result.parent.mkdir(parents=True)
            result.write_text(
                json.dumps({"id": "multi_turn_miss_param_1", "result": [[[{"cat": "{}"}]]]}) + "\n",
                encoding="utf-8",
            )
            trace = candidate / "traces" / "trace.json"
            trace.parent.mkdir(parents=True)
            trace.write_text(
                json.dumps(
                    {
                        "validation": {
                            "next_tool_plan_activated": True,
                            "selected_next_tool": "cat",
                            "next_tool_emitted": True,
                            "next_tool_matches_recommendation": True,
                            "next_tool_args_match_binding_normalized": True,
                            "repair_kinds": ["coerce_no_tool_text_to_empty"],
                        }
                    }
                ),
                encoding="utf-8",
            )

            rows = build_case_report(
                baseline_run=baseline,
                candidate_run=candidate,
                category="multi_turn_miss_param",
                selected_ids=["multi_turn_miss_param_1"],
            )
            summary = summarize_case_report(rows)

        self.assertTrue(rows[0]["case_fixed"])
        self.assertEqual(rows[0]["selected_next_tool"], "cat")
        self.assertEqual(rows[0]["repair_kinds"], ["coerce_no_tool_text_to_empty"])
        self.assertEqual(summary["case_fixed_count"], 1)
        self.assertTrue(summary["accepted"])


if __name__ == "__main__":
    unittest.main()
