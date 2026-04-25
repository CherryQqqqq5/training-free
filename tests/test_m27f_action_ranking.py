from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.diagnose_m27f_action_ranking import evaluate_action_ranking_audit
from scripts.diagnose_m27f_activation_predicates import SOURCE_TRACE_RUNTIME


CATEGORY = "multi_turn_miss_param"


def _write_activation_audit(root: Path, selected: list[str]) -> Path:
    cases = [
        {
            "case_id": case_id,
            "source_trace_id": f"{case_id}__000__trace-{index}",
            "activated": True,
            "selected_next_tool": "cat",
        }
        for index, case_id in enumerate(selected)
    ]
    path = root / "m27g_activation_audit.json"
    path.write_text(
        json.dumps(
            {
                "category": CATEGORY,
                "trace_state_primary_source": SOURCE_TRACE_RUNTIME,
                "cases_by_state": {SOURCE_TRACE_RUNTIME: cases},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _bfcl_tool(name: str) -> dict:
    return {
        "name": name,
        "description": f"{name} tool",
        "parameters": {"type": "object", "properties": {"target": {"type": "string"}}},
    }


def _dataset_rows(selected: list[str]) -> list[dict]:
    return [
        {
            "id": case_id,
            "question": [[{"role": "user", "content": f"Please handle 'item_{index}.txt'."}]],
            "function": [_bfcl_tool("cat"), _bfcl_tool("mkdir"), _bfcl_tool("touch")],
        }
        for index, case_id in enumerate(selected)
    ]


def _write_rule(rules_dir: Path, *, all_cat: bool = False) -> None:
    rules_dir.mkdir(parents=True, exist_ok=True)
    candidates = [
        {
            "tool": "cat",
            "args": {"target": "item_0.txt"},
            "arg_bindings": {"target": {"source": "explicit_literal", "value": "item_0.txt"}},
            "recommended_tools": ["cat"],
        }
    ]
    recommended = ["cat"]
    if not all_cat:
        candidates.extend(
            [
                {
                    "tool": "mkdir",
                    "args": {"target": "archive"},
                    "arg_bindings": {"target": {"source": "explicit_literal", "value": "archive"}},
                    "recommended_tools": ["mkdir"],
                },
                {
                    "tool": "touch",
                    "args": {"target": "todo.txt"},
                    "arg_bindings": {"target": {"source": "explicit_literal", "value": "todo.txt"}},
                    "recommended_tools": ["touch"],
                },
            ]
        )
        recommended = ["cat", "mkdir", "touch"]
    (rules_dir / "rule.yaml").write_text(
        yaml.safe_dump(
            {
                "patch_id": "m27h_test",
                "rules": [
                    {
                        "rule_id": "rule_m27h_test",
                        "priority": 100,
                        "enabled": True,
                        "trigger": {
                            "tool_names": [],
                            "error_types": ["actionable_no_tool_decision"],
                            "request_predicates": ["tools_available", "prior_explicit_literals_present"],
                        },
                        "scope": {"tool_names": [], "patch_sites": ["policy_executor", "prompt_injector"]},
                        "action": {
                            "decision_policy": {
                                "request_predicates": ["tools_available", "prior_explicit_literals_present"],
                                "recommended_tools": recommended,
                                "action_candidates": candidates,
                                "next_tool_policy": {
                                    "activation_predicates": ["tools_available", "prior_explicit_literals_present"],
                                    "recommended_tools": recommended,
                                    "tool_choice_mode": "required",
                                    "confidence": 0.8,
                                },
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _request_for(index: int) -> dict:
    if index % 3 == 0:
        content = "Read 'item_0.txt' and show me the content."
    elif index % 3 == 1:
        content = "Create a directory named 'archive'."
    else:
        content = "Create an empty file named 'todo.txt'."
    return {
        "model": "demo-model",
        "messages": [
            {"role": "user", "content": content},
            {"role": "tool", "content": json.dumps({"current_working_directory": "/tmp", "matches": ["item_0.txt"]})},
        ],
        "tools": [_bfcl_tool("cat"), _bfcl_tool("mkdir"), _bfcl_tool("touch")],
    }


def _write_trace(trace_dir: Path, case_id: str, index: int, *, emitted_tool: str | None = None) -> None:
    trace_dir.mkdir(parents=True, exist_ok=True)
    output = []
    if emitted_tool:
        output.append({"type": "function_call", "name": emitted_tool, "arguments": "{}"})
    payload = {
        "request_original": _request_for(index),
        "request": _request_for(index),
        "final_response": {"output": output},
        "validation": {"failure_labels": ["(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)"]},
    }
    (trace_dir / f"{case_id}__000__trace-{index}.json").write_text(json.dumps(payload), encoding="utf-8")


class M27fActionRankingAuditTests(unittest.TestCase):
    def test_action_ranking_reports_components_and_expected_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            selected = ["case_0", "case_1", "case_2"]
            activation = _write_activation_audit(root, selected)
            rules_dir = root / "rules"
            traces = root / "traces"
            _write_rule(rules_dir)
            for index, case_id in enumerate(selected):
                _write_trace(traces, case_id, index, emitted_tool=["cat", "mkdir", "touch"][index])

            report = evaluate_action_ranking_audit(
                activation,
                rules_dir=rules_dir,
                runtime_config=root / "runtime.yaml",
                source_traces=traces,
                min_trace_activation_count=1,
                min_tool_count=3,
                min_proxy_match_rate=0.5,
                dataset_rows=_dataset_rows(selected),
            )

        self.assertTrue(report["m2_7h_action_ranking_passed"])
        first = report["cases"][0]
        self.assertEqual(first["expected_next_tool_proxy"]["tool"], "cat")
        self.assertIn("literal_score", first["top_k_candidates"][0]["candidate_rank_scores"])
        self.assertIn("prior_tool_output_keys", first)
        self.assertIn("explicit_literals", first)

    def test_action_ranking_fails_when_dominant_tool_rate_is_high(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            selected = [f"case_{index}" for index in range(5)]
            activation = _write_activation_audit(root, selected)
            rules_dir = root / "rules"
            traces = root / "traces"
            _write_rule(rules_dir, all_cat=True)
            for index, case_id in enumerate(selected):
                _write_trace(traces, case_id, index, emitted_tool="cat")

            report = evaluate_action_ranking_audit(
                activation,
                rules_dir=rules_dir,
                runtime_config=root / "runtime.yaml",
                source_traces=traces,
                min_trace_activation_count=1,
                min_tool_count=3,
                dataset_rows=_dataset_rows(selected),
            )

        self.assertFalse(report["m2_7h_action_ranking_passed"])
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "dominant_selected_next_tool_rate")
        self.assertEqual(report["dominant_selected_next_tool_rate"], 1.0)
        self.assertTrue(any(case["why_cat_won"] for case in report["cases"]))


if __name__ == "__main__":
    unittest.main()
