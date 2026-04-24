from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_repair_contribution import _load_success_map, repair_records, summarize_repairs


class RepairAttributionTests(unittest.TestCase):
    def test_load_success_map_from_jsonl_score_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            score_path = root / "score.json"
            score_path.write_text(
                "\n".join(
                    [
                        json.dumps({"accuracy": 0.4, "correct_count": 80, "total_count": 200}),
                        json.dumps({"id": "case_1", "valid": True}),
                        json.dumps({"id": "case_2", "valid": False}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            success_map = _load_success_map(score_path)

        self.assertEqual(success_map, {"case_1": True, "case_2": False})

    def test_uses_request_fingerprint_when_score_jsonl_has_no_explicit_case_id_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            score_path = root / "score.json"
            score_path.write_text(
                json.dumps(
                    {
                        "prompt": {
                            "question": [
                                [{"role": "user", "content": "Read report.txt and summarize it."}],
                            ]
                        },
                        "valid": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "trace.json").write_text(
                json.dumps(
                    {
                        "trace_id": "trace_1",
                        "repairs": [{"kind": "coerce_no_tool_text_to_empty"}],
                        "request_original": {
                            "input": [
                                {"role": "user", "content": "Read report.txt and summarize it."},
                            ]
                        },
                        "validation": {"issues": [{"kind": "actionable_no_tool_decision"}]},
                    }
                ),
                encoding="utf-8",
            )

            success_map = _load_success_map(score_path)
            records = repair_records(root, run_id="run", success_map=success_map)

        self.assertEqual(records[0]["final_success"], True)

    def test_builds_repair_records_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "trace.json").write_text(
                json.dumps(
                    {
                        "trace_id": "trace",
                        "case_id": "case_1",
                        "repairs": [{"kind": "coerce_no_tool_text_to_empty"}],
                        "request": {
                            "messages": [
                                {"role": "user", "content": "use the tool"},
                                {"role": "tool", "content": "{\"path\":\"report.txt\"}"},
                            ]
                        },
                        "validation": {
                            "issues": [{"kind": "actionable_no_tool_decision"}],
                            "policy_hits": ["rule_next_tool_policy"],
                            "recommended_tools": ["lookup_file"],
                            "next_tool_plan_attempted": True,
                            "next_tool_plan_activated": True,
                            "next_tool_plan_blocked_reason": "activated",
                            "available_tools": ["lookup_file"],
                            "candidate_recommended_tools": ["lookup_file"],
                            "matched_recommended_tools": ["lookup_file"],
                            "activation_predicate_status": {"tools_available": True},
                            "selected_next_tool": "lookup_file",
                            "tool_choice_mode": "soft",
                            "next_tool_emitted": True,
                            "next_tool_matches_recommendation": True,
                        },
                    }
                ),
                encoding="utf-8",
            )

            records = repair_records(root, run_id="run", success_map={"case_1": True})
            summary = summarize_repairs(records, ablation_acc={"full": 43.5, "coerce_no_tool_text_to_empty": 40.0})

        self.assertEqual(records[0]["failure_type"], "ACTIONABLE_NO_TOOL_DECISION")
        self.assertEqual(records[0]["failure_stage"], "POST_TOOL")
        self.assertEqual(records[0]["repairs_applied"], ["coerce_no_tool_text_to_empty"])
        self.assertEqual(summary["repairs"]["coerce_no_tool_text_to_empty"]["applied"], 1)
        self.assertEqual(summary["repairs"]["coerce_no_tool_text_to_empty"]["repair_class"], "decision_adjacent")
        self.assertEqual(summary["repairs"]["coerce_no_tool_text_to_empty"]["success"], 1.0)
        self.assertEqual(summary["repairs"]["coerce_no_tool_text_to_empty"]["attribution_gain"], 3.5)
        self.assertEqual(summary["repair_by_family"][0]["failure_label"], "(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)")
        self.assertEqual(records[0]["policy_hits"], ["rule_next_tool_policy"])
        self.assertEqual(summary["policy_conversion_by_family"][0]["policy_hit_count"], 1)
        self.assertEqual(summary["policy_conversion_by_family"][0]["next_tool_conversion"], 1.0)
        self.assertEqual(summary["policy_conversion_by_family"][0]["recommended_tool_match"], 1.0)
        self.assertEqual(summary["policy_conversion_by_family"][0]["scorer_success"], 1.0)
        self.assertEqual(records[0]["next_tool_plan_blocked_reason"], "activated")
        self.assertEqual(summary["next_tool_plan_blocked_reason_distribution"], {"activated": 1})

    def test_summarizes_next_tool_blocked_reasons_without_policy_hits(self) -> None:
        records = [
            {
                "failure_label": "(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)",
                "repairs_applied": [],
                "final_success": None,
                "policy_hits": [],
                "next_tool_plan_attempted": True,
                "next_tool_plan_activated": False,
                "next_tool_plan_blocked_reason": "recommended_tools_empty",
            },
            {
                "failure_label": "(POST_TOOL,POST_TOOL_PROSE_SUMMARY)",
                "repairs_applied": [],
                "final_success": None,
                "policy_hits": [],
                "next_tool_plan_attempted": True,
                "next_tool_plan_activated": False,
                "next_tool_plan_blocked_reason": "activation_predicates_unmet",
            },
        ]

        summary = summarize_repairs(records)

        self.assertEqual(summary["policy_conversion_by_family"], [])
        self.assertEqual(
            summary["next_tool_plan_blocked_reason_distribution"],
            {"activation_predicates_unmet": 1, "recommended_tools_empty": 1},
        )
