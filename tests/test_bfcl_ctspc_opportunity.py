from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.scan_bfcl_ctspc_opportunities import scan_opportunities, select_opportunities, summarize_opportunities


def _write_score(root: Path, rows: list[dict]) -> None:
    score = root / "bfcl" / "score" / "model" / "multi_turn" / "BFCL_v4_multi_turn_miss_param_score.json"
    score.parent.mkdir(parents=True)
    lines = [json.dumps({"accuracy": 0.0})]
    lines.extend(json.dumps(row) for row in rows)
    score.write_text("\n".join(lines) + "\n", encoding="utf-8")


class BfclCtspcOpportunityTests(unittest.TestCase):
    def test_scanner_uses_prompt_path_and_selects_baseline_wrong_schema_local_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            _write_score(
                root,
                [
                    {
                        "id": "multi_turn_miss_param_1",
                        "valid": False,
                        "prompt": {
                            "path": ["GorillaFileSystem.cat"],
                            "question": [[{"role": "user", "content": "read file"}]],
                        },
                    },
                    {
                        "id": "multi_turn_miss_param_2",
                        "valid": False,
                        "prompt": {
                            "path": ["TravelAPI.book_flight"],
                            "question": [[{"role": "user", "content": "read file"}]],
                        },
                    },
                    {
                        "id": "multi_turn_miss_param_3",
                        "valid": True,
                        "prompt": {
                            "path": ["GorillaFileSystem.touch"],
                            "question": [[{"role": "user", "content": "touch file"}]],
                        },
                    },
                ],
            )

            rows = scan_opportunities(root, "multi_turn_miss_param")
            selected = select_opportunities(rows, max_cases=30)
            summary = summarize_opportunities(rows, selected)

        self.assertEqual(summary["total_cases"], 3)
        self.assertEqual(summary["schema_local_case_count"], 2)
        self.assertEqual(summary["candidate_generatable_count"], 2)
        self.assertEqual([row["case_id"] for row in selected], ["multi_turn_miss_param_1"])
        self.assertEqual(summary["cases_by_target_tool"], {"cat": 1, "touch": 1})

    def test_scan_script_writes_compact_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            out = root / "out"
            _write_score(
                root,
                [
                    {
                        "id": "multi_turn_miss_param_1",
                        "valid": False,
                        "prompt": {"path": ["GorillaFileSystem.cat"], "question": [[{"role": "user", "content": "read"}]]},
                    }
                ],
            )

            subprocess.run(
                [
                    sys.executable,
                    "scripts/scan_bfcl_ctspc_opportunities.py",
                    "--source-run-root",
                    str(root),
                    "--out-root",
                    str(out),
                    "--max-cases",
                    "30",
                ],
                cwd=Path.cwd(),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            summary = json.loads((out / "scan_summary.json").read_text(encoding="utf-8"))
            scan_report_exists = (out / "scan_report.jsonl").exists()
            table_exists = (out / "category_opportunity_table.md").exists()

        self.assertEqual(summary["selected_case_count"], 1)
        self.assertTrue(scan_report_exists)
        self.assertTrue(table_exists)

    def test_paired_subset_dry_run_generates_manifest_and_commands_when_gate_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            out = root / "paired"
            rules = root / "rules"
            rules.mkdir()
            (rules / "rule.yaml").write_text("rules: []\n", encoding="utf-8")
            rows = []
            for index in range(30):
                rows.append(
                    {
                        "id": f"multi_turn_miss_param_{index}",
                        "valid": False,
                        "prompt": {
                            "path": ["GorillaFileSystem.cat"],
                            "question": [[{"role": "user", "content": "read"}]],
                        },
                    }
                )
            _write_score(root, rows)

            subprocess.run(
                [
                    sys.executable,
                    "scripts/run_bfcl_ctspc_paired_subset.py",
                    "--source-run-root",
                    str(root),
                    "--out-root",
                    str(out),
                    "--candidate-rules-dir",
                    str(rules),
                ],
                cwd=Path.cwd(),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            manifest = json.loads((out / "paired_subset_manifest.json").read_text(encoding="utf-8"))
            ids_file_exists = (out / "baseline" / "bfcl" / "test_case_ids_to_generate.json").exists()

        self.assertTrue(manifest["gate_passed"])
        self.assertTrue(manifest["candidate_rules_available"])
        self.assertEqual(len(manifest["selected_case_ids"]), 30)
        self.assertEqual(len(manifest["planned_commands"]), 2)
        self.assertTrue(ids_file_exists)

    def test_paired_subset_dry_run_fails_gate_without_commands_when_too_few_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            out = root / "paired"
            rules = root / "rules"
            rules.mkdir()
            (rules / "rule.yaml").write_text("rules: []\n", encoding="utf-8")
            _write_score(
                root,
                [
                    {
                        "id": "multi_turn_miss_param_1",
                        "valid": False,
                        "prompt": {"path": ["GorillaFileSystem.cat"], "question": [[{"role": "user", "content": "read"}]]},
                    }
                ],
            )

            subprocess.run(
                [
                    sys.executable,
                    "scripts/run_bfcl_ctspc_paired_subset.py",
                    "--source-run-root",
                    str(root),
                    "--out-root",
                    str(out),
                    "--candidate-rules-dir",
                    str(rules),
                ],
                cwd=Path.cwd(),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            manifest = json.loads((out / "paired_subset_manifest.json").read_text(encoding="utf-8"))

        self.assertFalse(manifest["gate_passed"])
        self.assertEqual(manifest["planned_commands"], [])


if __name__ == "__main__":
    unittest.main()
