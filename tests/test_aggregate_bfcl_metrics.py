from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
