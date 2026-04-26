from __future__ import annotations

import json
from pathlib import Path

from scripts.diagnose_m27ab_unresolved_regression_repair import evaluate
from scripts.check_m27tw_offline import evaluate as evaluate_tw


def _wj(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def test_covered_but_not_effective_pattern_does_not_pass(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    key = '{"selected_tool_family":"read_content"}'
    _wj(root / "m27aa_regression_patterns.json", {
        "old_regression_unresolved_case_ids": ["multi_turn_miss_param_35"],
        "cases": [{"case_id": "multi_turn_miss_param_35", "regression_guard_key": key, "selected_tool": "cat", "binding_source": "prior_tool_output.matches[0]|basename", "repair_kinds": ["resolve_contextual_string_arg"]}],
    })
    _wj(root / "m27i_guard_preflight.json", {"cases": [{"case_id": "multi_turn_miss_param_35", "after_guard_plan": {"activated": True, "selected_action_candidate": {"tool": "cat", "args": {"file_name": "config.py"}}, "rejected_action_candidates": []}}]})

    report = evaluate(root)

    assert report["m27ab_unresolved_regression_repair_passed"] is False
    assert report["pattern_effective_coverage"] == 0.0
    assert report["pattern_ineffective_case_ids"] == ["multi_turn_miss_param_35"]


def test_pattern_record_only_rejection_is_effective(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    key = '{"selected_tool_family":"create_file"}'
    _wj(root / "m27aa_regression_patterns.json", {
        "old_regression_unresolved_case_ids": ["multi_turn_miss_param_39"],
        "cases": [{"case_id": "multi_turn_miss_param_39", "regression_guard_key": key, "selected_tool": "touch", "binding_source": "prior_tool_output.cwd_or_listing", "repair_kinds": ["coerce_no_tool_text_to_empty"]}],
    })
    _wj(root / "m27i_guard_preflight.json", {"cases": [{"case_id": "multi_turn_miss_param_39", "after_guard_plan": {"activated": False, "selected_action_candidate": None, "rejected_action_candidates": [{"tool": "touch", "args": {"file_name": "marker.txt"}, "matched_regression_guard_key": key, "scorer_feedback_pattern_matched": True, "scorer_feedback_pattern_action": "record_only", "scorer_feedback_action": "record_only", "guard": {"reason": "intervention_mode_record_only", "intervention_mode": "record_only", "risk_flags": ["scorer_feedback_record_only"]}}]}}]})

    report = evaluate(root)

    assert report["m27ab_unresolved_regression_repair_passed"] is True
    assert report["pattern_effective_coverage"] == 1.0
    assert report["old_regression_unresolved_count_after_repair"] == 0
    assert report["cases"][0]["guard_outcome"] == "pattern_record_only_rejection"


def test_no_proxy_regression_enters_audit_and_can_be_effectively_absent(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    key = '{"selected_tool_family":"unknown"}'
    _wj(root / "m27aa_regression_patterns.json", {
        "old_regression_unresolved_case_ids": ["multi_turn_miss_param_9"],
        "cases": [{"case_id": "multi_turn_miss_param_9", "regression_guard_key": key, "selected_tool": None, "binding_source": "unknown", "repair_kinds": ["coerce_no_tool_text_to_empty"]}],
    })
    _wj(root / "m27i_guard_preflight.json", {"cases": [{"case_id": "multi_turn_miss_param_9", "after_guard_plan": {"activated": False, "selected_action_candidate": None, "rejected_action_candidates": []}}]})

    report = evaluate(root)

    assert report["m27ab_unresolved_regression_repair_passed"] is True
    assert report["cases"][0]["guard_outcome"] == "no_proxy_candidate_absent_or_guard_rejected"


def test_pattern_effective_coverage_required_for_tw_offline(tmp_path: Path) -> None:
    root = tmp_path / "subset"; hold = tmp_path / "hold"; source = tmp_path / "source"
    _wj(source / "source_collection_manifest.json", {"m27t_source_pool_ready": True})
    _wj(hold / "holdout_manifest.json", {"m27tw_holdout_manifest_ready": True, "selected_case_count": 30, "candidate_generatable_count": 30, "overlap_with_dev_case_ids": []})
    _wj(root / "m27u_tool_ranking.json", {"m27u_tool_ranking_passed": True})
    _wj(root / "m27v_arg_realization.json", {"m27v_arg_realization_passed": True})
    _wj(root / "m27w_rule_retention.json", {"m27w_rule_retention_passed": True})
    _wj(root / "subset_summary.json", {"recommended_tool_match_rate_among_activated": 0.7, "raw_normalized_arg_match_rate_among_activated": 0.4})
    _wj(root / "m27x_scorer_proxy_gap.json", {"m27x_scorer_proxy_gap_explained": True, "fixed_by_code_change": True})
    _wj(root / "m27aa_regression_patterns.json", {"m27aa_regression_patterns_passed": True, "old_regression_unresolved_count": 0, "new_regression_pattern_count": 0, "regression_pattern_coverage": 1.0, "pattern_effective_coverage": 0.5, "diagnostic_unsafe_gap_count": 0, "scorer_feedback_covers_regression_patterns": True, "scorer_feedback_effective_for_regression_patterns": False})

    out = evaluate_tw(root, hold, source)

    assert out["pattern_proxy_calibration_passed"] is False
    assert out["m2_7tw_offline_passed"] is False
