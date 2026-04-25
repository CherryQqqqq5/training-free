from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.diagnose_m27o_candidate_quality import evaluate_candidate_quality


class M27OCandidateQualityTests(unittest.TestCase):
    def _write_fixture(self, root: Path, *, candidates: list[dict], exact_mode: str = "guidance_only") -> tuple[Path, Path]:
        root.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                "case_id": "case_fixed",
                "policy_plan_activated": True,
                "candidate_success": True,
                "recommended_tool_match": True,
                "raw_normalized_arg_match": True,
                "case_fixed": True,
                "case_regressed": False,
            },
            {
                "case_id": "case_traj_fail",
                "policy_plan_activated": True,
                "candidate_success": False,
                "recommended_tool_match": True,
                "raw_normalized_arg_match": True,
                "case_fixed": False,
                "case_regressed": False,
            },
        ]
        with (root / "subset_case_report.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
        rule_path = root / "rule.yaml"
        rule_path.write_text(
            yaml.safe_dump(
                {
                    "patch_id": "test",
                    "rules": [
                        {
                            "rule_id": "rule_1",
                            "action": {"decision_policy": {"action_candidates": candidates}},
                        }
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        config_path = root / "runtime.yaml"
        config_path.write_text(yaml.safe_dump({"runtime_policy": {"exact_next_tool_choice_mode": exact_mode}}), encoding="utf-8")
        return rule_path, config_path

    def _good_candidate(self) -> dict:
        return {
            "tool": "cat",
            "args": {"file_name": "report.txt"},
            "postcondition": {"kind": "file_content", "expected_state_key": "file_content", "target_arg": "file_name", "confidence": 0.8},
            "trajectory_risk_score": 2,
            "trajectory_risk_flags": ["trajectory_sensitive_tool"],
            "binding_type": "file",
            "intervention_mode": "guidance",
        }

    def test_quality_gate_passes_for_typed_low_risk_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rule_path, config_path = self._write_fixture(root, candidates=[self._good_candidate()])
            report = evaluate_candidate_quality(root, rule_path=rule_path, runtime_config=config_path)

        self.assertTrue(report["candidate_quality_gate_passed"])
        self.assertEqual(report["postcondition_missing_count"], 0)
        self.assertEqual(report["file_dir_type_mismatch_count"], 0)
        self.assertEqual(report["high_risk_candidate_intervention_count"], 0)
        self.assertEqual(report["case_failure_layer_distribution"]["local_tool_arg_match_but_trajectory_fail"], 1)

    def test_quality_gate_fails_for_missing_postcondition(self) -> None:
        candidate = {"tool": "cat", "args": {"file_name": "report.txt"}, "intervention_mode": "guidance"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rule_path, config_path = self._write_fixture(root, candidates=[candidate])
            report = evaluate_candidate_quality(root, rule_path=rule_path, runtime_config=config_path)

        self.assertFalse(report["candidate_quality_gate_passed"])
        self.assertEqual(report["postcondition_missing_count"], 1)
        self.assertEqual(report["diagnostic"]["first_failed_criterion"], "postcondition_missing_count")

    def test_quality_gate_fails_for_file_directory_type_mismatch(self) -> None:
        candidate = self._good_candidate()
        candidate.update({"tool": "mkdir", "args": {"dir_name": "final_report.pdf"}, "binding_type": "directory"})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rule_path, config_path = self._write_fixture(root, candidates=[candidate])
            report = evaluate_candidate_quality(root, rule_path=rule_path, runtime_config=config_path)

        self.assertFalse(report["candidate_quality_gate_passed"])
        self.assertEqual(report["file_dir_type_mismatch_count"], 1)

    def test_quality_gate_fails_for_high_risk_guidance_intervention(self) -> None:
        candidate = self._good_candidate()
        candidate.update({"trajectory_risk_score": 7, "trajectory_risk_flags": ["weak_cwd_or_listing_binding"]})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rule_path, config_path = self._write_fixture(root, candidates=[candidate])
            report = evaluate_candidate_quality(root, rule_path=rule_path, runtime_config=config_path)

        self.assertFalse(report["candidate_quality_gate_passed"])
        self.assertEqual(report["high_risk_candidate_intervention_count"], 1)

    def test_quality_gate_fails_when_runtime_not_guidance_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rule_path, config_path = self._write_fixture(
                root,
                candidates=[self._good_candidate()],
                exact_mode="exact_tool_when_single_step_confident",
            )
            report = evaluate_candidate_quality(root, rule_path=rule_path, runtime_config=config_path)

        self.assertFalse(report["candidate_quality_gate_passed"])
        self.assertIn("guidance_only_mode", report["diagnostic"]["failed_criteria"])


if __name__ == "__main__":
    unittest.main()
