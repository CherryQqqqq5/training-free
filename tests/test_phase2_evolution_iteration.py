from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class Phase2EvolutionIterationTests(unittest.TestCase):
    def test_dry_run_emits_planned_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            target = root / "target"
            holdout = root / "holdout"
            history = root / "history.jsonl"
            out = root / "out"
            for path in (baseline / "traces", target / "traces", holdout / "traces"):
                path.mkdir(parents=True)
            history.write_text("", encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "scripts/run_phase2_evolution_iteration.py",
                    "--repo-root",
                    str(root),
                    "--baseline-run-root",
                    str(baseline),
                    "--target-run-root",
                    str(target),
                    "--holdout-run-root",
                    str(holdout),
                    "--history",
                    str(history),
                    "--out-root",
                    str(out),
                    "--dry-run",
                ],
                check=True,
                cwd="/Users/cherry/mnt/training-free",
            )
            summary = json.loads((out / "evolution_iteration_summary.json").read_text(encoding="utf-8"))
        self.assertIn("run_bfcl_v4_patch.sh", "\n".join(summary["planned_commands"]))

    def test_execute_requires_holdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            target = root / "target"
            history = root / "history.jsonl"
            out = root / "out"
            for path in (baseline / "traces", target / "traces"):
                path.mkdir(parents=True)
            history.write_text("", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/run_phase2_evolution_iteration.py",
                    "--repo-root",
                    str(root),
                    "--baseline-run-root",
                    str(baseline),
                    "--target-run-root",
                    str(target),
                    "--history",
                    str(history),
                    "--out-root",
                    str(out),
                    "--execute",
                ],
                cwd="/Users/cherry/mnt/training-free",
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("holdout", result.stderr + result.stdout)
