from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.diagnose_m27i_guard_calibration import evaluate_guard_calibration, render_markdown


def _plan(*, activated: bool, tool: str | None, reason: str | None = None, rejected_reason: str | None = None) -> dict:
    plan = {
        "activated": activated,
        "selected_tool": tool if activated else None,
        "blocked_reason": "activated" if activated else "action_candidate_guard_rejected",
        "selected_action_candidate": {"tool": tool, "args": {"path": f"{tool}.txt"}} if activated and tool else None,
        "action_candidate_guard": {"accepted": True, "reason": reason or "strong_explicit_literal_binding", "risk_flags": []} if activated else None,
        "rejected_action_candidates": [],
        "selected_candidate_rank_scores": {"literal_score": 10, "arg_binding_score": 12} if activated else None,
    }
    if rejected_reason:
        plan["rejected_action_candidates"].append(
            {
                "tool": tool or "cat",
                "args": {"path": "x.txt"},
                "guard": {"accepted": False, "reason": rejected_reason, "risk_flags": [rejected_reason]},
                "candidate_rank_scores": {"literal_score": 0, "arg_binding_score": 6},
            }
        )
    return plan


def _case(case_id: str, status: str, *, before: str, after: str | None, reason: str | None = None, rejected_reason: str | None = None) -> dict:
    activated = status in {"guard_kept", "guard_changed_tool"}
    return {
        "case_id": case_id,
        "guard_status": status,
        "request_state_source": "source_trace_runtime_request",
        "source_trace_id": f"{case_id}__trace",
        "before_guard_plan": _plan(activated=True, tool=before),
        "after_guard_plan": _plan(activated=activated, tool=after, reason=reason, rejected_reason=rejected_reason),
    }


class M27iGuardCalibrationTests(unittest.TestCase):
    def test_reports_false_negatives_false_positives_and_case_level_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            preflight = root / "m27i_guard_preflight.json"
            regression = root / "m27i_regression_audit.json"
            preflight.write_text(
                json.dumps(
                    {
                        "m2_7i_guard_preflight_passed": False,
                        "plan_activated_count_after_guard": 6,
                        "selected_next_tool_distribution_after_guard": {"cat": 5, "touch": 1},
                        "diagnostic": {"first_failed_criterion": "plan_activated_count_after_guard_min"},
                        "cases": [
                            _case("fixed_keep", "guard_kept", before="cat", after="cat", reason="strong_prior_output_binding", rejected_reason="weak_arg_binding_evidence"),
                            _case("fixed_reject", "guard_rejected", before="mkdir", after=None, rejected_reason="weak_arg_binding_evidence"),
                            _case("regressed_reject", "guard_rejected", before="touch", after=None, rejected_reason="weak_cwd_or_listing_binding"),
                            _case("regressed_keep", "guard_kept", before="cat", after="cat", reason="strong_explicit_literal_binding"),
                        ],
                    }
                ),
                encoding="utf-8",
            )
            regression.write_text(
                json.dumps({"fixed_cases": ["fixed_keep", "fixed_reject"], "regressed_cases": ["regressed_reject", "regressed_keep"]}),
                encoding="utf-8",
            )

            report = evaluate_guard_calibration(preflight, regression_audit_path=regression, artifact_root=root)

        self.assertEqual(report["fixed_cases_guard_false_negative"], ["fixed_reject"])
        self.assertEqual(report["regressed_cases_guard_false_positive"], ["regressed_keep"])
        self.assertEqual(report["case_level_guard_reason"]["fixed_reject"], "weak_arg_binding_evidence")
        self.assertEqual(report["case_level_guard_reason"]["fixed_keep"], "strong_prior_output_binding")
        self.assertIn("weak_cwd_or_listing_binding", report["top_candidate_rejection_reason_distribution"])
        self.assertIn("fixed_reject", report["top_rejected_candidate_by_case"])
        self.assertIn("fixed_keep", report["accepted_candidate_by_case"])
        self.assertIn("top_rejected", report["score_components_by_case"]["fixed_reject"])
        self.assertIn("increase_guard_recall_without_reenabling_weak_cwd_or_listing", report["calibration_recommendation"])
        self.assertIn("fixed_reject", render_markdown(report))


if __name__ == "__main__":
    unittest.main()
