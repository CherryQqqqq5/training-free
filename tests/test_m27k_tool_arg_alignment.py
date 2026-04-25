from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.diagnose_m27k_tool_arg_alignment import evaluate_tool_arg_alignment, render_markdown


def _write_manifest(root: Path, selected: list[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "paired_subset_manifest.json").write_text(
        json.dumps({"category": "multi_turn_miss_param", "selected_case_ids": selected}, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_case_report(root: Path) -> None:
    rows = [
        {
            "case_id": "case_tool_mismatch",
            "baseline_success": False,
            "candidate_success": False,
            "policy_plan_activated": True,
            "selected_next_tool": "cat",
            "next_tool_emitted": True,
            "recommended_tool_match": False,
            "raw_normalized_arg_match": False,
            "final_normalized_arg_match": False,
            "case_fixed": False,
            "case_regressed": False,
            "repair_kinds": [],
        },
        {
            "case_id": "case_arg_mismatch",
            "baseline_success": False,
            "candidate_success": False,
            "policy_plan_activated": True,
            "selected_next_tool": "touch",
            "next_tool_emitted": True,
            "recommended_tool_match": True,
            "raw_normalized_arg_match": False,
            "final_normalized_arg_match": False,
            "case_fixed": False,
            "case_regressed": False,
            "repair_kinds": ["resolve_contextual_string_arg"],
        },
        {
            "case_id": "case_continuation",
            "baseline_success": False,
            "candidate_success": False,
            "policy_plan_activated": True,
            "selected_next_tool": "cat",
            "next_tool_emitted": True,
            "recommended_tool_match": True,
            "raw_normalized_arg_match": True,
            "final_normalized_arg_match": True,
            "case_fixed": False,
            "case_regressed": False,
            "repair_kinds": [],
        },
        {
            "case_id": "case_fixed",
            "baseline_success": False,
            "candidate_success": True,
            "policy_plan_activated": True,
            "selected_next_tool": "touch",
            "next_tool_emitted": True,
            "recommended_tool_match": True,
            "raw_normalized_arg_match": True,
            "final_normalized_arg_match": True,
            "case_fixed": True,
            "case_regressed": False,
            "repair_kinds": [],
        },
        {
            "case_id": "case_inactive",
            "baseline_success": False,
            "candidate_success": False,
            "policy_plan_activated": False,
            "selected_next_tool": None,
            "next_tool_emitted": None,
            "recommended_tool_match": None,
            "raw_normalized_arg_match": None,
            "final_normalized_arg_match": None,
            "case_fixed": False,
            "case_regressed": False,
            "repair_kinds": [],
        },
    ]
    with (root / "subset_case_report.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _write_trace(root: Path, case_id: str, *, tool: str, candidate: dict | None = None) -> None:
    trace_dir = root / "candidate" / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "request_original": {"input": [{"role": "user", "content": f"Handle {case_id}.txt"}]},
        "request": {"input": [{"role": "user", "content": f"Handle {case_id}.txt"}]},
        "final_response": {"output": [{"type": "function_call", "name": tool, "arguments": "{}"}]},
        "validation": {
            "next_tool_plan_activated": True,
            "selected_next_tool": tool,
            "selected_action_candidate": candidate or {"tool": tool, "args": {"file_name": f"{case_id}.txt"}, "binding_source": "explicit_literal"},
        },
    }
    (trace_dir / f"{case_id}-0.json").write_text(json.dumps(payload), encoding="utf-8")


def _preflight(*, guidance: bool = True, exact: bool = True) -> dict:
    cases = []
    for case_id, tool in [("case_tool_mismatch", "cat"), ("case_arg_mismatch", "touch"), ("case_continuation", "cat"), ("case_fixed", "touch")]:
        patches = []
        if guidance:
            patches.append(f"prompt_injector:Policy selected next tool: call `{tool}` next with grounded arguments {{}}.")
        tool_choice = {"type": "function", "function": {"name": tool}} if exact else "required"
        cases.append(
            {
                "case_id": case_id,
                "after_guard_plan": {
                    "activated": True,
                    "selected_tool": tool,
                    "selected_action_candidate": {"tool": tool, "args": {"file_name": f"{case_id}.txt"}},
                    "request_patches": patches,
                    "patched_tool_choice": tool_choice,
                },
            }
        )
    return {
        "candidate_rules_schema_local": True,
        "plan_activated_count_after_guard": 12,
        "dominant_selected_next_tool_rate_after_guard": 0.5,
        "fixed_cases_guard_status": {"case_fixed": "guard_kept"},
        "regressed_cases_guard_status": {},
        "cases": cases,
    }


class M27kToolArgAlignmentTests(unittest.TestCase):
    def test_classifies_tool_arg_and_continuation_layers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            selected = ["case_tool_mismatch", "case_arg_mismatch", "case_continuation", "case_fixed", "case_inactive"]
            _write_manifest(root, selected)
            _write_case_report(root)
            for case_id in selected[:-1]:
                _write_trace(root, case_id, tool="touch" if "arg" in case_id or "fixed" in case_id else "cat")

            report = evaluate_tool_arg_alignment(root, preflight_report=_preflight())

        self.assertTrue(report["m2_7k_tool_arg_alignment_passed"])
        self.assertEqual(report["classification_counts"]["actuation_or_prompt_guidance"], 1)
        self.assertEqual(report["classification_counts"]["argument_realization"], 1)
        self.assertEqual(report["classification_counts"]["trajectory_continuation_or_final_answer"], 1)
        self.assertEqual(report["classification_counts"]["not_activated_context"], 1)
        tool_case = next(case for case in report["cases"] if case["case_id"] == "case_tool_mismatch")
        self.assertEqual(tool_case["classification"], "actuation_or_prompt_guidance")
        arg_case = next(case for case in report["cases"] if case["case_id"] == "case_arg_mismatch")
        self.assertEqual(arg_case["repair_kinds"], ["resolve_contextual_string_arg"])
        self.assertIn("M2.7k", render_markdown(report))

    def test_preflight_fails_without_action_specific_guidance_but_not_without_exact_tool_choice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            selected = ["case_tool_mismatch", "case_arg_mismatch", "case_continuation", "case_fixed", "case_inactive"]
            _write_manifest(root, selected)
            _write_case_report(root)
            report = evaluate_tool_arg_alignment(root, preflight_report=_preflight(guidance=False, exact=True))
            exact_report = evaluate_tool_arg_alignment(root, preflight_report=_preflight(guidance=True, exact=False))

        self.assertFalse(report["m2_7k_tool_arg_alignment_passed"])
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "action_specific_guidance_coverage")
        self.assertTrue(exact_report["m2_7k_tool_arg_alignment_passed"])
        self.assertEqual(exact_report["exact_tool_choice_coverage"], 0.0)


if __name__ == "__main__":
    unittest.main()
