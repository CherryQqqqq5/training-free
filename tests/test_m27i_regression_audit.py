from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.diagnose_m27i_regression_audit import evaluate_regression_audit, render_markdown


CATEGORY = "multi_turn_miss_param"


def _write_manifest(root: Path, selected: list[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "paired_subset_manifest.json").write_text(
        json.dumps({"category": CATEGORY, "selected_case_ids": selected}, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_case_report(root: Path) -> None:
    rows = [
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
            "repair_kinds": ["resolve_contextual_string_arg"],
            "case_fixed": True,
            "case_regressed": False,
        },
        {
            "case_id": "case_regressed",
            "baseline_success": True,
            "candidate_success": False,
            "policy_plan_activated": True,
            "selected_next_tool": "cat",
            "next_tool_emitted": True,
            "recommended_tool_match": False,
            "raw_normalized_arg_match": False,
            "final_normalized_arg_match": False,
            "repair_kinds": [],
            "case_fixed": False,
            "case_regressed": True,
        },
        {
            "case_id": "case_stable",
            "baseline_success": False,
            "candidate_success": False,
            "policy_plan_activated": True,
            "selected_next_tool": "mkdir",
            "next_tool_emitted": True,
            "recommended_tool_match": True,
            "raw_normalized_arg_match": False,
            "final_normalized_arg_match": False,
            "repair_kinds": [],
            "case_fixed": False,
            "case_regressed": False,
        },
    ]
    with (root / "subset_case_report.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _request(case_id: str) -> dict:
    return {
        "input": [{"role": "user", "content": f"Please handle {case_id}.txt"}],
        "tools": [
            {"type": "function", "function": {"name": "cat", "parameters": {"type": "object"}}},
            {"type": "function", "function": {"name": "touch", "parameters": {"type": "object"}}},
            {"type": "function", "function": {"name": "mkdir", "parameters": {"type": "object"}}},
        ],
    }


def _write_trace(root: Path, run: str, case_id: str, index: int, *, validation: dict | None = None, tool: str | None = None) -> None:
    trace_dir = root / run / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    output = [] if tool is None else [{"type": "function_call", "name": tool, "arguments": "{}"}]
    payload = {
        "request_original": _request(case_id),
        "request": _request(case_id),
        "final_response": {"output": output},
        "validation": validation or {},
    }
    (trace_dir / f"{case_id}-{index}.json").write_text(json.dumps(payload), encoding="utf-8")


class M27iRegressionAuditTests(unittest.TestCase):
    def test_audit_classifies_fixed_and_regressed_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            selected = ["case_fixed", "case_regressed", "case_stable"]
            _write_manifest(root, selected)
            _write_case_report(root)
            for case_id in selected:
                _write_trace(root, "baseline", case_id, 0, tool="cat")
            _write_trace(
                root,
                "candidate",
                "case_fixed",
                0,
                tool="touch",
                validation={
                    "next_tool_plan_activated": True,
                    "selected_next_tool": "touch",
                    "selected_action_candidate": {
                        "tool": "touch",
                        "args": {"file_name": "case_fixed.txt"},
                        "binding_source": "explicit_literal",
                        "arg_bindings": {"file_name": {"source": "explicit_literal", "value": "case_fixed.txt"}},
                    },
                    "repair_kinds": ["resolve_contextual_string_arg"],
                },
            )
            _write_trace(
                root,
                "candidate",
                "case_regressed",
                0,
                tool="cat",
                validation={
                    "next_tool_plan_activated": True,
                    "selected_next_tool": "cat",
                    "selected_action_candidate": {
                        "tool": "cat",
                        "args": {"file_name": "wrong.txt"},
                        "binding_source": "prior_tool_output.matches[0]|basename",
                        "arg_bindings": {"file_name": {"source": "prior_tool_output.matches[0]|basename", "value": "wrong.txt"}},
                    },
                },
            )
            _write_trace(root, "candidate", "case_stable", 0, tool="mkdir", validation={"next_tool_plan_activated": True})

            report = evaluate_regression_audit(root)

        self.assertTrue(report["m2_7i_regression_audit_passed"])
        self.assertEqual(report["regressed_cases"], ["case_regressed"])
        self.assertEqual(report["fixed_cases"], ["case_fixed"])
        regressed = next(case for case in report["cases"] if case["case_id"] == "case_regressed")
        self.assertIn("over_actuation", regressed["failure_layers"])
        self.assertIn("wrong_next_tool", regressed["failure_layers"])
        self.assertEqual(regressed["binding_risk"], "prior_output_binding_not_realized")
        fixed = next(case for case in report["cases"] if case["case_id"] == "case_fixed")
        self.assertIn("explicit_literal_binding", fixed["success_conditions"])
        self.assertIn("resolve_contextual_string_arg", fixed["repair_kinds"])
        self.assertIn("case_regressed", render_markdown(report))


if __name__ == "__main__":
    unittest.main()
