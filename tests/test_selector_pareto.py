from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from grc.selector.pareto import select_patch, write_selection_outputs


class ParetoSelectionTests(unittest.TestCase):
    @staticmethod
    def _write_manifest(path: Path, *, route: str = "x-ai/grok-3-beta") -> None:
        path.write_text(
            json.dumps(
                {
                    "protocol_id": "bfcl_v4_phase1",
                    "test_category": "simple_python",
                    "bfcl_model_alias": "gpt-4o-mini-2024-07-18-FC",
                    "upstream_profile": "openrouter",
                    "upstream_model_route": route,
                }
            ),
            encoding="utf-8",
        )

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
                        "evaluation_status": "complete",
                        "metric_sources": ["baseline.csv"],
                    }
                ),
                encoding="utf-8",
            )
            (baseline_dir / "failure_summary.json").write_text(json.dumps({"trace_count": 10}), encoding="utf-8")
            self._write_manifest(baseline_dir / "run_manifest.json")
            (candidate_dir / "metrics.json").write_text(
                json.dumps(
                    {
                        "acc": 1.0,
                        "cost": 1.0,
                        "latency": 50.0,
                        "evaluation_status": "incomplete",
                        "metric_sources": [],
                    }
                ),
                encoding="utf-8",
            )
            (candidate_dir / "failure_summary.json").write_text(json.dumps({"trace_count": 10}), encoding="utf-8")
            self._write_manifest(candidate_dir / "run_manifest.json")
            (candidate_dir / "rule.yaml").write_text(
                "patch_id: patch_001\nrules: []\nsource_failure_count: 0\n",
                encoding="utf-8",
            )
            (candidate_dir / "compile_status.json").write_text(
                json.dumps({"status": "uncompilable_failure_evidence"}),
                encoding="utf-8",
            )

            decision = select_patch(str(baseline_dir / "metrics.json"), str(candidate_dir / "metrics.json"))

        self.assertFalse(decision["accept"])
        self.assertFalse(decision["candidate_valid"])
        self.assertEqual(decision["decision_code"], "evaluation_incomplete")
        self.assertIn("evaluation_status != complete (incomplete)", decision["candidate_validity_issues"])
        self.assertIn("metric_sources empty", decision["candidate_validity_issues"])
        self.assertIn("source_failure_count <= 0", decision["candidate_validity_issues"])
        self.assertIn("rules empty", decision["candidate_validity_issues"])
        self.assertIn(
            "compile_status != actionable_patch (uncompilable_failure_evidence)",
            decision["candidate_validity_issues"],
        )

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
                        "evaluation_status": "complete",
                        "metric_sources": ["baseline.csv"],
                        "subsets": {"multi_turn_base": 70.0},
                    }
                ),
                encoding="utf-8",
            )
            (baseline_dir / "failure_summary.json").write_text(json.dumps({"trace_count": 10}), encoding="utf-8")
            self._write_manifest(baseline_dir / "run_manifest.json")
            (candidate_dir / "metrics.json").write_text(
                json.dumps(
                    {
                        "acc": 1.2,
                        "cost": 1.5,
                        "latency": 150.0,
                        "evaluation_status": "complete",
                        "metric_sources": ["candidate.csv"],
                        "subsets": {"multi_turn_base": 72.0},
                    }
                ),
                encoding="utf-8",
            )
            (candidate_dir / "failure_summary.json").write_text(json.dumps({"trace_count": 10}), encoding="utf-8")
            self._write_manifest(candidate_dir / "run_manifest.json")
            (candidate_dir / "rule.yaml").write_text(
                "patch_id: patch_002\nrules:\n  - rule_id: rule_ok\nsource_failure_count: 3\n",
                encoding="utf-8",
            )
            (candidate_dir / "compile_status.json").write_text(
                json.dumps({"status": "actionable_patch"}),
                encoding="utf-8",
            )

            decision = select_patch(str(baseline_dir / "metrics.json"), str(candidate_dir / "metrics.json"))

        self.assertTrue(decision["baseline_valid"])
        self.assertTrue(decision["candidate_valid"])
        self.assertTrue(decision["accept"])
        self.assertEqual(decision["decision_code"], "accepted")
        self.assertEqual(decision["reason"], "candidate dominates baseline on Pareto criteria")

    def test_blocks_selection_on_manifest_mismatch(self) -> None:
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
                        "evaluation_status": "complete",
                        "metric_sources": ["baseline.csv"],
                        "subsets": {"memory_kv": 27.0},
                    }
                ),
                encoding="utf-8",
            )
            (baseline_dir / "failure_summary.json").write_text(json.dumps({"trace_count": 10}), encoding="utf-8")
            self._write_manifest(baseline_dir / "run_manifest.json", route="x-ai/grok-3-beta")
            (candidate_dir / "metrics.json").write_text(
                json.dumps(
                    {
                        "acc": 1.2,
                        "cost": 1.5,
                        "latency": 150.0,
                        "evaluation_status": "complete",
                        "metric_sources": ["candidate.csv"],
                        "subsets": {"memory_kv": 28.0},
                    }
                ),
                encoding="utf-8",
            )
            (candidate_dir / "failure_summary.json").write_text(json.dumps({"trace_count": 10}), encoding="utf-8")
            self._write_manifest(candidate_dir / "run_manifest.json", route="gpt-5.4")
            (candidate_dir / "rule.yaml").write_text(
                "patch_id: patch_003\nrules:\n  - rule_id: rule_ok\nsource_failure_count: 3\n",
                encoding="utf-8",
            )
            (candidate_dir / "compile_status.json").write_text(
                json.dumps({"status": "actionable_patch"}),
                encoding="utf-8",
            )

            decision = select_patch(str(baseline_dir / "metrics.json"), str(candidate_dir / "metrics.json"))

        self.assertFalse(decision["accept"])
        self.assertFalse(decision["manifest_valid"])
        self.assertIn("upstream_model_route mismatch", decision["manifest_consistency_issues"][0])

    def test_write_selection_outputs_removes_stale_accepted_and_active_on_reject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate_dir = root / "patch_sync_001"
            accepted_dir = root / "accepted"
            rejected_dir = root / "rejected"
            active_dir = root / "active"
            candidate_dir.mkdir()
            accepted_dir.mkdir()
            rejected_dir.mkdir()
            active_dir.mkdir()

            rule_path = candidate_dir / "rule.yaml"
            rule_path.write_text("patch_id: patch_sync_001\nrules:\n  - rule_id: rule_ok\nsource_failure_count: 1\n", encoding="utf-8")
            (candidate_dir / "metrics.json").write_text("{}", encoding="utf-8")

            stale_accepted = accepted_dir / "patch_sync_001"
            stale_accepted.mkdir()
            (stale_accepted / "rule.yaml").write_text("stale", encoding="utf-8")
            stale_active = active_dir / "patch_sync_001.yaml"
            stale_active.write_text("stale", encoding="utf-8")

            write_selection_outputs(
                {"accept": False},
                str(candidate_dir),
                str(rule_path),
                str(accepted_dir),
                str(rejected_dir),
                str(active_dir),
                None,
            )
            self.assertFalse(stale_accepted.exists())
            self.assertFalse(stale_active.exists())
            self.assertTrue((rejected_dir / "patch_sync_001").exists())


if __name__ == "__main__":
    unittest.main()
