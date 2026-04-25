from __future__ import annotations

import unittest

from scripts.check_m27m_guidance_only_readiness import render_markdown, summarize_guidance_only_readiness


def _trace(passed: bool = True) -> dict:
    return {
        "m2_7l_trace_completeness_passed": passed,
        "case_level_gate_allowed": passed,
        "missing_trace_ids": {} if passed else {"baseline": [], "candidate": ["multi_turn_miss_param_43"]},
        "diagnostic": {"first_failed_criterion": None if passed else "missing_prompt_prefix_trace_ids"},
    }


def _case(case_id: str, tool: str, *, exact: bool = False, guidance: bool = True) -> dict:
    patches = []
    if guidance:
        patches.append(f"prompt_injector:Policy selected next tool: call `{tool}` next with grounded arguments {{}}.")
    tool_choice = {"type": "function", "function": {"name": tool}} if exact else None
    return {
        "case_id": case_id,
        "after_guard_plan": {
            "activated": True,
            "selected_tool": tool,
            "selected_action_candidate": {"tool": tool, "args": {"path": f"{case_id}.txt"}},
            "request_patches": patches,
            "patched_tool_choice": tool_choice,
        },
    }


def _guard(*, mode: str = "guidance_only", exact_case: str | None = None, exact_tool: str = "cat", guidance: bool = True, activated_count: int = 13, dominant_cat_count: int = 8) -> dict:
    cases = []
    for index in range(activated_count):
        tool = "cat" if index < dominant_cat_count else "touch"
        case_id = f"case_{index}"
        exact = exact_case == case_id
        if exact:
            tool = exact_tool
        cases.append(_case(case_id, tool, exact=exact, guidance=guidance))
    return {
        "selected_case_count": 30,
        "m2_7i_guard_preflight_passed": True,
        "exact_next_tool_choice_mode": mode,
        "exact_tool_choice_trajectory_sensitive_tools": ["cat", "touch", "mkdir"],
        "plan_activated_count_after_guard": activated_count,
        "dominant_selected_next_tool_rate_after_guard": dominant_cat_count / activated_count if activated_count else 0.0,
        "selected_next_tool_distribution_after_guard": {"cat": dominant_cat_count, "touch": activated_count - dominant_cat_count},
        "regressed_cases_guard_status": {"case_0": "guard_kept"},
        "cases": cases,
    }


class M27mGuidanceOnlyReadinessTests(unittest.TestCase):
    def test_guidance_only_passes_when_trace_and_runtime_conditions_hold(self) -> None:
        report = summarize_guidance_only_readiness(guard_preflight=_guard(), trace_preflight=_trace())

        self.assertTrue(report["m2_7m_guidance_only_readiness_passed"])
        self.assertTrue(report["m2_7m_preflight_passed"])
        self.assertEqual(report["action_specific_guidance_coverage"], 1.0)
        self.assertEqual(report["exact_tool_choice_coverage"], 0.0)
        self.assertEqual(report["trajectory_sensitive_exact_forcing_count"], 0)
        self.assertIn("M2.7m", render_markdown(report))

    def test_trace_completeness_failure_blocks_combined_preflight_but_not_guidance_readiness(self) -> None:
        report = summarize_guidance_only_readiness(guard_preflight=_guard(), trace_preflight=_trace(False))

        self.assertTrue(report["m2_7m_guidance_only_readiness_passed"])
        self.assertFalse(report["m2_7m_preflight_passed"])
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "trace_completeness")
        self.assertEqual(report["diagnostic"]["trace_first_failed_criterion"], "missing_prompt_prefix_trace_ids")

    def test_missing_action_specific_guidance_fails(self) -> None:
        report = summarize_guidance_only_readiness(guard_preflight=_guard(guidance=False), trace_preflight=_trace())

        self.assertFalse(report["m2_7m_guidance_only_readiness_passed"])
        self.assertEqual(report["diagnostic"]["guidance_only_first_failed_criterion"], "action_specific_guidance_coverage")

    def test_exact_tool_choice_or_wrong_mode_fails(self) -> None:
        exact_report = summarize_guidance_only_readiness(guard_preflight=_guard(exact_case="case_0", exact_tool="cat"), trace_preflight=_trace())
        mode_report = summarize_guidance_only_readiness(guard_preflight=_guard(mode="exact_tool_when_single_step_confident"), trace_preflight=_trace())

        self.assertFalse(exact_report["m2_7m_guidance_only_readiness_passed"])
        self.assertEqual(exact_report["trajectory_sensitive_exact_forcing_count"], 1)
        self.assertEqual(exact_report["regressed_exact_forcing_cases"], ["case_0"])
        self.assertEqual(exact_report["diagnostic"]["guidance_only_first_failed_criterion"], "exact_tool_choice_coverage")
        self.assertFalse(mode_report["m2_7m_guidance_only_readiness_passed"])
        self.assertEqual(mode_report["diagnostic"]["guidance_only_first_failed_criterion"], "exact_next_tool_choice_mode")

    def test_activation_bounds_and_dominant_rate_fail(self) -> None:
        low_report = summarize_guidance_only_readiness(guard_preflight=_guard(activated_count=9, dominant_cat_count=6), trace_preflight=_trace())
        high_report = summarize_guidance_only_readiness(guard_preflight=_guard(activated_count=21, dominant_cat_count=10), trace_preflight=_trace())
        dominant_report = summarize_guidance_only_readiness(guard_preflight=_guard(activated_count=13, dominant_cat_count=12), trace_preflight=_trace())

        self.assertEqual(low_report["diagnostic"]["guidance_only_first_failed_criterion"], "plan_activated_count_after_guard_min")
        self.assertEqual(high_report["diagnostic"]["guidance_only_first_failed_criterion"], "plan_activated_count_after_guard_max")
        self.assertEqual(dominant_report["diagnostic"]["guidance_only_first_failed_criterion"], "dominant_selected_next_tool_rate_after_guard")


if __name__ == "__main__":
    unittest.main()
