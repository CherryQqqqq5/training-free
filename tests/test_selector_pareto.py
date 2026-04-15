from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from grc.selector.pareto import select_patch


class ParetoSelectionTests(unittest.TestCase):
    def test_rejects_candidate_without_metrics_or_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_dir = root / "baseline"
            candidate_dir = root / "candidate"
            baseline_dir.mkdir()
            candidate_dir.mkdir()

            (baseline_dir / "metrics.json").write_text(
                json.dumps(
                    {
                        "acc": 1.0,
                        "cost": 1.0,
                        "latency": 100.0,
                        "metric_sources": ["baseline.csv"],
                    }
                ),
                encoding="utf-8",
            )
            (baseline_dir / "failure_summary.json").write_text(json.dumps({"trace_count": 10}), encoding="utf-8")
            (candidate_dir / "metrics.json").write_text(
                json.dumps(
                    {
                        "acc": 1.0,
                        "cost": 1.0,
                        "latency": 50.0,
                        "metric_sources": [],
                    }
                ),
                encoding="utf-8",
            )
            (candidate_dir / "failure_summary.json").write_text(json.dumps({"trace_count": 10}), encoding="utf-8")
            (candidate_dir / "rule.yaml").write_text(
                "patch_id: patch_001\nrules: []\nsource_failure_count: 0\n",
                encoding="utf-8",
            )

            decision = select_patch(str(baseline_dir / "metrics.json"), str(candidate_dir / "metrics.json"))

        self.assertFalse(decision["accept"])
        self.assertFalse(decision["candidate_valid"])
        self.assertIn("metric_sources empty", decision["candidate_validity_issues"])
        self.assertIn("source_failure_count <= 0", decision["candidate_validity_issues"])
        self.assertIn("rules empty", decision["candidate_validity_issues"])

    def test_accepts_valid_candidate_that_dominates_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_dir = root / "baseline"
            candidate_dir = root / "candidate"
            baseline_dir.mkdir()
            candidate_dir.mkdir()

            (baseline_dir / "metrics.json").write_text(
                json.dumps(
                    {
                        "acc": 1.0,
                        "cost": 2.0,
                        "latency": 200.0,
                        "metric_sources": ["baseline.csv"],
                        "subsets": {"multi_turn_base": 70.0},
                    }
                ),
                encoding="utf-8",
            )
            (baseline_dir / "failure_summary.json").write_text(json.dumps({"trace_count": 10}), encoding="utf-8")
            (candidate_dir / "metrics.json").write_text(
                json.dumps(
                    {
                        "acc": 1.2,
                        "cost": 1.5,
                        "latency": 150.0,
                        "metric_sources": ["candidate.csv"],
                        "subsets": {"multi_turn_base": 72.0},
                    }
                ),
                encoding="utf-8",
            )
            (candidate_dir / "failure_summary.json").write_text(json.dumps({"trace_count": 10}), encoding="utf-8")
            (candidate_dir / "rule.yaml").write_text(
                "patch_id: patch_002\nrules:\n  - rule_id: rule_ok\nsource_failure_count: 3\n",
                encoding="utf-8",
            )

            decision = select_patch(str(baseline_dir / "metrics.json"), str(candidate_dir / "metrics.json"))

        self.assertTrue(decision["baseline_valid"])
        self.assertTrue(decision["candidate_valid"])
        self.assertTrue(decision["accept"])
        self.assertEqual(decision["reason"], "candidate dominates baseline on Pareto criteria")


if __name__ == "__main__":
    unittest.main()
