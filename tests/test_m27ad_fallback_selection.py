from __future__ import annotations

import json
from pathlib import Path

from scripts.diagnose_m27ad_fallback_selection import evaluate
from scripts.check_m27tw_offline import evaluate as evaluate_tw


def _wj(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def _base_tw(root: Path, hold: Path, source: Path) -> None:
    _wj(source / "source_collection_manifest.json", {"m27t_source_pool_ready": True})
    _wj(hold / "holdout_manifest.json", {"m27tw_holdout_manifest_ready": True, "selected_case_count": 30, "candidate_generatable_count": 30, "overlap_with_dev_case_ids": []})
    _wj(root / "m27u_tool_ranking.json", {"m27u_tool_ranking_passed": True})
    _wj(root / "m27v_arg_realization.json", {"m27v_arg_realization_passed": True})
    _wj(root / "m27w_rule_retention.json", {"m27w_rule_retention_passed": True})
    _wj(root / "subset_summary.json", {"recommended_tool_match_rate_among_activated": 0.56, "raw_normalized_arg_match_rate_among_activated": 0.33})
    _wj(root / "m27x_scorer_proxy_gap.json", {"m27x_scorer_proxy_gap_explained": True, "fixed_by_code_change": True})
    _wj(root / "m27aa_regression_patterns.json", {"m27aa_regression_patterns_passed": False, "old_regression_unresolved_count": 1, "new_regression_pattern_count": 0, "regression_pattern_coverage": 1.0, "pattern_effective_coverage": 0.6667, "diagnostic_unsafe_gap_count": 0, "scorer_feedback_covers_regression_patterns": True, "scorer_feedback_effective_for_regression_patterns": False})
    _wj(root / "m27m_guidance_only_readiness.json", {"m2_7m_preflight_passed": True, "m2_7m_guidance_only_readiness_passed": True, "plan_activated_count_after_guard": 10, "dominant_selected_next_tool_rate_after_guard": 0.8, "exact_tool_choice_coverage": 0.0})
    _wj(root / "m27i_guard_preflight.json", {"m2_7i_guard_preflight_passed": True, "guard_keeps_fixed_cases": 1})


def test_fallback_chain_recall_tradeoff_passes_ad_when_block_all_breaks_readiness(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    _wj(root / "m27ab_unresolved_regression_repair.json", {"old_regression_unresolved_case_ids_after_repair": ["multi_turn_miss_param_39"], "pattern_ineffective_case_ids": ["multi_turn_miss_param_39"]})
    _wj(root / "m27ac_pattern_guard_recall.json", {"fixed_case_blocked_count": 0, "productive_nonregression_case_blocked_count": 0})
    _wj(root / "m27x_scorer_proxy_gap.json", {"cases": [{"case_id": "multi_turn_miss_param_39", "gap_type": "proxy_arg_ok_scorer_arg_wrong", "baseline_success": True, "repair_kinds": ["coerce_no_tool_text_to_empty"]}]})
    _wj(root / "m27m_guidance_only_readiness.json", {"m2_7m_preflight_passed": True, "m2_7m_guidance_only_readiness_passed": True, "plan_activated_count_after_guard": 10, "dominant_selected_next_tool_rate_after_guard": 0.8})
    _wj(root / "m27i_guard_preflight.json", {"cases": [{"case_id": "multi_turn_miss_param_39", "before_guard_plan": {"selected_action_candidate": {"tool": "touch", "args": {"file_name": "marker.txt"}}}, "after_guard_plan": {"activated": True, "selected_action_candidate": {"tool": "cat", "args": {"file_name": "test_results.json"}, "binding_source": "prior_tool_output.matches[0]|basename", "trajectory_risk_flags": ["trajectory_sensitive_tool"], "scorer_feedback_pattern_matched": True}, "rejected_action_candidates": [{"tool": "cat", "args": {"file_name": "analysis_report.txt"}, "scorer_feedback_fallback_guard_matched": True, "scorer_feedback_fallback_action": "record_only", "guard": {"reason": "intervention_mode_record_only", "intervention_mode": "record_only"}}]}}]})

    report = evaluate(root)

    assert report["m27ad_fallback_selection_passed"] is True
    assert report["fallback_chain_recall_tradeoff_count"] == 1
    case = report["cases"][0]
    assert case["fallback_selection_class"] == "fallback_chain_recall_tradeoff"
    assert case["block_all_would_break_m27m_readiness"] is True


def test_unsafe_fallback_without_recall_tradeoff_keeps_ad_blocked(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    _wj(root / "m27ab_unresolved_regression_repair.json", {"old_regression_unresolved_case_ids_after_repair": ["case_1"]})
    _wj(root / "m27ac_pattern_guard_recall.json", {"fixed_case_blocked_count": 0})
    _wj(root / "m27x_scorer_proxy_gap.json", {"cases": [{"case_id": "case_1", "gap_type": "proxy_arg_ok_scorer_arg_wrong", "baseline_success": True}]})
    _wj(root / "m27m_guidance_only_readiness.json", {"m2_7m_preflight_passed": True, "m2_7m_guidance_only_readiness_passed": True, "plan_activated_count_after_guard": 12, "dominant_selected_next_tool_rate_after_guard": 0.5})
    _wj(root / "m27i_guard_preflight.json", {"cases": [{"case_id": "case_1", "after_guard_plan": {"activated": True, "selected_action_candidate": {"tool": "cat", "args": {"file_name": "x.txt"}, "binding_source": "prior_tool_output.matches[0]|basename", "trajectory_risk_flags": ["trajectory_sensitive_tool"], "scorer_feedback_pattern_matched": True}, "rejected_action_candidates": []}}]})

    report = evaluate(root)

    assert report["m27ad_fallback_selection_passed"] is False
    assert report["unsafe_fallback_unblocked_count"] == 1
    assert report["cases"][0]["fallback_selection_class"] == "unsafe_fallback"


def test_tw_offline_can_use_ad_residual_tradeoff_when_strict_aa_fails(tmp_path: Path) -> None:
    root = tmp_path / "subset"; hold = tmp_path / "hold"; source = tmp_path / "source"
    _base_tw(root, hold, source)
    _wj(root / "m27ad_fallback_selection.json", {"m27ad_fallback_selection_passed": True, "old_regression_unresolved_count_after_repair": 1, "fallback_chain_recall_tradeoff_count": 1, "repair_policy_or_no_tool_coercion_count": 0, "unsafe_fallback_unblocked_count": 0, "m2_7m_guidance_only_readiness_passed": True})

    out = evaluate_tw(root, hold, source)

    assert out["pattern_proxy_calibration_passed"] is True
    assert out["m2_7tw_offline_passed"] is True
    assert out["pattern_proxy_calibration"]["m27ad_fallback_selection_passed"] is True


def test_tw_offline_stays_blocked_when_ad_reports_unsafe_fallback(tmp_path: Path) -> None:
    root = tmp_path / "subset"; hold = tmp_path / "hold"; source = tmp_path / "source"
    _base_tw(root, hold, source)
    _wj(root / "m27ad_fallback_selection.json", {"m27ad_fallback_selection_passed": False, "old_regression_unresolved_count_after_repair": 1, "fallback_chain_recall_tradeoff_count": 0, "repair_policy_or_no_tool_coercion_count": 0, "unsafe_fallback_unblocked_count": 1, "m2_7m_guidance_only_readiness_passed": True})

    out = evaluate_tw(root, hold, source)

    assert out["pattern_proxy_calibration_passed"] is False
    assert out["m2_7tw_offline_passed"] is False


def test_ad_fails_when_recall_readiness_is_broken(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    _wj(root / "m27ab_unresolved_regression_repair.json", {"old_regression_unresolved_case_ids_after_repair": ["multi_turn_miss_param_39"]})
    _wj(root / "m27ac_pattern_guard_recall.json", {"fixed_case_blocked_count": 0})
    _wj(root / "m27x_scorer_proxy_gap.json", {"cases": [{"case_id": "multi_turn_miss_param_39", "gap_type": "proxy_arg_ok_scorer_arg_wrong", "baseline_success": True}]})
    _wj(root / "m27m_guidance_only_readiness.json", {"m2_7m_preflight_passed": False, "m2_7m_guidance_only_readiness_passed": False, "plan_activated_count_after_guard": 7, "dominant_selected_next_tool_rate_after_guard": 0.7})
    _wj(root / "m27i_guard_preflight.json", {"cases": [{"case_id": "multi_turn_miss_param_39", "after_guard_plan": {"activated": True, "selected_action_candidate": {"tool": "cat", "args": {"file_name": "test_results.json"}, "binding_source": "prior_tool_output.matches[0]|basename", "trajectory_risk_flags": ["trajectory_sensitive_tool"], "scorer_feedback_pattern_matched": True}, "rejected_action_candidates": []}}]})

    report = evaluate(root)

    assert report["m27ad_fallback_selection_passed"] is False
    assert report["m2_7m_guidance_only_readiness_passed"] is False
