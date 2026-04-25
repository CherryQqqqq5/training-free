from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.diagnose_m27f_activation_predicates import (
    SOURCE_TRACE_RUNTIME,
    evaluate_activation_predicate_audit,
)


CATEGORY = "multi_turn_miss_param"


def _write_manifest(root: Path, selected: list[str]) -> Path:
    path = root / "paired_subset_manifest.json"
    path.write_text(
        json.dumps({"category": CATEGORY, "selected_case_ids": selected}, indent=2) + "\n",
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
    rows = []
    for index, case_id in enumerate(selected):
        if index % 2 == 0:
            content = f"Please read 'file_{index}.txt' and show me the content."
        else:
            content = f"Please create a directory named 'dir_{index}'."
        rows.append(
            {
                "id": case_id,
                "question": [[{"role": "user", "content": content}]],
                "function": [_bfcl_tool("cat"), _bfcl_tool("mkdir")],
            }
        )
    return rows



def _trajectory_candidate(candidate: dict) -> dict:
    tool = str(candidate.get("tool") or (candidate.get("recommended_tools") or [""])[0])
    args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
    target_arg = next(iter(args), "target")
    kind_by_tool = {
        "cat": "file_content",
        "touch": "file_exists",
        "mkdir": "directory_exists",
        "grep": "matches",
        "find": "matches",
        "mv": "target_path_changed",
        "cp": "target_path_changed",
        "move_file": "target_path_changed",
        "copy_file": "target_path_changed",
    }
    kind = kind_by_tool.get(tool, "target_path_changed")
    expected_state_key = (
        "file_content"
        if kind == "file_content"
        else "matches"
        if kind == "matches"
        else "current_directory_content"
    )
    enriched = dict(candidate)
    enriched.setdefault(
        "postcondition",
        {
            "kind": kind,
            "expected_state_key": expected_state_key,
            "target_arg": target_arg,
            "confidence": 0.8,
        },
    )
    enriched.setdefault("trajectory_risk_score", 2 if tool in {"cat", "touch", "mkdir"} else 0)
    enriched.setdefault(
        "trajectory_risk_flags",
        ["trajectory_sensitive_tool"] if tool in {"cat", "touch", "mkdir"} else [],
    )
    enriched.setdefault("binding_type", "directory" if tool == "mkdir" else "file" if tool in {"cat", "touch"} else "path")
    enriched.setdefault("intervention_mode", "guidance")
    return enriched

def _write_rule(
    rules_dir: Path,
    *,
    recommended_tools: list[str] | None = None,
    action_candidates: list[dict] | None = None,
    request_predicates: list[str] | None = None,
    activation_predicates: list[str] | None = None,
) -> None:
    recommended_tools = list(recommended_tools or ["cat", "mkdir"])
    action_candidates = [
        _trajectory_candidate(candidate)
        for candidate in (
            action_candidates
            or [
                {"tool": "cat", "args": {"target": "file_0.txt"}, "recommended_tools": ["cat"]},
                {"tool": "mkdir", "args": {"target": "dir_1"}, "recommended_tools": ["mkdir"]},
            ]
        )
    ]
    request_predicates = list(request_predicates or ["tools_available", "prior_tool_outputs_present"])
    activation_predicates = list(activation_predicates or request_predicates)
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "rule.yaml").write_text(
        yaml.safe_dump(
            {
                "patch_id": "m27g_test",
                "rules": [
                    {
                        "rule_id": "rule_m27g_test",
                        "priority": 100,
                        "enabled": True,
                        "trigger": {
                            "tool_names": [],
                            "error_types": ["actionable_no_tool_decision"],
                            "category_patterns": [],
                            "request_predicates": request_predicates,
                        },
                        "scope": {"tool_names": [], "patch_sites": ["policy_executor", "prompt_injector"]},
                        "action": {
                            "decision_policy": {
                                "request_predicates": request_predicates,
                                "recommended_tools": recommended_tools,
                                "action_candidates": action_candidates,
                                "next_tool_policy": {
                                    "activation_predicates": activation_predicates,
                                    "recommended_tools": recommended_tools,
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


def _request_for(case_index: int, *, with_tool_output: bool = True) -> dict:
    if case_index % 2 == 0:
        user = f"Please read 'file_{case_index}.txt' and show me the content."
    else:
        user = f"Please create a directory named 'dir_{case_index}'."
    input_items = [{"role": "user", "content": user}]
    if with_tool_output:
        input_items.append({"role": "tool", "content": json.dumps({"current_working_directory": "/tmp"})})
    return {
        "model": "test-model",
        "input": input_items,
        "tools": [_bfcl_tool("cat"), _bfcl_tool("mkdir")],
    }


def _write_trace(trace_dir: Path, case_id: str, index: int, request: dict, *, target_failure: bool = True) -> None:
    trace_dir.mkdir(parents=True, exist_ok=True)
    labels = ["(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)"] if target_failure else []
    payload = {
        "trace_id": f"trace-{case_id}-{index}",
        "request_original": request,
        "request": request,
        "validation": {"failure_labels": labels},
    }
    (trace_dir / f"{case_id}__000__trace-{index}.json").write_text(json.dumps(payload), encoding="utf-8")


class M27fActivationPredicateAuditTests(unittest.TestCase):
    def test_dataset_state_can_fail_while_source_trace_state_activates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            selected = ["case_0", "case_1"]
            manifest = _write_manifest(root, selected)
            rules_dir = root / "rules"
            traces = root / "traces"
            _write_rule(rules_dir)
            for index, case_id in enumerate(selected):
                _write_trace(traces, case_id, index, _request_for(index, with_tool_output=True))

            report = evaluate_activation_predicate_audit(
                manifest,
                rules_dir=rules_dir,
                runtime_config=root / "runtime.yaml",
                source_traces=traces,
                min_trace_activation_count=1,
                dataset_rows=_dataset_rows(selected),
            )

        self.assertTrue(report["m2_7g_activation_audit_passed"])
        self.assertEqual(report["per_state_summary"]["dataset_prompt_prefix"]["activated_case_count"], 0)
        self.assertEqual(report["per_state_summary"][SOURCE_TRACE_RUNTIME]["activated_case_count"], 2)
        self.assertEqual(report["diagnostic"]["branch"], "plan_only_state_too_shallow")

    def test_source_trace_no_activation_due_to_unmet_activation_predicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            selected = ["case_0", "case_1"]
            manifest = _write_manifest(root, selected)
            rules_dir = root / "rules"
            traces = root / "traces"
            _write_rule(
                rules_dir,
                request_predicates=["tools_available"],
                activation_predicates=["tools_available", "prior_tool_outputs_present"],
            )
            for index, case_id in enumerate(selected):
                _write_trace(traces, case_id, index, _request_for(index, with_tool_output=False))

            report = evaluate_activation_predicate_audit(
                manifest,
                rules_dir=rules_dir,
                runtime_config=root / "runtime.yaml",
                source_traces=traces,
                min_trace_activation_count=1,
                dataset_rows=_dataset_rows(selected),
            )

        self.assertFalse(report["m2_7g_activation_audit_passed"])
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "trace_state_no_activation_dominant")
        self.assertEqual(report["diagnostic"]["branch"], "fix_trace_to_policy_predicate_generation")
        self.assertEqual(
            report["per_state_summary"][SOURCE_TRACE_RUNTIME]["blocked_reason_distribution"],
            {"activation_predicates_unmet": 2},
        )

    def test_schema_local_false_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            selected = ["case_0", "case_1"]
            manifest = _write_manifest(root, selected)
            rules_dir = root / "rules"
            traces = root / "traces"
            _write_rule(rules_dir, recommended_tools=["cat", "rm"])
            for index, case_id in enumerate(selected):
                _write_trace(traces, case_id, index, _request_for(index, with_tool_output=True))

            report = evaluate_activation_predicate_audit(
                manifest,
                rules_dir=rules_dir,
                runtime_config=root / "runtime.yaml",
                source_traces=traces,
                min_trace_activation_count=1,
                dataset_rows=_dataset_rows(selected),
            )

        self.assertFalse(report["m2_7g_activation_audit_passed"])
        self.assertFalse(report["candidate_rules_schema_local"])
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "candidate_rules_schema_local")

    def test_activation_count_below_threshold_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            selected = ["case_0", "case_1"]
            manifest = _write_manifest(root, selected)
            rules_dir = root / "rules"
            traces = root / "traces"
            _write_rule(rules_dir)
            _write_trace(traces, "case_0", 0, _request_for(0, with_tool_output=True))

            report = evaluate_activation_predicate_audit(
                manifest,
                rules_dir=rules_dir,
                runtime_config=root / "runtime.yaml",
                source_traces=traces,
                min_trace_activation_count=2,
                dataset_rows=_dataset_rows(selected),
            )

        self.assertFalse(report["m2_7g_activation_audit_passed"])
        self.assertEqual(report["trace_state_plan_activated_count"], 1)
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "trace_state_plan_activated_count")

    def test_dominant_selected_tool_rate_above_threshold_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            selected = [f"case_{index}" for index in range(5)]
            manifest = _write_manifest(root, selected)
            rules_dir = root / "rules"
            traces = root / "traces"
            _write_rule(
                rules_dir,
                recommended_tools=["cat"],
                action_candidates=[{"tool": "cat", "args": {"target": "file_0.txt"}, "recommended_tools": ["cat"]}],
            )
            for index, case_id in enumerate(selected):
                _write_trace(traces, case_id, index, _request_for(index, with_tool_output=True))

            report = evaluate_activation_predicate_audit(
                manifest,
                rules_dir=rules_dir,
                runtime_config=root / "runtime.yaml",
                source_traces=traces,
                min_trace_activation_count=1,
                dominant_threshold=0.8,
                dataset_rows=_dataset_rows(selected),
            )

        self.assertFalse(report["m2_7g_activation_audit_passed"])
        self.assertEqual(report["dominant_selected_next_tool_rate"], 1.0)
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "selected_next_tool_single_tool_collapse")


if __name__ == "__main__":
    unittest.main()
