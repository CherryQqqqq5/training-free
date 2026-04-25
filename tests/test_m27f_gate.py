from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_m27f_gate import evaluate_m27f_gate


def passing_summary() -> dict[str, object]:
    return {
        "case_report_trace_mapping": "prompt_user_prefix",
        "baseline_accuracy": 10.0,
        "candidate_accuracy": 20.0,
        "case_fixed_count": 3,
        "case_regressed_count": 1,
        "net_case_gain": 2,
        "policy_plan_activated_count": 5,
        "recommended_tool_match_rate_among_activated": 0.6,
        "raw_normalized_arg_match_rate_among_activated": 0.6,
        "stop_allowed_false_positive_count": 0,
        "accepted": False,
    }


class M27fGateTests(unittest.TestCase):
    def test_mapping_fallback_fails_even_when_accuracy_improves(self) -> None:
        summary = passing_summary()
        summary["case_report_trace_mapping"] = "mtime_by_result_step_count"

        report = evaluate_m27f_gate(summary)

        self.assertFalse(report["m2_7f_gate_passed"])
        self.assertFalse(report["criteria"]["case_report_trace_mapping"]["passed"])
        self.assertEqual(report["diagnostic"]["case_level_evidence"], "diagnostic_only")
        self.assertEqual(report["diagnostic"]["recommended_next_focus"], "prompt_prefix_fallback")

    def test_net_case_gain_below_two_fails(self) -> None:
        summary = passing_summary()
        summary["case_fixed_count"] = 2
        summary["case_regressed_count"] = 1
        summary["net_case_gain"] = 1

        report = evaluate_m27f_gate(summary)

        self.assertFalse(report["m2_7f_gate_passed"])
        self.assertFalse(report["criteria"]["net_case_gain_min_2"]["passed"])
        self.assertEqual(report["diagnostic"]["recommended_next_focus"], "trajectory_continuation_or_final_answer")

    def test_candidate_accuracy_not_above_baseline_fails(self) -> None:
        summary = passing_summary()
        summary["candidate_accuracy"] = 10.0

        report = evaluate_m27f_gate(summary)

        self.assertFalse(report["m2_7f_gate_passed"])
        self.assertFalse(report["criteria"]["candidate_accuracy_gt_baseline_accuracy"]["passed"])
        self.assertEqual(report["diagnostic"]["recommended_next_focus"], "over_actuation_or_repair_interaction")

    def test_all_explicit_conditions_pass(self) -> None:
        report = evaluate_m27f_gate(passing_summary())

        self.assertTrue(report["m2_7f_gate_passed"])
        self.assertEqual(report["diagnostic"]["case_level_evidence"], "durable")
        self.assertFalse(report["diagnostic"]["do_not_expand_to_100_case_m28_or_full_bfcl"])


    def test_case_level_gate_disallowed_fails_even_when_mapping_and_metrics_pass(self) -> None:
        summary = passing_summary()
        summary["case_level_gate_allowed"] = False

        report = evaluate_m27f_gate(summary)

        self.assertFalse(report["m2_7f_gate_passed"])
        self.assertFalse(report["criteria"]["case_level_gate_allowed"]["passed"])
        self.assertEqual(report["diagnostic"]["case_level_evidence"], "diagnostic_only")
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "case_level_gate_allowed")
        self.assertEqual(report["diagnostic"]["recommended_next_focus"], "trace_completeness_or_prompt_prefix_fallback")

    def test_mtime_mapping_with_good_metrics_remains_diagnostic_only(self) -> None:
        summary = passing_summary()
        summary["case_report_trace_mapping"] = "mtime_by_result_step_count"
        summary["case_level_gate_allowed"] = False
        summary["accepted"] = True

        report = evaluate_m27f_gate(summary)

        self.assertFalse(report["m2_7f_gate_passed"])
        self.assertEqual(report["diagnostic"]["case_level_evidence"], "diagnostic_only")
        self.assertIn("case_level_gate_allowed", report["diagnostic"]["failed_criteria"])
        self.assertIn("case_report_trace_mapping", report["diagnostic"]["failed_criteria"])

    def test_cli_exit_code_reflects_explicit_gate_not_accepted_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            summary_path = Path(tmp_raw) / "subset_summary.json"
            summary_path.write_text(json.dumps(passing_summary()), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "scripts/check_m27f_gate.py", "--summary", str(summary_path), "--compact"],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual(completed.returncode, 0)
        report = json.loads(completed.stdout)
        self.assertTrue(report["m2_7f_gate_passed"])
        self.assertFalse(report["summary_accepted_ignored"])


if __name__ == "__main__":
    unittest.main()
