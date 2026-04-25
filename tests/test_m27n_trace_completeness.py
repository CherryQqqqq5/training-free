from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.check_m27f_artifact_completeness import evaluate_artifact_completeness
from scripts.diagnose_m27n_trace_completeness import evaluate_trace_completeness
from scripts.run_phase2_target_subset import _trace_paths_by_case_from_prompt_prefix_with_diagnostics

CATEGORY = "multi_turn_miss_param"
CASE40 = "multi_turn_miss_param_40"
CASE43 = "multi_turn_miss_param_43"
FIRST = "shared first prompt"
SECOND40 = "case 40 second prompt"
SECOND43 = "case 43 second prompt"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _question(first: str, second: str) -> list[list[dict]]:
    return [[{"role": "user", "content": first}], [{"role": "user", "content": second}]]


def _write_manifest(root: Path, selected: list[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "paired_subset_manifest.json").write_text(
        json.dumps({"category": CATEGORY, "selected_case_ids": selected}, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_run(root: Path, run_name: str, selected: list[str], *, count: int = 2) -> Path:
    run = root / run_name
    result_rows = [{"id": case_id, "result": [[{"cat": "{}"}] for _ in range(count)]} for case_id in selected]
    _write_jsonl(run / "bfcl" / "result" / "model" / "multi_turn" / f"BFCL_v4_{CATEGORY}_result.json", result_rows)
    prompt_by_case = {CASE40: _question(FIRST, SECOND40), CASE43: _question(FIRST, SECOND43)}
    score_rows = [{"accuracy": 0.0, "correct_count": 0, "total_count": len(selected)}]
    for case_id in selected:
        score_rows.append({"id": case_id, "valid": False, "prompt": {"question": prompt_by_case[case_id]}})
    _write_jsonl(run / "bfcl" / "score" / "model" / "multi_turn" / f"BFCL_v4_{CATEGORY}_score.json", score_rows)
    return run


def _write_trace(run: Path, name: str, users: list[str], *, mtime: int) -> None:
    trace_dir = run / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    path = trace_dir / f"{name}.json"
    path.write_text(
        json.dumps({"request_original": {"input": [{"role": "user", "content": user} for user in users]}}),
        encoding="utf-8",
    )
    os.utime(path, (mtime, mtime))


class M27nTraceCompletenessTests(unittest.TestCase):
    def test_shared_first_prompt_is_split_by_expected_counts_and_trace_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            run = _write_run(root, "candidate", [CASE40, CASE43], count=2)
            for index in range(4):
                _write_trace(run, f"trace_{index}", [FIRST], mtime=100 + index)

            groups, diagnostic = _trace_paths_by_case_from_prompt_prefix_with_diagnostics(
                source_run_root=run,
                category=CATEGORY,
                selected_ids=[CASE40, CASE43],
            )

        self.assertEqual([path.name for path in groups[CASE40]], ["trace_0.json", "trace_1.json"])
        self.assertEqual([path.name for path in groups[CASE43]], ["trace_2.json", "trace_3.json"])
        self.assertFalse(diagnostic["unresolved_ambiguity"])
        self.assertEqual(diagnostic["resolved_ambiguous_match_sets"][0]["assigned_counts"], {CASE40: 2, CASE43: 2})

    def test_deeper_prompt_context_still_assigns_unique_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            run = _write_run(root, "candidate", [CASE40, CASE43], count=1)
            _write_trace(run, "trace_40", [FIRST, SECOND40], mtime=100)
            _write_trace(run, "trace_43", [FIRST, SECOND43], mtime=101)

            groups, diagnostic = _trace_paths_by_case_from_prompt_prefix_with_diagnostics(
                source_run_root=run,
                category=CATEGORY,
                selected_ids=[CASE40, CASE43],
            )

        self.assertEqual([path.name for path in groups[CASE40]], ["trace_40.json"])
        self.assertEqual([path.name for path in groups[CASE43]], ["trace_43.json"])
        self.assertFalse(diagnostic["unresolved_ambiguity"])

    def test_unresolved_ambiguity_fails_artifact_completeness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            _write_manifest(root, [CASE40, CASE43])
            baseline = _write_run(root, "baseline", [CASE40, CASE43], count=2)
            candidate = _write_run(root, "candidate", [CASE40, CASE43], count=2)
            for run in (baseline, candidate):
                for index in range(3):
                    _write_trace(run, f"trace_{index}", [FIRST], mtime=100 + index)

            report = evaluate_artifact_completeness(root, require_baseline_prompt_traces=True)

        self.assertFalse(report["m2_7f_artifact_completeness_passed"])
        self.assertTrue(report["runs"]["candidate"]["prompt_prefix_ambiguity_unresolved"])
        self.assertEqual(report["runs"]["candidate"]["prompt_prefix_mapping_diagnostic"]["unresolved_ambiguous_match_sets"][0]["reason"], "ambiguous_trace_count_below_expected")

    def test_complete_shared_prefix_artifacts_pass_and_diagnostic_marks_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            _write_manifest(root, [CASE40, CASE43])
            baseline = _write_run(root, "baseline", [CASE40, CASE43], count=2)
            candidate = _write_run(root, "candidate", [CASE40, CASE43], count=2)
            for run in (baseline, candidate):
                for index in range(4):
                    _write_trace(run, f"trace_{index}", [FIRST], mtime=100 + index)

            report = evaluate_trace_completeness(root)

        self.assertTrue(report["m2_7n_trace_completeness_passed"])
        self.assertEqual(report["runs"]["candidate"]["missing_trace_ids"], [])
        self.assertEqual(report["runs"]["candidate"]["cases"][CASE43]["diagnostic_branch"], "prompt_prefix_ambiguous_resolved")

    def test_score_result_complete_but_trace_missing_fails_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            root = Path(tmp_raw)
            _write_manifest(root, [CASE40, CASE43])
            baseline = _write_run(root, "baseline", [CASE40, CASE43], count=1)
            _write_run(root, "candidate", [CASE40, CASE43], count=1)
            _write_trace(baseline, "trace_40", [FIRST, SECOND40], mtime=100)
            _write_trace(baseline, "trace_43", [FIRST, SECOND43], mtime=101)

            report = evaluate_trace_completeness(root)

        self.assertFalse(report["m2_7n_trace_completeness_passed"])
        self.assertEqual(report["runs"]["candidate"]["missing_trace_ids"], [CASE40, CASE43])
        self.assertEqual(report["runs"]["candidate"]["cases"][CASE40]["diagnostic_branch"], "trace_write_failure")


if __name__ == "__main__":
    unittest.main()
