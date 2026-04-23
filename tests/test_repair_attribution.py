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
