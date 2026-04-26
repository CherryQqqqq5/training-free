from __future__ import annotations

import json
from pathlib import Path

from scripts.diagnose_m27aa_regression_patterns import evaluate
from scripts.check_m27tw_offline import evaluate as evaluate_tw


def _wj(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n")


def _wjl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_regression_pattern_report_tracks_old_new_and_unsafe_gap(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    _wj(root / "subset_summary.json", {"case_report_trace_mapping": "prompt_user_prefix", "case_level_gate_allowed": True, "net_case_gain": -2})
    _wjl(root / "subset_case_report.jsonl", [
        {"case_id": "old", "baseline_success": True, "candidate_success": False, "case_regressed": True, "policy_plan_activated": True, "selected_next_tool": "cat", "repair_kinds": ["resolve_contextual_string_arg"]},
        {"case_id": "new", "baseline_success": True, "candidate_success": False, "case_regressed": True, "policy_plan_activated": False, "selected_next_tool": None, "repair_kinds": ["coerce_no_tool_text_to_empty"]},
        {"case_id": "safe", "baseline_success": False, "candidate_success": False, "case_regressed": False, "policy_plan_activated": True, "selected_next_tool": "cp", "repair_kinds": []},
        {"case_id": "unsafe", "baseline_success": True, "candidate_success": False, "case_regressed": False, "policy_plan_activated": True, "selected_next_tool": "cat", "repair_kinds": ["resolve_contextual_string_arg"]},
    ])
    _wj(root / "m27x_scorer_proxy_gap.json", {"cases": [
        {"case_id": "old", "case_regressed": True, "baseline_success": True, "candidate_success": False, "offline_selected_tool": "cat", "offline_candidate_args": {"file_name": "a.txt"}, "gap_type": "proxy_arg_ok_scorer_arg_wrong", "repair_kinds": ["resolve_contextual_string_arg"]},
        {"case_id": "new", "case_regressed": True, "baseline_success": True, "candidate_success": False, "offline_selected_tool": None, "offline_candidate_args": {}, "gap_type": "no_proxy_gap", "repair_kinds": ["coerce_no_tool_text_to_empty"]},
        {"case_id": "safe", "case_regressed": False, "baseline_success": False, "candidate_success": False, "offline_selected_tool": "cp", "offline_candidate_args": {"source": "a.txt", "destination": "b.txt"}, "gap_type": "proxy_ok_trajectory_failed", "repair_kinds": []},
        {"case_id": "unsafe", "case_regressed": False, "baseline_success": True, "candidate_success": False, "offline_selected_tool": "cat", "offline_candidate_args": {"file_name": "a.txt"}, "gap_type": "proxy_arg_ok_scorer_arg_wrong", "repair_kinds": ["resolve_contextual_string_arg"]},
    ]})
    _wj(root / "m27y_scorer_feedback.json", {"regression_case_ids": ["old"], "feedback_cases": [], "m27y_scorer_feedback_ready": True})
    _wj(root / "m27z_feedback_effect.json", {"previous_regression_cases_still_regressed": ["old"], "new_regression_cases": [{"case_id": "new"}]})
    _wj(root / "m27v_arg_realization.json", {"cases": [
        {"case_id": "old", "selected_tool": "cat", "candidate_arg_json": {"file_name": "a.txt"}, "canonical_arg_validation": {"file_name": {"source": "prior_tool_output.matches[0]|basename"}}},
        {"case_id": "unsafe", "selected_tool": "cat", "candidate_arg_json": {"file_name": "a.txt"}, "canonical_arg_validation": {"file_name": {"source": "prior_tool_output.matches[0]|basename"}}},
    ]})
    report = evaluate(root, tmp_path / "missing_rules")
    assert report["old_regression_unresolved_count"] == 1
    assert report["new_regression_pattern_count"] == 1
    assert "unsafe" in report["diagnostic_unsafe_gap_case_ids"]
    assert report["regression_pattern_coverage"] == 1.0
    assert report["m27aa_regression_patterns_passed"] is False


def test_tw_offline_requires_pattern_calibration_when_scorer_floor_low(tmp_path: Path) -> None:
    root = tmp_path / "subset"; hold = tmp_path / "hold"; source = tmp_path / "source"
    _wj(source / "source_collection_manifest.json", {"m27t_source_pool_ready": True})
    _wj(hold / "holdout_manifest.json", {"m27tw_holdout_manifest_ready": True, "selected_case_count": 30, "candidate_generatable_count": 30, "overlap_with_dev_case_ids": []})
    _wj(root / "m27u_tool_ranking.json", {"m27u_tool_ranking_passed": True})
    _wj(root / "m27v_arg_realization.json", {"m27v_arg_realization_passed": True})
    _wj(root / "m27w_rule_retention.json", {"m27w_rule_retention_passed": True})
    _wj(root / "subset_summary.json", {"recommended_tool_match_rate_among_activated": 0.7, "raw_normalized_arg_match_rate_among_activated": 0.4})
    _wj(root / "m27x_scorer_proxy_gap.json", {"m27x_scorer_proxy_gap_explained": True, "fixed_by_code_change": True})
    out = evaluate_tw(root, hold, source)
    assert out["proxy_calibration_passed"] is True
    assert out["pattern_proxy_calibration_passed"] is False
    assert out["m2_7tw_offline_passed"] is False


def test_tw_offline_can_pass_after_pattern_calibration(tmp_path: Path) -> None:
    root = tmp_path / "subset"; hold = tmp_path / "hold"; source = tmp_path / "source"
    _wj(source / "source_collection_manifest.json", {"m27t_source_pool_ready": True})
    _wj(hold / "holdout_manifest.json", {"m27tw_holdout_manifest_ready": True, "selected_case_count": 30, "candidate_generatable_count": 30, "overlap_with_dev_case_ids": []})
    _wj(root / "m27u_tool_ranking.json", {"m27u_tool_ranking_passed": True})
    _wj(root / "m27v_arg_realization.json", {"m27v_arg_realization_passed": True})
    _wj(root / "m27w_rule_retention.json", {"m27w_rule_retention_passed": True})
    _wj(root / "subset_summary.json", {"recommended_tool_match_rate_among_activated": 0.7, "raw_normalized_arg_match_rate_among_activated": 0.4})
    _wj(root / "m27x_scorer_proxy_gap.json", {"m27x_scorer_proxy_gap_explained": True, "fixed_by_code_change": True})
    _wj(root / "m27aa_regression_patterns.json", {"m27aa_regression_patterns_passed": True, "old_regression_unresolved_count": 0, "new_regression_pattern_count": 0, "regression_pattern_coverage": 1.0, "pattern_effective_coverage": 1.0, "diagnostic_unsafe_gap_count": 0, "scorer_feedback_covers_regression_patterns": True, "scorer_feedback_effective_for_regression_patterns": True})
    _wj(root / "m27m_guidance_only_readiness.json", {"m2_7m_preflight_passed": True, "m2_7m_guidance_only_readiness_passed": True, "plan_activated_count_after_guard": 10, "dominant_selected_next_tool_rate_after_guard": 0.5, "exact_tool_choice_coverage": 0.0})
    _wj(root / "m27i_guard_preflight.json", {"m2_7i_guard_preflight_passed": True, "guard_keeps_fixed_cases": 1})
    out = evaluate_tw(root, hold, source)
    assert out["pattern_proxy_calibration_passed"] is True
    assert out["m2_7tw_offline_passed"] is True
