from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_phase2_taxonomy_report import build_comparison, summarize_run


class Phase2TaxonomyReportTests(unittest.TestCase):
    def test_summarize_run_uses_failure_label_and_boundary_misuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace_dir = root / "traces"
            trace_dir.mkdir()
            (trace_dir / "trace_1.json").write_text(
                json.dumps(
                    {
                        "trace_id": "trace_1",
                        "request": {
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "Use file report.txt\nHere is a list of functions in json format that you can invoke.\n[{\"name\":\"read_file\",\"parameters\":{\"type\":\"object\",\"properties\":{\"path\":{\"type\":\"string\"}},\"required\":[\"path\"]}}]",
                                }
                            ]
                        },
                        "raw_response": {"choices": [{"message": {"content": "Which file should I use?"}}]},
                        "validation": {"issues": [{"kind": "clarification_request"}]},
                    }
                ),
                encoding="utf-8",
            )
            summary = summarize_run("baseline", trace_dir)

        row = summary["taxonomy_distribution"][0]
        self.assertEqual(row["failure_label"], "(PRE_TOOL,ACTIONABLE_NO_TOOL_DECISION)")
        self.assertEqual(row["failure_group"], "decision_layer_target")

    def test_build_comparison_outputs_deltas(self) -> None:
        run_summaries = [
            {"run": "baseline", "taxonomy_distribution": [{"failure_label": "(PRE_TOOL,ACTIONABLE_NO_TOOL_DECISION)", "count": 3, "share": 0.6}]},
            {"run": "primary_v4", "taxonomy_distribution": [{"failure_label": "(PRE_TOOL,ACTIONABLE_NO_TOOL_DECISION)", "count": 1, "share": 0.2}]},
        ]
        merged, delta = build_comparison(run_summaries, "baseline")
        self.assertEqual(merged[0]["baseline_count"], 3)
        self.assertEqual(delta[0]["count_delta_vs_baseline"], -2)
