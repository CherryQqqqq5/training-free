from __future__ import annotations

import json
from pathlib import Path

import scripts.audit_delivery_evidence as audit


def _wj(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_policy_conversion_counters_detect_runtime_fields(tmp_path: Path) -> None:
    trace = tmp_path / "run" / "traces" / "trace.json"
    _wj(trace, {
        "events": [
            {"rule_hits": ["r1"], "policy_hits": ["p1"], "recommended_tools": ["search"], "selected_next_tool": "search", "next_tool_emitted": True, "tool_choice_mode": "required"},
            {"rule_hits": [], "policy_hits": [], "recommended_tools": []},
        ]
    })

    counters = audit.policy_conversion_counters(tmp_path)

    assert counters["trace_files_scanned"] == 1
    assert counters["rule_hits"] == 1
    assert counters["policy_hits"] == 1
    assert counters["recommended_tools"] == 1
    assert counters["selected_next_tool"] == 1
    assert counters["next_tool_emitted"] == 1
    assert counters["required_tool_choice_records"] == 1
    assert counters["policy_conversion_observed"] is True
    assert counters["rule_hits_without_policy_hits"] == 0


def test_delivery_audit_reports_scaffold_status_when_gates_fail(tmp_path: Path, monkeypatch) -> None:
    subset = tmp_path / "subset"
    low = tmp_path / "low"
    traces = tmp_path / "phase2"
    _wj(subset / "m27ae_ctspc_v0_status.json", {"status": "diagnostic_experimental", "ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _wj(subset / "repair_stack_contribution.json", {"repair_stack_split_ready": True})
    _wj(subset / "subset_summary.json", {"baseline_accuracy": 20.0, "candidate_accuracy": 10.0, "net_case_gain": -3})
    _wj(low / "compiler_summary.json", {"compiler_ready": True, "explicit_holdout_ready": False, "ctspc_v0_action_rules_enabled": False, "ctspc_v0_file_path_multi_turn_enabled": False, "repair_stack_default": "disabled", "candidate_rules_type": "explicit_required_arg_literal_completion", "no_next_tool_intervention": True, "exact_tool_choice": False, "retention_prior_required": True, "retain_eligible_candidate_count": 17, "required_explicit_candidate_generatable": 35, "planned_commands": [], "candidate_commands": []})
    _wj(low / "retention_prior_coverage_audit.json", {"m28pre_retention_prior_coverage_audit_ready": True, "explicit_prior_family_coverage_zero": False, "current_context_anchored_literal_candidate_count": 17, "candidate_commands": [], "planned_commands": []})
    _wj(low / "raw_bfcl_literal_coverage_audit.json", {"m28pre_raw_bfcl_literal_coverage_audit_ready": True, "source_result_literals_prompt_anchored_count": 17, "source_result_literals_prompt_coverage_zero": False, "candidate_commands": [], "planned_commands": []})
    _wj(low / "m28pre_source_result_availability_audit.json", {"source_result_availability_audit_ready": True, "source_result_availability_ready": True, "hard_issue_counts": {}, "issue_counts": {}, "candidate_commands": [], "planned_commands": []})
    _wj(low / "wrong_arg_key_alias_coverage_audit.json", {"wrong_arg_key_alias_coverage_audit_ready": True, "wrong_arg_key_alias_family_coverage_zero": True, "rejection_reason_counts": {"no_wrong_arg_key_alias_detected": 3}, "candidate_commands": [], "planned_commands": []})
    _wj(low / "deterministic_schema_local_coverage_audit.json", {"deterministic_schema_local_coverage_audit_ready": True, "deterministic_schema_local_family_coverage_zero": True, "rejection_reason_counts": {"no_deterministic_schema_local_repair_detected": 2}, "candidate_commands": [], "planned_commands": []})
    monkeypatch.setattr(audit, "artifact_boundary_status", lambda: {"artifact_boundary_passed": False, "forbidden_artifact_count": 2, "forbidden_artifact_examples": ["outputs/x/.env"]})

    report = audit.evaluate(subset, low, traces)

    assert report["delivery_claim_status"] == "scaffold_and_diagnostic_package_only"
    assert report["sota_3pp_claim_ready"] is False
    assert "artifact_boundary_not_clean" in report["p0_blockers"]
    assert "m2_8pre_offline_not_passed" in report["p0_blockers"]
    assert "scorer_authorization_not_ready" in report["p0_blockers"]
    assert "policy_conversion_not_observed_in_existing_traces" in report["p0_blockers"]
    assert report["ctspc_v0"]["latest_net_case_gain"] == -3


def test_policy_conversion_counters_explain_rule_hits_without_policy(tmp_path: Path) -> None:
    trace = tmp_path / "run" / "traces" / "trace.json"
    _wj(trace, {"events": [{"rule_hits": ["r1", "r2"], "request_patches": ["prompt guidance"]}]})

    counters = audit.policy_conversion_counters(tmp_path)

    assert counters["rule_hits"] == 2
    assert counters["policy_conversion_observed"] is False
    assert counters["rule_hits_without_policy_hits"] == 2
    assert counters["policy_conversion_absent_reason"] == "policy_artifact_or_runtime_candidate_missing"
    assert counters["policy_artifact_or_runtime_candidate_missing"] is True
    assert counters["sample_rule_hit_no_policy_traces"] == [str(trace)]


def test_source_result_layout_status_distinguishes_scope_mismatch_from_parser_bug(tmp_path: Path) -> None:
    low = tmp_path / "low"
    _wj(low / "m28pre_source_result_availability_audit.json", {
        "source_result_availability_ready": True,
        "hard_issue_counts": {},
        "issue_counts": {"source_result_case_not_collected": 7},
    })
    _wj(low / "wrong_arg_key_alias_coverage_audit.json", {
        "wrong_arg_key_alias_family_coverage_zero": True,
        "rejection_reason_counts": {"missing_source_result": 5},
    })
    _wj(low / "deterministic_schema_local_coverage_audit.json", {
        "deterministic_schema_local_family_coverage_zero": True,
        "rejection_reason_counts": {"missing_source_result": 6},
    })

    status = audit.source_result_layout_status(low)

    assert status["source_result_root_cause"] == "source_collection_subset_vs_full_dataset_audit_scope_mismatch"
    assert status["route_recommendation"] == "align_audit_scope_with_source_collection_subset"
    assert status["source_scope_mismatch_count"] == 7
    assert status["audit_missing_source_result_count"] == 6
