from __future__ import annotations

import unittest

from scripts.check_m27i_guard_preflight import render_markdown, summarize_guard_preflight


REGRESSED = ["multi_turn_miss_param_9", "multi_turn_miss_param_21", "multi_turn_miss_param_36"]
FIXED = ["multi_turn_miss_param_31", "multi_turn_miss_param_39"]


def _plan(
    *,
    activated: bool,
    tool: str | None = None,
    candidate: bool = True,
    blocked_reason: str | None = None,
    rejected_reason: str | None = None,
) -> dict:
    payload = {
        "activated": activated,
        "blocked_reason": blocked_reason or ("activated" if activated else "action_candidate_guard_rejected"),
        "selected_tool": tool if activated else None,
        "selected_action_candidate": {"tool": tool, "args": {"path": f"{tool}.txt"}} if activated and candidate and tool else None,
        "action_candidate_guard": {"accepted": True, "reason": "strong_explicit_literal_binding", "risk_flags": []} if activated and candidate and tool else None,
        "rejected_action_candidates": [],
    }
    if rejected_reason:
        payload["rejected_action_candidates"].append(
            {"tool": tool or "cat", "guard": {"accepted": False, "reason": rejected_reason, "risk_flags": [rejected_reason]}}
        )
    return payload


def _case(
    case_id: str,
    *,
    before_tool: str = "cat",
    after_tool: str | None = "cat",
    after_activated: bool = True,
    after_candidate: bool = True,
    after_blocked_reason: str | None = None,
    rejected_reason: str | None = None,
) -> dict:
    return {
        "case_id": case_id,
        "before_guard_plan": _plan(activated=True, tool=before_tool),
        "after_guard_plan": _plan(
            activated=after_activated,
            tool=after_tool,
            candidate=after_candidate,
            blocked_reason=after_blocked_reason,
            rejected_reason=rejected_reason,
        ),
    }


def _base_cases() -> list[dict]:
    cases = [
        _case(REGRESSED[0], after_activated=False, after_tool=None, rejected_reason="weak_arg_binding_evidence"),
        _case(REGRESSED[1], after_activated=False, after_tool=None, rejected_reason="prior_output_state_unavailable"),
        _case(REGRESSED[2], after_tool="touch"),
        _case(FIXED[0], before_tool="touch", after_tool="touch"),
        _case(FIXED[1], before_tool="mkdir", after_activated=False, after_tool=None, rejected_reason="weak_cwd_or_listing_binding"),
    ]
    tools = ["cat"] * 6 + ["touch"] * 5 + ["mkdir"] * 4
    for index, tool in enumerate(tools):
        cases.append(_case(f"stable_{index}", before_tool=tool, after_tool=tool))
    return cases


def _report(cases: list[dict], *, schema_local: bool = True, **kwargs) -> dict:
    return summarize_guard_preflight(
        cases,
        selected_case_count=len(cases),
        regressed_cases=REGRESSED,
        fixed_cases=FIXED,
        schema_local=schema_local,
        **kwargs,
    )


class M27iGuardPreflightTests(unittest.TestCase):
    def test_gate_passes_when_guard_rejects_regressions_and_keeps_fixed_case(self) -> None:
        report = _report(_base_cases())

        self.assertTrue(report["m2_7i_guard_preflight_passed"])
        self.assertEqual(report["guard_rejects_regressed_cases"], 2)
        self.assertEqual(report["guard_keeps_fixed_cases"], 1)
        self.assertEqual(report["plan_activated_count_after_guard"], 17)
        self.assertLessEqual(report["dominant_selected_next_tool_rate_after_guard"], 0.8)
        self.assertEqual(report["regressed_cases_guard_status"][REGRESSED[0]], "guard_rejected")
        self.assertEqual(report["fixed_cases_guard_status"][FIXED[0]], "guard_kept")
        self.assertIn("weak_arg_binding_evidence", report["guard_reason_distribution"])
        self.assertIn("prior_output_state_unavailable", report["all_candidate_rejection_reason_distribution"])
        self.assertIn("weak_cwd_or_listing_binding", report["top_candidate_rejection_reason_distribution"])
        self.assertIn("strong_explicit_literal_binding", report["case_final_guard_reason_distribution"])
        self.assertEqual(report["selected_next_tool_count_after_guard"], 3)
        rejected = next(case for case in report["cases"] if case["case_id"] == REGRESSED[0])
        self.assertEqual(rejected["top_candidate_rejection_reason"], "weak_arg_binding_evidence")
        self.assertEqual(rejected["case_final_guard_reason"], "weak_arg_binding_evidence")
        kept = next(case for case in report["cases"] if case["case_id"] == FIXED[0])
        self.assertEqual(kept["case_final_guard_reason"], "strong_explicit_literal_binding")
        self.assertIn("M2.7i Guard Preflight", render_markdown(report))

    def test_fails_when_too_few_regressed_cases_are_rejected(self) -> None:
        cases = _base_cases()
        cases[1] = _case(REGRESSED[1], after_tool="cat")

        report = _report(cases)

        self.assertFalse(report["m2_7i_guard_preflight_passed"])
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "guard_rejects_regressed_cases")

    def test_fails_when_fixed_cases_are_not_kept(self) -> None:
        cases = _base_cases()
        cases[3] = _case(FIXED[0], after_activated=False, after_tool=None, rejected_reason="weak_arg_binding_evidence")

        report = _report(cases)

        self.assertFalse(report["m2_7i_guard_preflight_passed"])
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "guard_keeps_fixed_cases")

    def test_fails_when_after_guard_activation_is_outside_bounds(self) -> None:
        low_cases = _base_cases()[:9]
        low_report = _report(low_cases)
        self.assertEqual(low_report["diagnostic"]["first_failed_criterion"], "plan_activated_count_after_guard_min")

        high_cases = _base_cases() + [_case(f"extra_{index}", after_tool="touch") for index in range(9)]
        high_report = _report(high_cases)
        self.assertEqual(high_report["diagnostic"]["first_failed_criterion"], "plan_activated_count_after_guard_max")

    def test_fails_when_dominant_tool_rate_is_too_high(self) -> None:
        cases = _base_cases()
        for row in cases:
            if row["after_guard_plan"].get("activated"):
                row["after_guard_plan"]["selected_tool"] = "cat"
                row["after_guard_plan"]["selected_action_candidate"] = {"tool": "cat", "args": {"path": "same.txt"}}

        report = _report(cases)

        self.assertFalse(report["m2_7i_guard_preflight_passed"])
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "dominant_selected_next_tool_rate_after_guard")

    def test_fails_when_schema_local_is_false(self) -> None:
        report = _report(_base_cases(), schema_local=False)

        self.assertFalse(report["m2_7i_guard_preflight_passed"])
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "candidate_rules_schema_local")


if __name__ == "__main__":
    unittest.main()
