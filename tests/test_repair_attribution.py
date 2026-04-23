from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_repair_contribution import repair_records, summarize_repairs


class RepairAttributionTests(unittest.TestCase):
    def test_builds_repair_records_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "trace.json").write_text(
                json.dumps(
                    {
                        "trace_id": "trace",
                        "case_id": "case_1",
                        "repairs": [{"kind": "coerce_no_tool_text_to_empty"}],
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
        self.assertEqual(records[0]["repairs_applied"], ["coerce_no_tool_text_to_empty"])
        self.assertEqual(summary["repairs"]["coerce_no_tool_text_to_empty"]["applied"], 1)
        self.assertEqual(summary["repairs"]["coerce_no_tool_text_to_empty"]["repair_class"], "decision_adjacent")
        self.assertEqual(summary["repairs"]["coerce_no_tool_text_to_empty"]["success"], 1.0)
        self.assertEqual(summary["repairs"]["coerce_no_tool_text_to_empty"]["attribution_gain"], 3.5)
        self.assertEqual(summary["repair_by_family"][0]["failure_label"], "(PRE_TOOL,ACTIONABLE_NO_TOOL_DECISION)")
