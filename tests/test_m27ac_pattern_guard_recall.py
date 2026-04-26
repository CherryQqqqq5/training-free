from __future__ import annotations

import json
from pathlib import Path

from scripts.diagnose_m27ac_pattern_guard_recall import evaluate
from scripts.build_m27y_scorer_feedback import build_feedback


def _wj(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def _wjl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_fixed_case_collateral_recommends_diagnostic_only(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    key = '{"selected_tool_family":"create_file"}'
    _wj(root / "m27aa_regression_patterns.json", {"blocked_regression_patterns": [{"regression_guard_key": key, "action": "record_only"}], "raw_old_regression_unresolved_case_ids": ["reg"]})
    _wjl(root / "subset_case_report.jsonl", [{"case_id": "fixed", "candidate_success": True, "case_regressed": False}])
    _wj(root / "m27m_guidance_only_readiness.json", {"plan_activated_count_after_guard": 2, "dominant_selected_next_tool_rate_after_guard": 0.5})
    _wj(root / "m27i_guard_preflight.json", {
        "fixed_cases_guard_status": {"fixed": "guard_rejected"},
        "cases": [
            {"case_id": "reg", "guard_status": "guard_rejected", "after_guard_plan": {"activated": False, "rejected_action_candidates": [{"tool": "touch", "matched_regression_guard_key": key, "scorer_feedback_pattern_matched": True, "scorer_feedback_pattern_action": "record_only", "guard": {"intervention_mode": "record_only"}}]}},
            {"case_id": "fixed", "guard_status": "guard_rejected", "after_guard_plan": {"activated": False, "rejected_action_candidates": [{"tool": "touch", "matched_regression_guard_key": key, "scorer_feedback_pattern_matched": True, "scorer_feedback_pattern_action": "record_only", "guard": {"intervention_mode": "record_only"}}]}},
        ],
    })

    report = evaluate(root)

    assert report["m27ac_pattern_guard_recall_passed"] is False
    assert report["fixed_cases_blocked"] == ["fixed"]
    assert report["pattern_action_overrides"][key] == "diagnostic_only"


def test_regression_only_pattern_can_remain_record_only(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    key = '{"selected_tool_family":"read_content"}'
    _wj(root / "m27aa_regression_patterns.json", {"blocked_regression_patterns": [{"regression_guard_key": key, "action": "record_only"}], "raw_old_regression_unresolved_case_ids": ["reg"]})
    _wj(root / "m27m_guidance_only_readiness.json", {"plan_activated_count_after_guard": 10, "dominant_selected_next_tool_rate_after_guard": 0.5})
    _wj(root / "m27i_guard_preflight.json", {"fixed_cases_guard_status": {}, "cases": [{"case_id": "reg", "guard_status": "guard_rejected", "after_guard_plan": {"activated": False, "rejected_action_candidates": [{"tool": "cat", "matched_regression_guard_key": key, "scorer_feedback_pattern_matched": True, "scorer_feedback_pattern_action": "record_only", "guard": {"intervention_mode": "record_only"}}]}}]})

    report = evaluate(root)

    assert report["m27ac_pattern_guard_recall_passed"] is True
    assert report["pattern_action_overrides"][key] == "record_only"


def test_feedback_builder_applies_m27ac_action_override(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    key = '{"selected_tool_family":"read_content"}'
    _wj(root / "m27aa_regression_patterns.json", {"blocked_regression_patterns": [{"regression_guard_key": key, "action": "record_only"}]})
    _wj(root / "m27ac_pattern_guard_recall.json", {"pattern_action_overrides": {key: "diagnostic_only"}})
    _wj(root / "m27x_scorer_proxy_gap.json", {"cases": [{"case_id": "reg", "gap_type": "proxy_arg_ok_scorer_arg_wrong", "case_regressed": True, "offline_selected_tool": "cat", "offline_candidate_args": {"file_name": "a.txt"}}]})

    feedback = build_feedback(root)

    assert feedback["blocked_regression_patterns"][0]["action"] == "diagnostic_only"
    assert feedback["blocked_regression_patterns"][0]["action_source"] == "m27ac_pattern_guard_recall"
