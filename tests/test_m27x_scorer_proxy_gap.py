
from __future__ import annotations

import json
from pathlib import Path

from scripts.diagnose_m27x_scorer_proxy_gap import evaluate
from scripts.build_m27y_scorer_feedback import build_feedback


def _wj(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def _wjl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_scorer_proxy_gap_classifies_tool_arg_and_trajectory_failures(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    _wj(root / "subset_summary.json", {
        "baseline_accuracy": 13.33,
        "candidate_accuracy": 6.67,
        "net_case_gain": -2,
        "recommended_tool_match_rate_among_activated": 0.6,
        "raw_normalized_arg_match_rate_among_activated": 0.4,
    })
    _wj(root / "m27tw_offline_summary.json", {
        "tool_ranking": {"offline_recommended_tool_match_proxy": 1.0},
        "arg_realization": {"raw_arg_match_rate_proxy": 1.0},
    })
    _wj(root / "m27q_postmortem.json", {"recommended_next_focus": "regression_and_rule_retention"})
    _wj(root / "m27v_arg_realization.json", {"cases": [
        {"case_id": "tool", "selected_tool": "cat", "candidate_arg_json": {"file_name": "a.txt"}, "arg_realization_proxy_ready": True},
        {"case_id": "arg", "selected_tool": "cat", "candidate_arg_json": {"file_name": "b.txt"}, "arg_realization_proxy_ready": True},
        {"case_id": "traj", "selected_tool": "touch", "candidate_arg_json": {"file_name": "c.txt"}, "arg_realization_proxy_ready": True},
    ]})
    _wjl(root / "subset_case_report.jsonl", [
        {"case_id": "tool", "policy_plan_activated": True, "selected_next_tool": "cat", "recommended_tool_match": False, "raw_normalized_arg_match": True, "baseline_success": False, "candidate_success": False, "case_fixed": False, "case_regressed": False},
        {"case_id": "arg", "policy_plan_activated": True, "selected_next_tool": "cat", "recommended_tool_match": True, "raw_normalized_arg_match": False, "baseline_success": False, "candidate_success": False, "case_fixed": False, "case_regressed": False},
        {"case_id": "traj", "policy_plan_activated": True, "selected_next_tool": "touch", "recommended_tool_match": True, "raw_normalized_arg_match": True, "baseline_success": True, "candidate_success": False, "case_fixed": False, "case_regressed": True},
    ])

    report = evaluate(root)

    assert report["m27x_scorer_proxy_gap_explained"] is True
    assert report["m27x_scorer_proxy_gap_passed"] is False
    assert report["gap_type_distribution"]["proxy_tool_ok_scorer_tool_wrong"] == 1
    assert report["gap_type_distribution"]["proxy_arg_ok_scorer_arg_wrong"] == 1
    assert report["gap_type_distribution"]["proxy_ok_trajectory_failed"] == 1
    assert report["regressed_case_count"] == 1


def test_fixed_by_code_change_marks_gap_passed(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    _wj(root / "m27v_arg_realization.json", {"cases": [{"case_id": "arg", "arg_realization_proxy_ready": True}]})
    _wjl(root / "subset_case_report.jsonl", [{"case_id": "arg", "policy_plan_activated": True, "recommended_tool_match": True, "raw_normalized_arg_match": False, "candidate_success": False}])

    report = evaluate(root, fixed_by_code_change=True)

    assert report["m27x_scorer_proxy_gap_explained"] is True
    assert report["m27x_scorer_proxy_gap_passed"] is True



def test_m27y_feedback_marks_gap_fixed_when_it_covers_gap_and_regression(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    _wj(root / "subset_summary.json", {
        "baseline_accuracy": 13.33,
        "candidate_accuracy": 6.67,
        "net_case_gain": -2,
        "recommended_tool_match_rate_among_activated": 0.63,
        "raw_normalized_arg_match_rate_among_activated": 0.45,
    })
    _wj(root / "m27tw_offline_summary.json", {
        "tool_ranking": {"offline_recommended_tool_match_proxy": 1.0},
        "arg_realization": {"raw_arg_match_rate_proxy": 1.0},
    })
    _wj(root / "m27v_arg_realization.json", {"cases": [
        {"case_id": "tool", "selected_tool": "cat", "candidate_arg_json": {"file_name": "a.txt"}, "arg_realization_proxy_ready": True},
        {"case_id": "reg", "selected_tool": "touch", "candidate_arg_json": {"file_name": "b.txt"}, "arg_realization_proxy_ready": True},
    ]})
    _wjl(root / "subset_case_report.jsonl", [
        {"case_id": "tool", "policy_plan_activated": True, "selected_next_tool": "cat", "recommended_tool_match": False, "raw_normalized_arg_match": True, "baseline_success": False, "candidate_success": False, "case_fixed": False, "case_regressed": False},
        {"case_id": "reg", "policy_plan_activated": True, "selected_next_tool": "touch", "recommended_tool_match": True, "raw_normalized_arg_match": True, "baseline_success": True, "candidate_success": False, "case_fixed": False, "case_regressed": True},
    ])

    first = evaluate(root)
    _wj(root / "m27x_scorer_proxy_gap.json", first)
    feedback = build_feedback(root)
    _wj(root / "m27y_scorer_feedback.json", feedback)
    report = evaluate(root)

    assert feedback["m27y_scorer_feedback_ready"] is True
    assert feedback["feedback_reason_distribution"]["scorer_tool_mismatch_after_guidance"] == 1
    assert feedback["feedback_reason_distribution"]["scorer_regression"] == 1
    assert feedback["blocked_candidate_signatures"] == [{"tool": "touch", "args": {"file_name": "b.txt"}}]
    by_feedback_case = {case["case_id"]: case for case in feedback["feedback_cases"]}
    assert by_feedback_case["tool"]["feedback_action"] == "diagnostic_only"
    assert by_feedback_case["reg"]["feedback_action"] == "record_only"
    assert report["fixed_by_code_change"] is True
    assert report["m27x_scorer_proxy_gap_passed"] is True
    assert report["scorer_feedback_covers_gap_cases"] is True
    assert report["scorer_feedback_covers_regression_cases"] is True
    by_case = {case["case_id"]: case for case in report["cases"]}
    assert by_case["tool"]["scorer_feedback_applied"] is True
    assert by_case["tool"]["feedback_action"] == "diagnostic_only"
    assert by_case["reg"]["feedback_action"] == "record_only"


def test_m27y_feedback_is_not_ready_if_regression_not_covered(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    _wj(root / "m27y_scorer_feedback.json", {
        "m27y_scorer_feedback_ready": True,
        "fixed_by_code_change": True,
        "blocked_case_ids": ["tool"],
    })
    _wjl(root / "subset_case_report.jsonl", [
        {"case_id": "tool", "policy_plan_activated": True, "recommended_tool_match": False, "raw_normalized_arg_match": True, "candidate_success": False},
        {"case_id": "reg", "policy_plan_activated": True, "recommended_tool_match": True, "raw_normalized_arg_match": True, "baseline_success": True, "candidate_success": False, "case_regressed": True},
    ])

    report = evaluate(root)

    assert report["fixed_by_code_change"] is False
    assert report["m27x_scorer_proxy_gap_passed"] is False
    assert report["scorer_feedback_covers_regression_cases"] is False
