from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.run_phase2_target_subset import (
    build_case_report,
    _execution_env,
    _result_json_path,
    _score_json_path,
    _tool_names_from_trace,
    _tool_names_from_prompt_path,
    build_gap_report_rows,
    candidate_case_infos,
    candidate_policy_tool_distribution,
    materialize_selected_traces,
    prune_rule_policy_tools,
    rules_have_ctspc_actions,
    select_case_ids,
    summarize_schema_scan,
    summarize_gap_report,
    summarize_case_report,
    write_test_case_ids,
)


class Phase2TargetSubsetTests(unittest.TestCase):
    def test_select_case_ids_prefers_failed_path_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            score = root / "bfcl" / "score" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_param_score.json"
            score.parent.mkdir(parents=True)
            score.write_text(
                "\n".join(
                    [
                        json.dumps({"accuracy": 0.0}),
                        json.dumps(
                            {
                                "id": "multi_turn_miss_param_2",
                                "valid": True,
                                "prompt": {"question": [[{"role": "user", "content": "read file report.txt"}]]},
                            }
                        ),
                        json.dumps(
                            {
                                "id": "multi_turn_miss_param_1",
                                "valid": False,
                                "prompt": {"question": [[{"role": "user", "content": "find matches then cat file"}]]},
                            }
                        ),
                        json.dumps(
                            {
                                "id": "multi_turn_miss_param_3",
                                "valid": False,
                                "prompt": {"question": [[{"role": "user", "content": "say hello"}]]},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            selected = select_case_ids(root, "multi_turn_miss_param", 2, schema_local=False)

        self.assertEqual(selected, ["multi_turn_miss_param_1", "multi_turn_miss_param_3"])

    def test_tool_names_from_trace_supports_snapshot_dict_list_and_request_fallback(self) -> None:
        trace = {
            "tool_schema_snapshot": {
                "cat": {"type": "object"},
                "find": {"type": "object"},
            },
            "request": {
                "tools": [
                    {"type": "function", "function": {"name": "touch"}},
                    {"name": "mkdir"},
                ]
            },
        }
        self.assertEqual(_tool_names_from_trace(trace), {"cat", "find", "touch", "mkdir"})

        list_trace = {
            "tool_schema_snapshot": [
                {"type": "function", "function": {"name": "grep"}},
                {"name": "ls"},
            ]
        }
        self.assertEqual(_tool_names_from_trace(list_trace), {"grep", "ls"})

    def test_tool_names_from_prompt_path_extracts_leaf_function_names(self) -> None:
        row = {"prompt": {"path": ["GorillaFileSystem.find", "GorillaFileSystem.mv", "TwitterAPI.post_tweet"]}}
        self.assertEqual(_tool_names_from_prompt_path(row), {"find", "mv", "post_tweet"})

    def test_schema_local_selection_filters_keyword_cases_without_target_tool_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            score = root / "bfcl" / "score" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_param_score.json"
            result = root / "bfcl" / "result" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_param_result.json"
            score.parent.mkdir(parents=True)
            result.parent.mkdir(parents=True)
            score.write_text(
                "\n".join(
                    [
                        json.dumps({"accuracy": 0.0}),
                        json.dumps(
                            {
                                "id": "multi_turn_miss_param_1",
                                "valid": False,
                                "prompt": {
                                    "path": ["TravelAPI.book_flight"],
                                    "question": [[{"role": "user", "content": "find file path"}]],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "id": "multi_turn_miss_param_2",
                                "valid": False,
                                "prompt": {
                                    "path": ["GorillaFileSystem.cat"],
                                    "question": [[{"role": "user", "content": "find file path"}]],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "id": "multi_turn_miss_param_3",
                                "valid": False,
                                "prompt": {
                                    "path": ["GorillaFileSystem.touch"],
                                    "question": [[{"role": "user", "content": "say hello"}]],
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            result.write_text(
                "\n".join(
                    [
                        json.dumps({"id": "multi_turn_miss_param_1", "result": [[[{"book_flight": "{}"}]]]}),
                        json.dumps({"id": "multi_turn_miss_param_2", "result": [[[{"cat": "{}"}]]]}),
                        json.dumps({"id": "multi_turn_miss_param_3", "result": [[[{"book_flight": "{}"}]]]}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            trace_dir = root / "traces"
            trace_dir.mkdir()
            (trace_dir / "trace_1.json").write_text(json.dumps({"tool_schema_snapshot": {"book_flight": {}}}), encoding="utf-8")
            (trace_dir / "trace_2.json").write_text(json.dumps({"tool_schema_snapshot": {"cat": {}}}), encoding="utf-8")
            (trace_dir / "trace_3.json").write_text(json.dumps({"tool_schema_snapshot": {"book_flight": {}}}), encoding="utf-8")

            infos = candidate_case_infos(root, "multi_turn_miss_param")
            selected = select_case_ids(root, "multi_turn_miss_param", 10)
            scan = summarize_schema_scan(infos)

        self.assertEqual(len(infos), 3)
        self.assertEqual(selected, ["multi_turn_miss_param_2", "multi_turn_miss_param_3"])
        self.assertEqual(infos[0]["target_action_tools_present"], [])
        self.assertEqual(infos[1]["target_action_tools_present"], ["cat"])
        self.assertEqual(infos[2]["target_action_tools_present"], ["touch"])
        self.assertEqual(infos[0]["schema_source"], "prompt_path")
        self.assertEqual(scan["cases_with_TARGET_ACTION_TOOLS"], 2)
        self.assertEqual(scan["schema_source_distribution"], {"prompt_path": 3})

    def test_write_test_case_ids_uses_category_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            path = Path(tmp_raw) / "test_case_ids_to_generate.json"
            write_test_case_ids(path, "multi_turn_miss_param", ["multi_turn_miss_param_7"])
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["multi_turn_miss_param"], ["multi_turn_miss_param_7"])

    def test_execution_env_prepends_repo_venv_python_and_enables_run_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            env = _execution_env(root)

        self.assertTrue(env["PATH"].startswith(str(root / ".venv" / "bin")))
        self.assertEqual(env["GRC_BFCL_USE_RUN_IDS"], "1")
        self.assertEqual(env["GRC_BFCL_PARTIAL_EVAL"], "1")
        self.assertEqual(env["GRC_BFCL_NUM_THREADS"], "1")

    def test_rules_have_ctspc_actions_detects_action_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            rule = root / "rule.yaml"
            rule.write_text(
                """
rules:
  - rule_id: r1
    action:
      decision_policy:
        recommended_tools: [cat]
        action_candidates:
          - tool: cat
            args: {file_name: notes.txt}
""",
                encoding="utf-8",
            )
            empty = root / "empty.yaml"
            empty.write_text("rules:\n  - rule_id: r2\n    action:\n      decision_policy: {}\n", encoding="utf-8")

            self.assertTrue(rules_have_ctspc_actions(rule))
            self.assertFalse(rules_have_ctspc_actions(empty))

    def test_build_case_report_joins_scores_and_trace_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            baseline = root / "baseline"
            candidate = root / "candidate"
            for run, valid in ((baseline, False), (candidate, True)):
                score = run / "bfcl" / "score" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_param_score.json"
                score.parent.mkdir(parents=True)
                score.write_text(
                    json.dumps({"accuracy": 0.0}) + "\n" + json.dumps({"id": "multi_turn_miss_param_1", "valid": valid}) + "\n",
                    encoding="utf-8",
                )
            result = candidate / "bfcl" / "result" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_param_result.json"
            result.parent.mkdir(parents=True)
            result.write_text(
                json.dumps({"id": "multi_turn_miss_param_1", "result": [[[{"cat": "{}"}]]]}) + "\n",
                encoding="utf-8",
            )
            trace = candidate / "traces" / "trace.json"
            trace.parent.mkdir(parents=True)
            trace.write_text(
                json.dumps(
                    {
                        "validation": {
                            "next_tool_plan_activated": True,
                            "selected_next_tool": "cat",
                            "next_tool_emitted": True,
                            "next_tool_matches_recommendation": True,
                            "next_tool_args_match_binding_normalized": True,
                            "repair_kinds": ["coerce_no_tool_text_to_empty"],
                        }
                    }
                ),
                encoding="utf-8",
            )

            rows = build_case_report(
                baseline_run=baseline,
                candidate_run=candidate,
                category="multi_turn_miss_param",
                selected_ids=["multi_turn_miss_param_1"],
            )
            summary = summarize_case_report(rows)

        self.assertTrue(rows[0]["case_fixed"])
        self.assertEqual(rows[0]["selected_next_tool"], "cat")
        self.assertEqual(rows[0]["repair_kinds"], ["coerce_no_tool_text_to_empty"])
        self.assertEqual(summary["case_fixed_count"], 1)
        self.assertTrue(summary["accepted"])

    def test_nested_partial_eval_score_and_result_paths_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            run = Path(tmp_raw)
            score = (
                run
                / "bfcl"
                / "outputs"
                / "phase2"
                / "score"
                / "model"
                / "multi_turn"
                / "BFCL_v4_multi_turn_miss_param_score.json"
            )
            result = (
                run
                / "bfcl"
                / "outputs"
                / "phase2"
                / "result"
                / "model"
                / "multi_turn"
                / "BFCL_v4_multi_turn_miss_param_result.json"
            )
            score.parent.mkdir(parents=True)
            result.parent.mkdir(parents=True)
            score.write_text(
                json.dumps({"accuracy": 0.5, "correct_count": 1, "total_count": 2})
                + "\n"
                + json.dumps({"id": "multi_turn_miss_param_1", "valid": True})
                + "\n",
                encoding="utf-8",
            )
            result.write_text(
                json.dumps({"id": "multi_turn_miss_param_1", "result": [[[{"cat": "{}"}]]]}) + "\n",
                encoding="utf-8",
            )

            rows = build_case_report(
                baseline_run=run,
                candidate_run=run,
                category="multi_turn_miss_param",
                selected_ids=["multi_turn_miss_param_1"],
            )
            score_path = _score_json_path(run, "multi_turn_miss_param")
            result_path = _result_json_path(run, "multi_turn_miss_param")

        self.assertEqual(score_path, score)
        self.assertEqual(result_path, result)
        self.assertTrue(rows[0]["baseline_success"])
        self.assertTrue(rows[0]["candidate_success"])

    def test_materialize_selected_traces_copies_only_selected_case_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            source = root / "source"
            result = source / "bfcl" / "result" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_param_result.json"
            result.parent.mkdir(parents=True)
            result.write_text(
                "\n".join(
                    [
                        json.dumps({"id": "multi_turn_miss_param_1", "result": [[[{"cat": "{}"}], [{"cat": "{}"}]]]}),
                        json.dumps({"id": "multi_turn_miss_param_2", "result": [[[{"touch": "{}"}]]]}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            trace_dir = source / "traces"
            trace_dir.mkdir(parents=True)
            for index in range(3):
                (trace_dir / f"trace_{index}.json").write_text(json.dumps({"index": index}), encoding="utf-8")

            manifest = materialize_selected_traces(
                source_run_root=source,
                category="multi_turn_miss_param",
                selected_ids=["multi_turn_miss_param_2"],
                out_dir=root / "selected",
            )
            copied = sorted((root / "selected").glob("*.json"))

        self.assertEqual(manifest["expected_trace_count"], 1)
        self.assertEqual(manifest["selected_trace_count"], 1)
        self.assertEqual(len(copied), 1)
        self.assertIn("multi_turn_miss_param_2", copied[0].name)

    def test_candidate_policy_tool_distribution_counts_policy_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            rule = root / "rule.yaml"
            rule.write_text(
                """
rules:
  - rule_id: r1
    action:
      decision_policy:
        recommended_tools: [cat]
        action_candidates:
          - tool: cat
            recommended_tools: [cat]
          - tool: touch
            recommended_tools: [touch]
        next_tool_policy:
          recommended_tools: [cat]
""",
                encoding="utf-8",
            )

            distribution = candidate_policy_tool_distribution(rule)

        self.assertEqual(distribution["cat"], 4)
        self.assertEqual(distribution["touch"], 2)

    def test_prune_rule_policy_tools_removes_non_file_path_policy_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            rule = root / "rule.yaml"
            rule.write_text(
                """
rules:
  - rule_id: r1
    action:
      decision_policy:
        recommended_tools: [cat, book_flight]
        action_candidates:
          - tool: cat
            recommended_tools: [cat]
          - tool: book_flight
            recommended_tools: [book_flight]
        next_tool_policy:
          recommended_tools: [touch, add_to_watchlist]
""",
                encoding="utf-8",
            )

            result = prune_rule_policy_tools(rule, allowed_tools={"cat", "touch"})
            distribution = candidate_policy_tool_distribution(rule)
            has_ctspc_actions = rules_have_ctspc_actions(rule)

        self.assertEqual(result["kept_action_candidate_count"], 1)
        self.assertIn("book_flight", result["removed_tools"])
        self.assertEqual(distribution, {"cat": 3, "touch": 1})
        self.assertTrue(has_ctspc_actions)

    def test_gap_report_classifies_non_target_schema_insufficient_evidence_and_generator_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            failures = root / "failures.jsonl"
            failures.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "trace_id": "case_generator_gap__000__trace",
                                "failure_label": "(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)",
                                "recommended_tools": ["book_flight"],
                                "action_candidates": [{"tool": "book_flight", "recommended_tools": ["book_flight"]}],
                            }
                        ),
                        json.dumps(
                            {
                                "trace_id": "case_schema_local__000__trace",
                                "failure_label": "(POST_TOOL,POST_TOOL_PROSE_SUMMARY)",
                                "recommended_tools": ["cat"],
                                "action_candidates": [{"tool": "cat", "recommended_tools": ["cat"]}],
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            candidates = [
                {
                    "case_id": "case_non_target",
                    "failure_labels": ["(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)"],
                    "available_tools_in_case_schema": ["book_flight"],
                    "target_action_tools_present": [],
                },
                {
                    "case_id": "case_insufficient",
                    "failure_labels": ["(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)"],
                    "available_tools_in_case_schema": ["cat"],
                    "target_action_tools_present": ["cat"],
                },
                {
                    "case_id": "case_generator_gap",
                    "failure_labels": ["(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)"],
                    "available_tools_in_case_schema": ["cat"],
                    "target_action_tools_present": ["cat"],
                },
                {
                    "case_id": "case_schema_local",
                    "failure_labels": ["(POST_TOOL,POST_TOOL_PROSE_SUMMARY)"],
                    "available_tools_in_case_schema": ["cat"],
                    "target_action_tools_present": ["cat"],
                },
            ]

            rows = build_gap_report_rows(
                candidates,
                failures_path=failures,
                prune_result={"kept_tools": {"cat": 1}, "removed_tools": {"book_flight": 1}},
            )
            summary = summarize_gap_report(rows, selected_ids=["case_schema_local"], min_schema_local_cases=20)

        reasons = {row["case_id"]: row["why_no_schema_local_candidate"] for row in rows}
        self.assertEqual(reasons["case_non_target"], "non_target_schema")
        self.assertEqual(reasons["case_insufficient"], "insufficient_local_evidence")
        self.assertEqual(reasons["case_generator_gap"], "generator_gap")
        self.assertEqual(reasons["case_schema_local"], "schema_local_candidate")
        self.assertEqual(summary["schema_local_candidate_count"], 3)
        self.assertEqual(summary["schema_filtered_out_count"], 1)
        self.assertFalse(summary["eligible_for_execution"])

    def test_dry_run_with_too_few_schema_local_cases_writes_gap_artifacts_without_bfcl_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            source = root / "source"
            out = root / "out"
            score = source / "bfcl" / "score" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_param_score.json"
            result = source / "bfcl" / "result" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_param_result.json"
            score.parent.mkdir(parents=True)
            result.parent.mkdir(parents=True)
            score.write_text(
                json.dumps({"accuracy": 0.0})
                + "\n"
                + json.dumps(
                    {
                        "id": "multi_turn_miss_param_1",
                        "valid": False,
                        "prompt": {
                            "path": ["TravelAPI.book_flight"],
                            "question": [[{"role": "user", "content": "find file path"}]],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result.write_text(json.dumps({"id": "multi_turn_miss_param_1", "result": [[[{"book_flight": "{}"}]]]}) + "\n", encoding="utf-8")
            trace_dir = source / "traces"
            trace_dir.mkdir(parents=True)
            (trace_dir / "trace.json").write_text(json.dumps({"tool_schema_snapshot": {"book_flight": {}}}), encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    "scripts/run_phase2_target_subset.py",
                    "--source-run-root",
                    str(source),
                    "--out-root",
                    str(out),
                    "--dry-run",
                ],
                check=True,
                cwd=Path.cwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            manifest = json.loads((out / "subset_manifest.json").read_text(encoding="utf-8"))
            gap_summary = json.loads((out / "gap_summary.json").read_text(encoding="utf-8"))
            schema_scan_summary = json.loads((out / "schema_scan_summary.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["selected_case_ids"], [])
        self.assertEqual(manifest["planned_commands"], [])
        self.assertEqual(gap_summary["schema_filtered_out_count"], 1)
        self.assertEqual(gap_summary["why_no_schema_local_candidate_distribution"], {"non_target_schema": 1})
        self.assertEqual(schema_scan_summary["cases_with_TARGET_ACTION_TOOLS"], 0)

    def test_dry_run_with_enough_schema_local_cases_writes_planned_commands_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            source = root / "source"
            out = root / "out"
            score = source / "bfcl" / "score" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_param_score.json"
            score.parent.mkdir(parents=True)
            lines = [json.dumps({"accuracy": 0.0})]
            for index in range(2):
                lines.append(
                    json.dumps(
                        {
                            "id": f"multi_turn_miss_param_{index}",
                            "valid": False,
                            "prompt": {
                                "path": ["GorillaFileSystem.cat"],
                                "question": [[{"role": "user", "content": "hello"}]],
                            },
                        }
                    )
                )
            score.write_text("\n".join(lines) + "\n", encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    "scripts/run_phase2_target_subset.py",
                    "--source-run-root",
                    str(source),
                    "--out-root",
                    str(out),
                    "--dry-run",
                    "--min-schema-local-cases",
                    "2",
                ],
                check=True,
                cwd=Path.cwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            manifest = json.loads((out / "subset_manifest.json").read_text(encoding="utf-8"))
            schema_scan_summary = json.loads((out / "schema_scan_summary.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["selected_case_ids"], ["multi_turn_miss_param_0", "multi_turn_miss_param_1"])
        self.assertEqual(len(manifest["planned_commands"]), 2)
        self.assertEqual(schema_scan_summary["cases_with_TARGET_ACTION_TOOLS"], 2)


if __name__ == "__main__":
    unittest.main()
