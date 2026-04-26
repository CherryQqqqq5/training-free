from __future__ import annotations

import json
from pathlib import Path

from scripts.build_m27r_holdout_manifest import select_holdout
from scripts.diagnose_m27r_arg_realization import classify_arg_case
from scripts.diagnose_m27r_not_activated import classify_not_activated
from scripts.diagnose_m27r_rule_retention import decide_rule, evaluate_rule_retention
from scripts.write_m27r_dev_subset_protocol import build_protocol
from scripts.check_m27r_offline import evaluate_m27r_offline


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_rule_retention_rejects_nonpositive_or_low_alignment_rules(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    _write_json(root / "subset_summary.json", {"selected_case_count": 3, "case_report_trace_mapping": "prompt_user_prefix", "case_level_gate_allowed": True})
    _write_jsonl(root / "subset_case_report.jsonl", [{"case_id": "a"}, {"case_id": "b"}, {"case_id": "c"}])
    _write_json(root / "m27f_rule_level_report.json", {
        "rules": [
            {"rule_id": "no_gain", "activation_count": 2, "fixed_count": 0, "regressed_count": 0, "net_case_gain": 0, "tool_match_rate": 1.0, "arg_match_rate": 1.0, "trajectory_fail_count": 0},
            {"rule_id": "low_arg", "activation_count": 2, "fixed_count": 1, "regressed_count": 0, "net_case_gain": 1, "tool_match_rate": 1.0, "arg_match_rate": 0.2, "trajectory_fail_count": 0},
        ]
    })
    report = evaluate_rule_retention(root)
    assert report["m27r_rule_retention_ready"] is True
    assert report["decision_distribution"] == {"retain": 0, "demote": 0, "reject": 2}
    assert [rule["reason"] for rule in report["rules"]] == ["no_positive_net_case_gain", "arg_match_rate_below_retention_floor"]
    assert decide_rule({"activation_count": 1, "fixed_count": 1, "regressed_count": 0, "net_case_gain": 1, "tool_match_rate": 1.0, "arg_match_rate": 1.0, "trajectory_fail_count": 0})[0] == "retain"


def test_not_activated_classification_and_guard_reason() -> None:
    false_negative = classify_not_activated(
        {"case_id": "a", "baseline_success": False, "candidate_success": False, "blocked_reason": "activation_predicates_unmet"},
        {
            "target_failure_trace": True,
            "before_guard_plan": {"activated": True, "selected_action_candidate": {"tool": "cat"}, "recommended_tools": ["cat"]},
            "after_guard_plan": {"activated": False},
            "case_final_guard_reason": "weak_arg_binding_evidence",
            "guard_status": "guard_rejected",
        },
    )
    assert false_negative["classification"] == "not_activated_false_negative"
    assert false_negative["candidate_existed_before_guard"] is True
    assert false_negative["guard_rejected_reason"] == "weak_arg_binding_evidence"

    true_negative = classify_not_activated(
        {"case_id": "b", "baseline_success": True, "candidate_success": True},
        {"before_guard_plan": {"activated": False}, "after_guard_plan": {"activated": False}},
    )
    assert true_negative["classification"] == "not_activated_true_negative"


def test_arg_realization_separates_candidate_and_emitted_failures() -> None:
    candidate_wrong = classify_arg_case(
        {"case_id": "a", "selected_next_tool": "cat", "recommended_tool_match": True, "raw_normalized_arg_match": False, "final_normalized_arg_match": False},
        {"after_guard_plan": {"selected_action_candidate": {"tool": "cat", "args": {}}}},
    )
    assert candidate_wrong["failure_reason"] == "candidate_arg_wrong"

    emitted_wrong = classify_arg_case(
        {"case_id": "b", "selected_next_tool": "cat", "recommended_tool_match": True, "raw_normalized_arg_match": False, "final_normalized_arg_match": False},
        {"after_guard_plan": {"selected_action_candidate": {"tool": "cat", "args": {"file_name": "x.txt"}, "arg_bindings": {"file_name": {"source": "explicit_literal"}}}}},
    )
    assert emitted_wrong["failure_reason"] == "emitted_arg_wrong_or_guidance_not_followed"
    assert emitted_wrong["schema_arg_names"] == ["file_name"]


def test_holdout_selection_excludes_dev_and_omits_commands() -> None:
    rows = [
        {"case_id": "dev", "baseline_wrong": True, "schema_local": True, "target_action_tools_present": ["cat"]},
        {"case_id": "holdout1", "baseline_wrong": True, "schema_local": True, "target_action_tools_present": ["touch"]},
        {"case_id": "skip", "baseline_wrong": True, "schema_local": False, "target_action_tools_present": ["cat"]},
        {"case_id": "holdout2", "baseline_wrong": True, "schema_local": True, "target_action_tools_present": ["mv"]},
    ]
    selected = select_holdout(rows, excluded_ids={"dev"}, max_cases=30)
    assert [row["case_id"] for row in selected] == ["holdout1", "holdout2"]


def test_dev_protocol_and_offline_summary(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    holdout = tmp_path / "holdout"
    selected = [f"case_{i}" for i in range(30)]
    _write_json(root / "paired_subset_manifest.json", {"selected_case_ids": selected, "category": "multi_turn_miss_param"})
    _write_json(root / "subset_summary.json", {"baseline_accuracy": 1.0, "candidate_accuracy": 1.0, "case_report_trace_mapping": "prompt_user_prefix", "case_level_gate_allowed": True})
    _write_json(root / "m27q_postmortem.json", {"evidence_status": "durable"})
    protocol = build_protocol(root)
    assert protocol["m27r_dev_subset_protocol_ready"] is True
    _write_json(root / "m27r_dev_subset_protocol.json", protocol)
    _write_json(root / "m27r_rule_retention.json", {"m27r_rule_retention_ready": True, "decision_distribution": {"reject": 1}})
    _write_json(root / "m27r_not_activated_audit.json", {"m27r_not_activated_audit_ready": True, "classification_distribution": {"not_activated_unknown": 1}})
    _write_json(root / "m27r_arg_realization.json", {"m27r_arg_realization_audit_ready": True, "failure_reason_distribution": {"emitted_arg_wrong_or_guidance_not_followed": 1}})
    _write_json(holdout / "holdout_manifest.json", {"m27r_holdout_manifest_ready": True, "selected_case_count": 30, "overlap_with_dev_case_ids": []})
    summary = evaluate_m27r_offline(root, holdout)
    assert summary["m2_7r_offline_passed"] is True
