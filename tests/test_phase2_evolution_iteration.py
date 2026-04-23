from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.run_phase2_evolution_iteration as runner
REPO_ROOT = Path(__file__).resolve().parent.parent


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
                cwd=str(REPO_ROOT),
            )
            summary = json.loads((out / "evolution_iteration_summary.json").read_text(encoding="utf-8"))
        self.assertIn("run_bfcl_v4_patch.sh", "\n".join(summary["planned_commands"]))
        self.assertIn("--baseline ", "\n".join(summary["planned_commands"]))
        self.assertIn("--candidate-dir", "\n".join(summary["planned_commands"]))
        self.assertIn("fresh_00", "\n".join(summary["planned_commands"]))

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
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("holdout", result.stderr + result.stdout)

    def test_select_candidate_dir_prefers_actionable_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fresh = root / "fresh_00"
            reuse = root / "reuse_00_patch_old"
            fresh.mkdir()
            reuse.mkdir()
            (fresh / "compile_status.json").write_text(json.dumps({"status": "incomplete"}), encoding="utf-8")
            (reuse / "compile_status.json").write_text(json.dumps({"status": "actionable_patch"}), encoding="utf-8")
            proposal_summary = root / "proposal_summary.json"
            proposal_summary.write_text(
                json.dumps(
                    {
                        "proposals": [
                            {"candidate_dir": str(fresh), "proposal_mode": "fresh"},
                            {"candidate_dir": str(reuse), "proposal_mode": "reuse"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            selected = runner._select_candidate_dir(proposal_summary, max_candidates=1)

        self.assertEqual(selected, reuse)

    def test_execute_rejects_unbounded_candidate_count(self) -> None:
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
                    "--holdout-run-root",
                    str(holdout),
                    "--history",
                    str(history),
                    "--out-root",
                    str(out),
                    "--execute",
                    "--max-candidates",
                    "4",
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("1 to 3", result.stderr + result.stdout)

    def test_execute_writes_summary_from_real_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            target = root / "target"
            holdout = root / "holdout"
            history = root / "history.jsonl"
            out = root / "out"
            for path in (baseline / "traces", target / "traces", holdout / "traces", baseline / "artifacts", holdout / "artifacts"):
                path.mkdir(parents=True)
            history.write_text("", encoding="utf-8")
            (baseline / "artifacts" / "metrics.json").write_text(
                json.dumps({"test_category": "multi_turn_miss_param", "subsets": {"multi_turn_miss_param": 36.5}}),
                encoding="utf-8",
            )
            (holdout / "artifacts" / "metrics.json").write_text(
                json.dumps({"test_category": "simple_python", "subsets": {"simple_python": 90.0}}),
                encoding="utf-8",
            )

            def fake_run(command: str, *, step_name: str, out_root: Path) -> None:
                out.mkdir(parents=True, exist_ok=True)
                proposal_root = out / "proposals"
                candidate_dir = proposal_root / "fresh_00"
                if "build_phase2_taxonomy_report.py" in command:
                    (out / "taxonomy_report.json").write_text(
                        json.dumps(
                            {
                                "runs": [
                                    {
                                        "run": "primary_v4",
                                        "taxonomy_distribution": [
                                            {"failure_label": "(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)", "share": 0.5},
                                        ],
                                    }
                                ]
                            }
                        ),
                        encoding="utf-8",
                    )
                elif "python -m grc.cli propose" in command:
                    candidate_dir.mkdir(parents=True, exist_ok=True)
                    (candidate_dir / "compile_status.json").write_text(json.dumps({"status": "actionable_patch"}), encoding="utf-8")
                    (candidate_dir / "proposal_metadata.json").write_text(json.dumps({"proposal_mode": "fresh"}), encoding="utf-8")
                    (candidate_dir / "rule.yaml").write_text("patch_id: fresh_00\nsource_failure_count: 1\nrules:\n  - rule_id: rule_1\n", encoding="utf-8")
                    (proposal_root / "proposal_summary.json").write_text(
                        json.dumps(
                            {
                                "proposals": [{"candidate_dir": str(candidate_dir), "proposal_mode": "fresh"}],
                                "top_failure_signatures": [{"signature": "sig"}],
                            }
                        ),
                        encoding="utf-8",
                    )
                elif step_name.endswith("_target_run"):
                    candidate_dir.mkdir(parents=True, exist_ok=True)
                    (candidate_dir / "metrics.json").write_text(
                        json.dumps({"test_category": "multi_turn_miss_param", "subsets": {"multi_turn_miss_param": 40.0}}),
                        encoding="utf-8",
                    )
                elif step_name.endswith("_holdout_run"):
                    holdout_artifacts = out / "candidate_runs" / candidate_dir.name / "holdout" / "artifacts"
                    holdout_artifacts.mkdir(parents=True, exist_ok=True)
                    (holdout_artifacts / "metrics.json").write_text(
                        json.dumps({"test_category": "simple_python", "subsets": {"simple_python": 91.0}}),
                        encoding="utf-8",
                    )
                elif step_name.endswith("_rerun"):
                    rerun_dir = candidate_dir / "rerun"
                    rerun_dir.mkdir(parents=True, exist_ok=True)
                    (rerun_dir / "metrics.json").write_text(
                        json.dumps({"test_category": "multi_turn_miss_param", "subsets": {"multi_turn_miss_param": 41.0}}),
                        encoding="utf-8",
                    )
                elif "assess_paired_rerun.py" in command:
                    (candidate_dir / "paired_rerun.json").write_text(
                        json.dumps({"paired_rerun_consistent": True}),
                        encoding="utf-8",
                    )
                elif "python -m grc.cli select" in command:
                    (candidate_dir / "accept.json").write_text(
                        json.dumps({"decision_code": "accepted", "target_delta": 3.5}),
                        encoding="utf-8",
                    )

            argv = [
                "run_phase2_evolution_iteration.py",
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
                "--execute",
            ]
            with patch.object(sys, "argv", argv):
                with patch.object(runner, "_run_logged_command", side_effect=fake_run):
                    runner.main()

            summary = json.loads((out / "evolution_iteration_summary.json").read_text(encoding="utf-8"))

        self.assertEqual(summary["mode"], "execute")
        self.assertEqual(summary["selected_proposal_mode"], "fresh")
        self.assertEqual(summary["evaluated_candidate_count"], 1)
        self.assertEqual(summary["accepted_count"], 1)
        self.assertEqual(summary["target_delta"], 3.5)
        self.assertEqual(summary["holdout_delta"], 1.0)
        self.assertEqual(summary["clean_slice_regression"], 0.0)

    def test_logged_command_writes_failure_state_and_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"

            with self.assertRaises(subprocess.CalledProcessError):
                runner._run_logged_command(
                    "echo before-fail && exit 7",
                    step_name="target_run",
                    out_root=out,
                )

            status = json.loads((out / "step_status" / "target_run.json").read_text(encoding="utf-8"))
            failure = json.loads((out / "failure_state.json").read_text(encoding="utf-8"))
            log_text = (out / "logs" / "target_run.log").read_text(encoding="utf-8")

        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["returncode"], 7)
        self.assertEqual(failure["step"], "target_run")
        self.assertIn("before-fail", log_text)

    def test_execute_fails_fast_on_reference_route_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            target = root / "target"
            holdout = root / "holdout"
            history = root / "history.jsonl"
            out = root / "out"
            for run_root, route in ((baseline, "x-ai/grok-3"), (target, "x-ai/grok-3-beta"), (holdout, "x-ai/grok-3")):
                (run_root / "traces").mkdir(parents=True)
                (run_root / "artifacts").mkdir(parents=True)
                (run_root / "artifacts" / "run_manifest.json").write_text(
                    json.dumps({"upstream_model_route": route}),
                    encoding="utf-8",
                )
            history.write_text("", encoding="utf-8")
            argv = [
                "run_phase2_evolution_iteration.py",
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
                "--execute",
            ]
            with patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit) as raised:
                    runner.main()

        self.assertIn("upstream_model_route mismatch", str(raised.exception))

    def test_candidate_selection_failure_writes_failure_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            target = root / "target"
            holdout = root / "holdout"
            history = root / "history.jsonl"
            out = root / "out"
            for path in (baseline / "traces", target / "traces", holdout / "traces", baseline / "artifacts", holdout / "artifacts"):
                path.mkdir(parents=True)
            history.write_text("", encoding="utf-8")

            def fake_run(command: str, *, step_name: str, out_root: Path) -> None:
                proposal_root = out / "proposals"
                candidate_dir = proposal_root / "fresh_00"
                if step_name == "propose":
                    candidate_dir.mkdir(parents=True, exist_ok=True)
                    (candidate_dir / "compile_status.json").write_text(json.dumps({"status": "uncompilable_failure_evidence"}), encoding="utf-8")
                    (proposal_root / "proposal_summary.json").write_text(
                        json.dumps({"proposals": [{"candidate_dir": str(candidate_dir), "proposal_mode": "fresh"}]}),
                        encoding="utf-8",
                    )

            argv = [
                "run_phase2_evolution_iteration.py",
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
                "--execute",
            ]
            with patch.object(sys, "argv", argv):
                with patch.object(runner, "_run_logged_command", side_effect=fake_run):
                    with self.assertRaises(SystemExit):
                        runner.main()

            failure = json.loads((out / "failure_state.json").read_text(encoding="utf-8"))

        self.assertEqual(failure["step"], "select_candidate")
        self.assertIn("no executable candidate", failure["reason"])
