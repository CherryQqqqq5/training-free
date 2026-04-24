from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.aggregate_bfcl_metrics import discover_bfcl_metrics


class AggregateBfclMetricsTests(unittest.TestCase):
    def test_discovers_metrics_from_csv_and_json_stream(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            score_dir = root / "score"
            score_dir.mkdir(parents=True)
            (score_dir / "data_overall.csv").write_text(
                "\n".join(
                    [
                        "Rank,Overall Acc,Model,Total Cost ($),Latency Mean (s),Multi Turn Miss Param",
                        "1,2.28%,demo-model,1.25,3.44,91.0%",
                    ]
                ),
                encoding="utf-8",
            )
            (score_dir / "data_multi_turn.csv").write_text(
                "\n".join(
                    [
                        "Rank,Model,Multi Turn Overall Acc,Base,Miss Param",
                        "1,demo-model,80.0%,75.0%,91.0%",
                    ]
                ),
                encoding="utf-8",
            )
            result_dir = root / "result"
            result_dir.mkdir(parents=True)
            (result_dir / "summary.json").write_text(
                '{"overall_accuracy": 3.0}\n{"metrics_by_subset": {"json_stream_subset": 4.0}}',
                encoding="utf-8",
            )

            overall, subsets, sources = discover_bfcl_metrics(root)

        self.assertEqual(overall["acc"], 2.28)
        self.assertEqual(overall["cost"], 1.25)
        self.assertEqual(overall["latency"], 3440.0)
        self.assertEqual(subsets["multi_turn_miss_param"], 91.0)
        self.assertEqual(subsets["multi_turn_overall_acc"], 80.0)
        self.assertEqual(subsets["multi_turn_base"], 75.0)
        self.assertEqual(subsets["json_stream_subset"], 4.0)
        self.assertTrue(any(path.endswith("data_overall.csv") for path in sources))
        self.assertTrue(any(path.endswith("summary.json") for path in sources))

    def test_result_json_latency_is_normalized_to_ms_via_trace_summary_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bfcl_root = root / "bfcl"
            trace_dir = root / "traces"
            artifacts_dir = root / "artifacts"
            result_dir = bfcl_root / "result"
            result_dir.mkdir(parents=True)
            trace_dir.mkdir(parents=True)
            artifacts_dir.mkdir(parents=True)

            (result_dir / "BFCL_v4_demo_result.json").write_text(
                '{"id":"demo_0","result":"x","latency":2.5}\n',
                encoding="utf-8",
            )
            (trace_dir / "trace.json").write_text(
                '{"trace_id":"trace","status_code":200,"latency_ms":2500.0,"validation":{"issues":[]}}\n',
                encoding="utf-8",
            )

            out = artifacts_dir / "metrics.json"
            repairs = artifacts_dir / "repairs.jsonl"
            summary = artifacts_dir / "failure_summary.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/aggregate_bfcl_metrics.py",
                    "--bfcl-root",
                    str(bfcl_root),
                    "--trace-dir",
                    str(trace_dir),
                    "--out",
                    str(out),
                    "--repairs-out",
                    str(repairs),
                    "--failure-summary-out",
                    str(summary),
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            metrics = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(metrics["latency"], 2500.0)
        self.assertEqual(metrics["evaluation_status"], "incomplete")
        self.assertIn("score source missing", metrics["artifact_validity_issues"])

    def test_complete_evaluation_requires_semantic_score_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bfcl_root = root / "bfcl"
            trace_dir = root / "traces"
            artifacts_dir = root / "artifacts"
            score_dir = bfcl_root / "score"
            result_dir = bfcl_root / "result"
            score_dir.mkdir(parents=True)
            result_dir.mkdir(parents=True)
            trace_dir.mkdir(parents=True)
            artifacts_dir.mkdir(parents=True)

            (score_dir / "data_overall.csv").write_text(
                "\n".join(
                    [
                        "Rank,Overall Acc,Model,Total Cost ($),Latency Mean (s),Memory Kv",
                        "1,demo-model,1.25,3.44,27.74%",
                    ]
                ).replace("1,demo-model", "1,27.74%,demo-model"),
                encoding="utf-8",
            )
            (score_dir / "BFCL_v4_memory_kv_score.json").write_text(
                json.dumps({"accuracy": 0.2774}),
                encoding="utf-8",
            )
            (result_dir / "BFCL_v4_memory_kv_result.json").write_text(
                json.dumps({"id": "demo_0", "ok": True}),
                encoding="utf-8",
            )
            (trace_dir / "trace.json").write_text(
                '{"trace_id":"trace","status_code":200,"latency_ms":2500.0,"validation":{"issues":[]}}\n',
                encoding="utf-8",
            )

            out = artifacts_dir / "metrics.json"
            repairs = artifacts_dir / "repairs.jsonl"
            summary = artifacts_dir / "failure_summary.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/aggregate_bfcl_metrics.py",
                    "--bfcl-root",
                    str(bfcl_root),
                    "--trace-dir",
                    str(trace_dir),
                    "--out",
                    str(out),
                    "--repairs-out",
                    str(repairs),
                    "--failure-summary-out",
                    str(summary),
                    "--test-category",
                    "memory_kv",
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            metrics = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(metrics["evaluation_status"], "complete")
        self.assertEqual(metrics["artifact_validity_issues"], [])
        self.assertTrue(metrics["resolved_result_sources"])
        self.assertTrue(metrics["resolved_score_sources"])

    def test_nested_partial_eval_sources_satisfy_artifact_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bfcl_root = root / "bfcl"
            trace_dir = root / "traces"
            artifacts_dir = root / "artifacts"
            score_dir = bfcl_root / "outputs" / "phase2" / "score" / "model" / "multi_turn"
            result_dir = bfcl_root / "outputs" / "phase2" / "result" / "model" / "multi_turn"
            score_dir.mkdir(parents=True)
            result_dir.mkdir(parents=True)
            trace_dir.mkdir(parents=True)
            artifacts_dir.mkdir(parents=True)

            (score_dir / "BFCL_v4_multi_turn_miss_param_score.json").write_text(
                json.dumps({"accuracy": 0.1, "correct_count": 1, "total_count": 10})
                + "\n"
                + json.dumps({"id": "multi_turn_miss_param_1", "valid": True})
                + "\n",
                encoding="utf-8",
            )
            (result_dir / "BFCL_v4_multi_turn_miss_param_result.json").write_text(
                json.dumps({"id": "multi_turn_miss_param_1", "result": []}) + "\n",
                encoding="utf-8",
            )
            (trace_dir / "trace.json").write_text(
                '{"trace_id":"trace","status_code":200,"latency_ms":2500.0,"validation":{"issues":[]}}\n',
                encoding="utf-8",
            )

            out = artifacts_dir / "metrics.json"
            repairs = artifacts_dir / "repairs.jsonl"
            summary = artifacts_dir / "failure_summary.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/aggregate_bfcl_metrics.py",
                    "--bfcl-root",
                    str(bfcl_root),
                    "--trace-dir",
                    str(trace_dir),
                    "--out",
                    str(out),
                    "--repairs-out",
                    str(repairs),
                    "--failure-summary-out",
                    str(summary),
                    "--test-category",
                    "multi_turn_miss_param",
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            metrics = json.loads(out.read_text(encoding="utf-8"))

        self.assertNotIn("result source missing", metrics["artifact_validity_issues"])
        self.assertNotIn("score source missing", metrics["artifact_validity_issues"])
        self.assertTrue(metrics["resolved_result_sources"])
        self.assertTrue(metrics["resolved_score_sources"])


if __name__ == "__main__":
    unittest.main()
