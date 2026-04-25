from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.check_m27f_artifact_completeness import evaluate_artifact_completeness
from scripts.check_m27f_candidate_action_diversity import evaluate_candidate_action_diversity
from scripts.check_m27f_candidate_plan_diversity import evaluate_candidate_plan_diversity
from scripts.run_phase2_target_subset import _dataset_user_texts_by_case


CATEGORY = "multi_turn_miss_param"
SELECTED = ["multi_turn_miss_param_0", "multi_turn_miss_param_1"]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _write_manifest(root: Path, selected: list[str] = SELECTED) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "paired_subset_manifest.json").write_text(
        json.dumps({"category": CATEGORY, "selected_case_ids": selected}, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_run(root: Path, run_name: str, *, missing_result: str | None = None, exception_id: str | None = None) -> None:
    run = root / run_name
    result_rows = []
    for case_id in SELECTED:
        if case_id == missing_result:
            continue
        if case_id == exception_id:
            result_rows.append({"id": case_id, "result": "Error during inference: boom", "traceback": "boom"})
        else:
            result_rows.append({"id": case_id, "result": [[[{"cat": "{}"}]]]})
    _write_jsonl(run / "bfcl" / "result" / "model" / "multi_turn" / f"BFCL_v4_{CATEGORY}_result.json", result_rows)
    _write_jsonl(
        run / "bfcl" / "score" / "model" / "multi_turn" / f"BFCL_v4_{CATEGORY}_score.json",
        [
            {"accuracy": 0.5, "correct_count": 1, "total_count": len(result_rows)},
            {"id": SELECTED[-1], "valid": False},
        ],
    )


def _write_candidate_traces(root: Path, selected: list[str] = SELECTED) -> None:
    trace_dir = root / "candidate" / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    prompt_users = _dataset_user_texts_by_case(CATEGORY, selected)
    for index, case_id in enumerate(selected):
        (trace_dir / f"trace_{index}.json").write_text(
            json.dumps({"request_original": {"input": [{"role": "user", "content": prompt_users[case_id][0]}]}}),
            encoding="utf-8",
        )


def _write_schema_local_rule(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "rules": [
                    {
                        "rule_id": "r1",
                        "action": {
                            "decision_policy": {
                                "recommended_tools": ["cat", "touch"],
                                "action_candidates": [
                                    {"tool": "cat", "recommended_tools": ["cat"]},
                                    {"tool": "touch", "recommended_tools": ["touch"]},
                                ],
                            }
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


class M27fPreflightTests(unittest.TestCase):
    def test_artifact_completeness_accepts_failure_only_score_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            _write_manifest(root)
            _write_run(root, "baseline")
            _write_run(root, "candidate")
            _write_candidate_traces(root)

            report = evaluate_artifact_completeness(root)

        self.assertTrue(report["m2_7f_artifact_completeness_passed"])
        self.assertEqual(report["runs"]["candidate"]["missing_score_ids"], [SELECTED[0]])
        self.assertEqual(report["runs"]["candidate"]["missing_effective_score_ids"], [])
        self.assertTrue(report["runs"]["candidate"]["scorer_coverage_explained_by_failure_only_rows"])

    def test_artifact_completeness_fails_when_result_row_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            _write_manifest(root)
            _write_run(root, "baseline")
            _write_run(root, "candidate", missing_result=SELECTED[0])
            _write_candidate_traces(root)

            report = evaluate_artifact_completeness(root)

        self.assertFalse(report["m2_7f_artifact_completeness_passed"])
        self.assertEqual(report["runs"]["candidate"]["missing_result_ids"], [SELECTED[0]])

    def test_artifact_completeness_preserves_exception_result_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            _write_manifest(root)
            _write_run(root, "baseline")
            _write_run(root, "candidate", exception_id=SELECTED[0])
            _write_candidate_traces(root)

            report = evaluate_artifact_completeness(root)

        self.assertTrue(report["m2_7f_artifact_completeness_passed"])
        self.assertEqual(report["runs"]["candidate"]["result_exception_ids"], [SELECTED[0]])

    def test_artifact_completeness_fails_when_prompt_prefix_trace_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            _write_manifest(root)
            _write_run(root, "baseline")
            _write_run(root, "candidate")
            _write_candidate_traces(root, selected=[SELECTED[0]])

            report = evaluate_artifact_completeness(root)

        self.assertFalse(report["m2_7f_artifact_completeness_passed"])
        self.assertEqual(report["runs"]["candidate"]["missing_trace_ids"], [SELECTED[1]])

    def test_action_diversity_fails_single_tool_collapse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            report_path = root / "subset_case_report.jsonl"
            rows = [
                {"case_id": f"case_{index}", "policy_plan_activated": True, "selected_next_tool": "mkdir"}
                for index in range(29)
            ] + [{"case_id": "case_29", "policy_plan_activated": False, "selected_next_tool": None}]
            _write_jsonl(report_path, rows)
            rule_path = root / "rule.yaml"
            _write_schema_local_rule(rule_path)

            report = evaluate_candidate_action_diversity(report_path, rule_path=rule_path)

        self.assertFalse(report["m2_7f_candidate_action_diversity_passed"])
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "selected_next_tool_single_tool_collapse")

    def test_action_diversity_accepts_multi_tool_distribution_under_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            report_path = root / "subset_case_report.jsonl"
            rows = [
                {"case_id": f"cat_{index}", "policy_plan_activated": True, "selected_next_tool": "cat"}
                for index in range(7)
            ] + [
                {"case_id": f"touch_{index}", "policy_plan_activated": True, "selected_next_tool": "touch"}
                for index in range(3)
            ]
            _write_jsonl(report_path, rows)
            rule_path = root / "rule.yaml"
            _write_schema_local_rule(rule_path)

            report = evaluate_candidate_action_diversity(report_path, rule_path=rule_path)

        self.assertTrue(report["m2_7f_candidate_action_diversity_passed"])
        self.assertEqual(report["dominant_selected_next_tool_rate"], 0.7)


def _bfcl_tool(name: str) -> dict:
    return {
        "name": name,
        "description": f"{name} tool",
        "parameters": {"type": "object", "properties": {"target": {"type": "string"}}},
    }


def _plan_dataset_rows() -> list[dict]:
    return [
        {
            "id": SELECTED[0],
            "question": [[{"role": "user", "content": "Please read 'alpha.txt' and show me the content."}]],
            "function": [_bfcl_tool("cat"), _bfcl_tool("mkdir")],
        },
        {
            "id": SELECTED[1],
            "question": [[{"role": "user", "content": "Please create a directory named 'archive'."}]],
            "function": [_bfcl_tool("cat"), _bfcl_tool("mkdir")],
        },
    ]


def _write_plan_rule(
    path: Path,
    *,
    recommended_tools: list[str],
    action_candidates: list[dict],
    request_predicates: list[str] | None = None,
    activation_predicates: list[str] | None = None,
) -> None:
    request_predicates = list(request_predicates or ["tools_available"])
    activation_predicates = list(activation_predicates or request_predicates)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "patch_id": "test_plan_diversity",
                "rules": [
                    {
                        "rule_id": "rule_plan_diversity",
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


class M27fPlanOnlyPreflightTests(unittest.TestCase):
    def test_plan_diversity_fails_single_mkdir_collapse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            _write_manifest(root)
            rules_dir = root / "rules"
            _write_plan_rule(
                rules_dir / "rule.yaml",
                recommended_tools=["mkdir"],
                action_candidates=[{"tool": "mkdir", "args": {"target": "archive"}, "recommended_tools": ["mkdir"]}],
            )

            report = evaluate_candidate_plan_diversity(
                root / "paired_subset_manifest.json",
                rules_dir=rules_dir,
                runtime_config=root / "runtime.yaml",
                dataset_rows=_plan_dataset_rows(),
            )

        self.assertFalse(report["m2_7f_candidate_plan_diversity_passed"])
        self.assertEqual(report["selected_next_tool_distribution"], {"mkdir": 2})
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "selected_next_tool_single_mkdir_collapse")

    def test_plan_diversity_accepts_request_local_multi_tool_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            _write_manifest(root)
            rules_dir = root / "rules"
            _write_plan_rule(
                rules_dir / "rule.yaml",
                recommended_tools=["mkdir", "cat"],
                action_candidates=[
                    {"tool": "mkdir", "args": {"target": "archive"}, "recommended_tools": ["mkdir"]},
                    {"tool": "cat", "args": {"target": "alpha.txt"}, "recommended_tools": ["cat"]},
                ],
            )

            report = evaluate_candidate_plan_diversity(
                root / "paired_subset_manifest.json",
                rules_dir=rules_dir,
                runtime_config=root / "runtime.yaml",
                dataset_rows=_plan_dataset_rows(),
            )

        self.assertTrue(report["m2_7f_candidate_plan_diversity_passed"])
        self.assertEqual(report["selected_next_tool_distribution"], {"cat": 1, "mkdir": 1})
        self.assertEqual(report["per_case_selected_tool"][SELECTED[0]], "cat")
        self.assertEqual(report["per_case_selected_tool"][SELECTED[1]], "mkdir")

    def test_plan_diversity_fails_when_no_plan_activates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            _write_manifest(root)
            rules_dir = root / "rules"
            _write_plan_rule(
                rules_dir / "rule.yaml",
                recommended_tools=["cat", "mkdir"],
                action_candidates=[{"tool": "cat", "args": {"target": "alpha.txt"}, "recommended_tools": ["cat"]}],
                request_predicates=["prior_tool_outputs_present", "tools_available"],
            )

            report = evaluate_candidate_plan_diversity(
                root / "paired_subset_manifest.json",
                rules_dir=rules_dir,
                runtime_config=root / "runtime.yaml",
                dataset_rows=_plan_dataset_rows(),
            )

        self.assertFalse(report["m2_7f_candidate_plan_diversity_passed"])
        self.assertEqual(report["plan_activated_count"], 0)
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "no_activation")

    def test_plan_diversity_fails_when_policy_tools_are_not_schema_local(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            _write_manifest(root)
            rules_dir = root / "rules"
            _write_plan_rule(
                rules_dir / "rule.yaml",
                recommended_tools=["cat", "rm"],
                action_candidates=[{"tool": "cat", "args": {"target": "alpha.txt"}, "recommended_tools": ["cat"]}],
            )

            report = evaluate_candidate_plan_diversity(
                root / "paired_subset_manifest.json",
                rules_dir=rules_dir,
                runtime_config=root / "runtime.yaml",
                dataset_rows=_plan_dataset_rows(),
            )

        self.assertFalse(report["m2_7f_candidate_plan_diversity_passed"])
        self.assertFalse(report["candidate_rules_schema_local"])


if __name__ == "__main__":
    unittest.main()
