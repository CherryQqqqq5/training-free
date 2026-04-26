from __future__ import annotations

import json
from pathlib import Path

from scripts.diagnose_m27q_postmortem import classify_case, evaluate_postmortem


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_classify_case_failure_layers() -> None:
    assert classify_case({"case_id": "a", "policy_plan_activated": False})["primary_failure_layer"] == "not_activated"
    assert classify_case({"case_id": "b", "policy_plan_activated": True, "recommended_tool_match": False})["primary_failure_layer"] == "tool_match_low"
    assert classify_case({"case_id": "c", "policy_plan_activated": True, "recommended_tool_match": True})["primary_failure_layer"] == "arg_match_low"
    assert classify_case({
        "case_id": "d",
        "policy_plan_activated": True,
        "recommended_tool_match": True,
        "raw_normalized_arg_match": True,
        "candidate_success": False,
    })["primary_failure_layer"] == "trajectory_continuation_or_postcondition"
    regressed = classify_case({
        "case_id": "e",
        "baseline_success": True,
        "candidate_success": False,
        "policy_plan_activated": True,
        "recommended_tool_match": False,
    })
    assert regressed["case_kind"] == "regressed"
    assert regressed["primary_failure_layer"] == "regression"


def test_classify_case_semantic_candidate_wrong() -> None:
    case = classify_case({
        "case_id": "x",
        "policy_plan_activated": True,
        "recommended_tool_match": True,
        "selected_action_candidate": {
            "postcondition": {"kind": "file_content"},
            "pending_goal_family": "create_file",
            "intervention_mode": "guidance",
        },
    })
    assert case["primary_failure_layer"] == "semantic_candidate_wrong"
    assert "pending_goal_postcondition_mismatch" in case["semantic_candidate_issues"]


def test_evaluate_postmortem_aggregates_rule_retention(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    _write_json(root / "paired_subset_manifest.json", {"selected_case_ids": ["a", "b", "c", "d"]})
    _write_json(root / "subset_summary.json", {
        "case_report_trace_mapping": "prompt_user_prefix",
        "case_level_gate_allowed": True,
        "baseline_accuracy": 6.67,
        "candidate_accuracy": 6.67,
        "case_fixed_count": 1,
        "case_regressed_count": 1,
        "net_case_gain": 0,
        "policy_plan_activated_count": 3,
        "recommended_tool_match_rate_among_activated": 0.7,
        "raw_normalized_arg_match_rate_among_activated": 0.3,
        "stop_allowed_false_positive_count": 0,
    })
    _write_json(root / "m27f_rule_level_report.json", {
        "rules": [
            {
                "rule_id": "r1",
                "activation_count": 2,
                "fixed_count": 1,
                "regressed_count": 1,
                "net_case_gain": 0,
                "tool_match_rate": 0.5,
                "arg_match_rate": 0.0,
                "trajectory_fail_count": 1,
                "decision": "reject",
            }
        ]
    })
    _write_jsonl(root / "subset_case_report.jsonl", [
        {"case_id": "a", "policy_plan_activated": False},
        {"case_id": "b", "policy_plan_activated": True, "recommended_tool_match": False},
        {"case_id": "c", "policy_plan_activated": True, "recommended_tool_match": True},
        {
            "case_id": "d",
            "baseline_success": True,
            "candidate_success": False,
            "policy_plan_activated": True,
            "recommended_tool_match": False,
        },
    ])

    report = evaluate_postmortem(root)

    assert report["evidence_status"] == "durable"
    assert report["m2_7q_postmortem_passed"] is True
    assert report["failure_layer_distribution"]["not_activated"] == 1
    assert report["failure_layer_distribution"]["tool_match_low"] == 2
    assert report["failure_layer_distribution"]["arg_match_low"] == 1
    assert report["failure_layer_distribution"]["regression"] == 1
    assert report["rule_retention"]["decision_distribution"] == {"reject": 1}
    assert report["recommended_next_focus"] == "binding_serialization_or_argument_realization"


def test_diagnostic_only_when_trace_mapping_not_durable(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    _write_json(root / "paired_subset_manifest.json", {"selected_case_ids": ["a"]})
    _write_json(root / "subset_summary.json", {
        "case_report_trace_mapping": "mtime_by_result_step_count",
        "case_level_gate_allowed": False,
        "baseline_accuracy": 1.0,
        "candidate_accuracy": 2.0,
        "case_fixed_count": 1,
        "case_regressed_count": 0,
        "net_case_gain": 1,
        "policy_plan_activated_count": 1,
        "recommended_tool_match_rate_among_activated": 1.0,
        "raw_normalized_arg_match_rate_among_activated": 1.0,
        "stop_allowed_false_positive_count": 0,
    })
    _write_json(root / "m27f_rule_level_report.json", {"rules": []})
    _write_jsonl(root / "subset_case_report.jsonl", [{"case_id": "a", "policy_plan_activated": True}])

    report = evaluate_postmortem(root)

    assert report["evidence_status"] == "diagnostic_only"
    assert report["m2_7q_postmortem_passed"] is False
    assert report["recommended_next_focus"] == "trace_attribution_or_completeness"
    assert "case_level_trace_attribution_allowed" in report["failed_gate_criteria"]
