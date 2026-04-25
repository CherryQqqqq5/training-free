from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.diagnose_m27l_exact_tool_choice_trajectory import evaluate_exact_tool_choice_trajectory, render_markdown


def _write_manifest(root: Path, selected: list[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "paired_subset_manifest.json").write_text(
        json.dumps({"category": "multi_turn_miss_param", "selected_case_ids": selected}, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_result_and_score(root: Path, run: str, selected: list[str]) -> None:
    result_dir = root / run / "bfcl" / "result" / "demo" / "multi_turn"
    score_dir = root / run / "bfcl" / "score" / "demo" / "multi_turn"
    result_dir.mkdir(parents=True, exist_ok=True)
    score_dir.mkdir(parents=True, exist_ok=True)
    result_path = result_dir / "BFCL_v4_multi_turn_miss_param_result.json"
    score_path = score_dir / "BFCL_v4_multi_turn_miss_param_score.json"
    with result_path.open("w", encoding="utf-8") as handle:
        for case_id in selected:
            handle.write(json.dumps({"id": case_id, "result": "ok"}) + "\n")
    with score_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"total_count": len(selected), "correct_count": 0}) + "\n")
        for case_id in selected:
            handle.write(json.dumps({"id": case_id, "valid": False, "prompt": {"question": [[{"role": "user", "content": f"Handle {case_id}"}]]}}) + "\n")


def _write_case_report(root: Path) -> None:
    rows = [
        {
            "case_id": "case_regressed_exact",
            "baseline_success": True,
            "candidate_success": False,
            "policy_plan_activated": True,
            "selected_next_tool": "cat",
            "next_tool_emitted": True,
            "recommended_tool_match": True,
            "raw_normalized_arg_match": True,
            "final_normalized_arg_match": True,
            "case_fixed": False,
            "case_regressed": True,
        },
        {
            "case_id": "case_local_match_fail",
            "baseline_success": False,
            "candidate_success": False,
            "policy_plan_activated": True,
            "selected_next_tool": "touch",
            "next_tool_emitted": True,
            "recommended_tool_match": True,
            "raw_normalized_arg_match": True,
            "final_normalized_arg_match": True,
            "case_fixed": False,
            "case_regressed": False,
        },
        {
            "case_id": "case_tool_mismatch",
            "baseline_success": False,
            "candidate_success": False,
            "policy_plan_activated": True,
            "selected_next_tool": "mkdir",
            "next_tool_emitted": True,
            "recommended_tool_match": False,
            "raw_normalized_arg_match": False,
            "final_normalized_arg_match": False,
            "case_fixed": False,
            "case_regressed": False,
        },
        {
            "case_id": "case_missing_trace",
            "baseline_success": False,
            "candidate_success": False,
            "policy_plan_activated": True,
            "selected_next_tool": "cat",
            "next_tool_emitted": False,
            "recommended_tool_match": False,
            "raw_normalized_arg_match": False,
            "final_normalized_arg_match": False,
            "case_fixed": False,
            "case_regressed": False,
        },
    ]
    with (root / "subset_case_report.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _trace(tool: str, *, exact: bool = False, guidance: bool = False, selected_tool: str | None = None, case_id: str = "case prompt") -> dict:
    selected_tool = selected_tool or tool
    patches = []
    if guidance:
        patches.append(f"prompt_injector:Policy selected next tool: call `{selected_tool}` next with grounded arguments {{}}.")
    if exact:
        patches.append(f"tool_choice:function(policy_next_tool)={selected_tool}")
    request = {"messages": [{"role": "user", "content": "case prompt"}]}
    if exact:
        request["tool_choice"] = {"type": "function", "function": {"name": selected_tool}}
    return {
        "request_original": {"input": [{"role": "user", "content": f"Handle {case_id}"}]},
        "request": request,
        "final_response": {"output": [{"type": "function_call", "name": tool, "arguments": json.dumps({"path": "x.txt"})}]},
        "validation": {
            "next_tool_plan_activated": True,
            "selected_next_tool": selected_tool,
            "selected_action_candidate": {"tool": selected_tool, "args": {"path": "x.txt"}},
            "request_patches": patches,
        },
    }


def _write_trace(root: Path, run: str, case_id: str, index: int, payload: dict) -> None:
    trace_dir = root / run / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    (trace_dir / f"{case_id}-{index}.json").write_text(json.dumps(payload), encoding="utf-8")


class M27lExactToolChoiceTrajectoryTests(unittest.TestCase):
    def test_classifies_exact_overconstraint_local_match_and_divergence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            selected = ["case_regressed_exact", "case_local_match_fail", "case_tool_mismatch", "case_missing_trace"]
            _write_manifest(root, selected)
            _write_result_and_score(root, "baseline", selected)
            _write_result_and_score(root, "candidate", selected)
            _write_case_report(root)
            for case_id in selected:
                _write_trace(root, "baseline", case_id, 0, _trace("touch", case_id=case_id))
            _write_trace(root, "candidate", "case_regressed_exact", 0, _trace("cat", exact=True, guidance=True, case_id="case_regressed_exact"))
            _write_trace(root, "candidate", "case_local_match_fail", 0, _trace("touch", guidance=True, case_id="case_local_match_fail"))
            _write_trace(root, "candidate", "case_tool_mismatch", 0, _trace("mkdir", guidance=True, case_id="case_tool_mismatch"))

            report = evaluate_exact_tool_choice_trajectory(root)

        self.assertTrue(report["m2_7l_exact_tool_choice_trajectory_diagnostic_completed"])
        self.assertEqual(report["failure_layer_distribution"]["exact_tool_choice_overconstraint"], 1)
        self.assertEqual(report["failure_layer_distribution"]["local_tool_arg_match_but_trajectory_fail"], 1)
        self.assertEqual(report["failure_layer_distribution"]["selected_action_not_expected_trajectory"], 1)
        self.assertEqual(report["failure_layer_distribution"]["trace_mapping_incomplete"], 1)
        exact_case = next(case for case in report["cases"] if case["case_id"] == "case_regressed_exact")
        self.assertTrue(exact_case["whether_exact_tool_choice_was_applied"])
        self.assertEqual(exact_case["first_divergent_step"], {"step_index": 0, "baseline_tool": "touch", "candidate_tool": "cat"})
        self.assertIn("M2.7l", render_markdown(report))

    def test_missing_candidate_prompt_prefix_trace_marks_diagnostic_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            selected = ["case_missing_trace"]
            _write_manifest(root, selected)
            _write_result_and_score(root, "baseline", selected)
            _write_result_and_score(root, "candidate", selected)
            _write_case_report(root)
            _write_trace(root, "baseline", "case_missing_trace", 0, _trace("cat", case_id="case_missing_trace"))
            report = evaluate_exact_tool_choice_trajectory(root)

        self.assertEqual(report["case_level_evidence"], "diagnostic_only")
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "trace_mapping_incomplete")
        self.assertEqual(report["missing_candidate_prompt_prefix_trace_ids"], ["case_missing_trace"])


if __name__ == "__main__":
    unittest.main()
