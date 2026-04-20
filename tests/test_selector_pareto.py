from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grc.selector.pareto import select_patch


def _write_manifest(path: Path, *, route: str = "x-ai/grok") -> None:
    path.write_text(
        json.dumps(
            {
                "bfcl_model_alias": "demo",
                "upstream_profile": "openrouter",
                "upstream_model_route": route,
                "protocol_id": "bfcl.v4",
                "test_category": "simple_python",
            }
        ),
        encoding="utf-8",
    )


class ParetoSelectionTests(unittest.TestCase):
    def test_rejects_evaluation_incomplete_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_dir = root / "baseline"
            candidate_dir = root / "candidate"
            baseline_dir.mkdir()
            candidate_dir.mkdir()

            (baseline_dir / "metrics.json").write_text(
                json.dumps({"acc": 1.0, "cost": 1.0, "latency": 100.0, "metric_sources": ["a.csv"], "evaluation_status": "complete"}),
                encoding="utf-8",
            )
            (candidate_dir / "metrics.json").write_text(
                json.dumps({"acc": 1.2, "cost": 0.8, "latency": 90.0, "metric_sources": ["b.csv"], "evaluation_status": "incomplete", "artifact_validity_issues": ["subset metric missing"]}),
                encoding="utf-8",
            )
            (baseline_dir / "failure_summary.json").write_text(json.dumps({"trace_count": 10}), encoding="utf-8")
            (candidate_dir / "failure_summary.json").write_text(json.dumps({"trace_count": 10}), encoding="utf-8")
            _write_manifest(baseline_dir / "run_manifest.json")
            _write_manifest(candidate_dir / "run_manifest.json")

            decision = select_patch(
                str(baseline_dir / "metrics.json"),
                str(candidate_dir / "metrics.json"),
                baseline_manifest_path=str(baseline_dir / "run_manifest.json"),
                candidate_manifest_path=str(candidate_dir / "run_manifest.json"),
                compile_status_path=None,
            )

        self.assertFalse(decision["accept"])
        self.assertEqual(decision["reason"], "evaluation_incomplete")

    def test_blocks_manifest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_dir = root / "baseline"
            candidate_dir = root / "candidate"
            baseline_dir.mkdir()
            candidate_dir.mkdir()

            metric_payload = {"acc": 1.0, "cost": 1.0, "latency": 100.0, "metric_sources": ["a.csv"], "evaluation_status": "complete"}
            (baseline_dir / "metrics.json").write_text(json.dumps(metric_payload), encoding="utf-8")
            (candidate_dir / "metrics.json").write_text(json.dumps({**metric_payload, "acc": 1.1}), encoding="utf-8")
            (baseline_dir / "failure_summary.json").write_text(json.dumps({"trace_count": 10}), encoding="utf-8")
            (candidate_dir / "failure_summary.json").write_text(json.dumps({"trace_count": 10}), encoding="utf-8")
            _write_manifest(baseline_dir / "run_manifest.json", route="x-ai/grok")
            _write_manifest(candidate_dir / "run_manifest.json", route="openai/o4")
            (candidate_dir / "compile_status.json").write_text(json.dumps({"status": "actionable_patch"}), encoding="utf-8")

            decision = select_patch(
                str(baseline_dir / "metrics.json"),
                str(candidate_dir / "metrics.json"),
                baseline_manifest_path=str(baseline_dir / "run_manifest.json"),
                candidate_manifest_path=str(candidate_dir / "run_manifest.json"),
                compile_status_path=str(candidate_dir / "compile_status.json"),
            )

        self.assertFalse(decision["accept"])
        self.assertEqual(decision["reason"], "candidate_invalid")
        self.assertTrue(any("upstream_model_route" in issue for issue in decision["manifest_validity_issues"]))


if __name__ == "__main__":
    unittest.main()
