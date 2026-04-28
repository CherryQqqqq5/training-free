#!/usr/bin/env python3
"""Build a compact first-stage delivery evidence audit.

This script is offline-only. It reads committed compact artifacts and optional
server-local trace files, then summarizes whether the repository is ready for a
Huawei first-stage delivery claim. It does not call BFCL, models, or scorers.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import scripts.check_artifact_boundary as artifact_boundary
from scripts.check_m28pre_offline import evaluate as evaluate_m28pre

DEFAULT_SUBSET = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_LOW_RISK = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1")
DEFAULT_PHASE2_VALIDATION = Path("outputs/phase2_validation/required_next_tool_choice_v1")
DEFAULT_POLICY_OPPORTUNITY = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/policy_conversion_opportunity_audit.json")
DEFAULT_POLICY_MANIFEST = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/postcondition_guided_policy_candidate_manifest.json")
DEFAULT_POLICY_NEGATIVE_CONTROLS = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/postcondition_guided_negative_control_audit.json")
DEFAULT_MEMORY_OBLIGATION = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_obligation_audit.json")
DEFAULT_MEMORY_DRY_RUN = Path("outputs/artifacts/phase2/memory_operation_obligation_dry_run_v1/first_pass/compile_status.json")
DEFAULT_MEMORY_RESOLVER = Path("outputs/artifacts/phase2/memory_operation_obligation_dry_run_v1/first_pass/memory_tool_family_resolver_audit.json")
DEFAULT_MEMORY_ACTIVATION = Path("outputs/artifacts/phase2/memory_operation_obligation_dry_run_v1/first_pass/memory_operation_activation_simulation.json")
DEFAULT_MEMORY_RUNTIME_SMOKE = Path("outputs/artifacts/phase2/memory_operation_obligation_runtime_smoke_v1/first_pass/memory_operation_runtime_smoke_readiness.json")
DEFAULT_POSTCONDITION_SMOKE_RESULT = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk/postcondition_guided_dev_smoke_result.json")
DEFAULT_POSTCONDITION_SMOKE_FAILURE = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk/postcondition_guided_dev_smoke_failure_diagnosis.json")
DEFAULT_POSTCONDITION_SATISFACTION = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk/postcondition_satisfaction_audit.json")
DEFAULT_POSTCONDITION_PROTOCOL = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk/postcondition_guided_dev_smoke_protocol.json")
DEFAULT_UNMET_POSTCONDITION_AUDIT = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/unmet_postcondition_source_expansion_audit.json")
DEFAULT_OUT = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1/delivery_evidence_audit.json")
DEFAULT_MD = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1/delivery_evidence_audit.md")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _iter_json_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return root.rglob("*.json")


def _walk_values(obj: Any) -> Iterable[Any]:
    yield obj
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _walk_values(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk_values(value)


def _truthy_count(value: Any) -> int:
    if value is None or value is False or value == "":
        return 0
    if isinstance(value, list):
        return len([item for item in value if item])
    if isinstance(value, (int, float)):
        return int(value)
    return 1


def policy_conversion_counters(trace_root: Path = DEFAULT_PHASE2_VALIDATION, *, max_files: int = 5000) -> dict[str, Any]:
    counters = {
        "trace_root": str(trace_root),
        "trace_files_scanned": 0,
        "rule_hits": 0,
        "policy_hits": 0,
        "recommended_tools": 0,
        "selected_next_tool": 0,
        "next_tool_emitted": 0,
        "required_tool_choice_records": 0,
        "sample_rule_hit_no_policy_traces": [],
    }
    for path in _iter_json_files(trace_root):
        if counters["trace_files_scanned"] >= max_files:
            counters["truncated_at_max_files"] = max_files
            break
        counters["trace_files_scanned"] += 1
        data = _load_json(path)
        if data is None:
            continue
        file_rule_hits = 0
        file_policy_signal = 0
        for node in _walk_values(data):
            if not isinstance(node, dict):
                continue
            node_rule_hits = _truthy_count(node.get("rule_hits"))
            node_policy_signal = (
                _truthy_count(node.get("policy_hits"))
                + _truthy_count(node.get("recommended_tools"))
                + _truthy_count(node.get("selected_next_tool"))
                + _truthy_count(node.get("next_tool_emitted"))
            )
            counters["rule_hits"] += node_rule_hits
            counters["policy_hits"] += _truthy_count(node.get("policy_hits"))
            counters["recommended_tools"] += _truthy_count(node.get("recommended_tools"))
            counters["selected_next_tool"] += _truthy_count(node.get("selected_next_tool"))
            counters["next_tool_emitted"] += _truthy_count(node.get("next_tool_emitted"))
            if node.get("tool_choice_mode") == "required":
                counters["required_tool_choice_records"] += 1
                node_policy_signal += 1
            file_rule_hits += node_rule_hits
            file_policy_signal += node_policy_signal
        if file_rule_hits and not file_policy_signal and len(counters["sample_rule_hit_no_policy_traces"]) < 10:
            counters["sample_rule_hit_no_policy_traces"].append(str(path))
    counters["policy_conversion_observed"] = bool(
        counters["policy_hits"]
        or counters["recommended_tools"]
        or counters["selected_next_tool"]
        or counters["next_tool_emitted"]
        or counters["required_tool_choice_records"]
    )
    counters["rule_hits_without_policy_hits"] = counters["rule_hits"] if not counters["policy_conversion_observed"] else 0
    if counters["rule_hits"] and not counters["policy_conversion_observed"]:
        counters["policy_conversion_absent_reason"] = "policy_artifact_or_runtime_candidate_missing"
        counters["policy_artifact_or_runtime_candidate_missing"] = True
    else:
        counters["policy_conversion_absent_reason"] = None
        counters["policy_artifact_or_runtime_candidate_missing"] = False
    return counters


def artifact_boundary_status(max_print: int = 20) -> dict[str, Any]:
    bad = artifact_boundary.forbidden_outputs(artifact_boundary.collect_output_paths())
    return {
        "artifact_boundary_passed": not bad,
        "forbidden_artifact_count": len(bad),
        "forbidden_artifact_examples": bad[:max_print],
    }


def policy_opportunity_status(
    path: Path = DEFAULT_POLICY_OPPORTUNITY,
    manifest_path: Path = DEFAULT_POLICY_MANIFEST,
    negative_control_path: Path = DEFAULT_POLICY_NEGATIVE_CONTROLS,
) -> dict[str, Any]:
    report = _load_json(path, {}) or {}
    manifest = _load_json(manifest_path, {}) or {}
    negative = _load_json(negative_control_path, {}) or {}
    low_risk_count = int(manifest.get("low_risk_dry_run_review_eligible_count") or 0)
    runtime_dry_run_compiler_ready = bool(low_risk_count >= 20 and negative.get("negative_control_audit_ready"))
    if low_risk_count < 20:
        runtime_blocker = "low_risk_support_too_small_or_witness_precision_pending"
    elif not negative.get("negative_control_audit_ready"):
        runtime_blocker = "negative_control_audit_not_ready"
    else:
        runtime_blocker = None
    return {
        "policy_conversion_opportunity_audit_ready": bool(report.get("policy_conversion_opportunity_audit_ready")),
        "policy_candidate_count": int(report.get("policy_candidate_count") or 0),
        "recommended_tools_count": int(report.get("recommended_tools_count") or 0),
        "candidate_capability_distribution": report.get("candidate_capability_distribution") or {},
        "recommended_tool_distribution": report.get("recommended_tool_distribution") or {},
        "postcondition_already_satisfied_count": int((report.get("rejection_reason_counts") or {}).get("postcondition_already_satisfied") or 0),
        "postcondition_low_risk_review_eligible_count": low_risk_count,
        "postcondition_negative_control_ready": bool(negative.get("negative_control_audit_ready")),
        "postcondition_negative_control_activation_count": int(negative.get("negative_control_activation_count") or 0),
        "postcondition_negative_control_activation_rate": negative.get("negative_control_activation_rate"),
        "runtime_dry_run_compiler_ready": runtime_dry_run_compiler_ready,
        "runtime_dry_run_compiler_blocker": runtime_blocker,
        "next_required_action": report.get("next_required_action"),
    }


def memory_obligation_status(path: Path = DEFAULT_MEMORY_OBLIGATION) -> dict[str, Any]:
    report = _load_json(path, {}) or {}
    negative = _load_json(path.parent / "memory_operation_negative_control_audit.json", {}) or {}
    approval = _load_json(path.parent / "memory_operation_approval_manifest.json", {}) or {}
    allowlist = _load_json(path.parent / "memory_operation_compiler_allowlist.json", {}) or {}
    return {
        "memory_operation_obligation_audit_ready": bool(report.get("candidate_count") is not None),
        "memory_operation_candidate_count": int(report.get("candidate_count") or 0),
        "memory_operation_candidate_distribution": report.get("candidate_operation_distribution") or {},
        "memory_operation_category_distribution": report.get("candidate_category_distribution") or {},
        "memory_operation_rejection_reason_counts": report.get("rejection_reason_counts") or {},
        "memory_operation_runtime_enabled": bool(report.get("runtime_enabled")),
        "memory_operation_negative_control_audit_passed": bool(negative.get("negative_control_audit_passed")),
        "memory_operation_approval_manifest_ready_for_review": bool(approval.get("approval_manifest_ready_for_review")),
        "memory_operation_approval_manifest_sanitized": bool(approval.get("approval_manifest_sanitized")),
        "memory_operation_review_manifest_compiler_input_eligible_count": int(approval.get("compiler_input_eligible_count") or 0),
        "memory_operation_compiler_allowlist_ready": bool(allowlist.get("compiler_allowlist_ready")),
        "memory_operation_compiler_allowlist_input_count": int(allowlist.get("compiler_input_eligible_count") or 0),
        "memory_operation_first_pass_review_candidate_count": int(approval.get("first_pass_review_candidate_count") or 0),
        "memory_operation_second_pass_review_candidate_count": int(approval.get("second_pass_review_candidate_count") or 0),
        "memory_operation_next_required_action": report.get("next_required_action"),
    }


def memory_dry_run_status(path: Path = DEFAULT_MEMORY_DRY_RUN) -> dict[str, Any]:
    report = _load_json(path, {}) or {}
    return {
        "memory_dry_run_policy_ready": bool(report.get("dry_run_policy_compile_ready")),
        "memory_dry_run_policy_unit_count": int(report.get("policy_unit_count") or 0),
        "memory_dry_run_selected_first_pass_count": int(report.get("selected_first_pass_count") or 0),
        "memory_dry_run_argument_creation_count": int(report.get("argument_creation_count") or 0),
        "memory_dry_run_runtime_enabled": bool(report.get("runtime_enabled")),
        "memory_dry_run_next_required_action": report.get("next_required_action"),
    }


def memory_resolver_status(path: Path = DEFAULT_MEMORY_RESOLVER) -> dict[str, Any]:
    report = _load_json(path, {}) or {}
    return {
        "memory_resolver_audit_passed": bool(report.get("resolver_audit_passed")),
        "memory_resolver_schema_records_scanned": int(report.get("schema_records_scanned") or 0),
        "memory_resolver_resolved_schema_count": int(report.get("resolved_schema_count") or 0),
        "memory_resolver_empty_resolution_count": int(report.get("empty_resolution_count") or 0),
        "memory_resolver_blocked_destructive_tool_count": int(report.get("blocked_destructive_tool_count") or 0),
        "memory_resolver_forbidden_mutation_resolved_count": int(report.get("forbidden_memory_mutation_tools_resolved_count") or 0),
        "memory_resolver_weak_witness_records_resolved_count": int(report.get("weak_witness_records_resolved_count") or 0),
        "memory_resolver_next_required_action": report.get("next_required_action"),
    }


def memory_activation_status(path: Path = DEFAULT_MEMORY_ACTIVATION) -> dict[str, Any]:
    report = _load_json(path, {}) or {}
    return {
        "memory_activation_simulation_passed": bool(report.get("activation_simulation_passed")),
        "memory_activation_count": int(report.get("activation_count") or 0),
        "memory_activation_blocked_count": int(report.get("blocked_count") or 0),
        "memory_activation_negative_control_count": int(report.get("negative_control_activation_count") or 0),
        "memory_activation_weak_lookup_count": int(report.get("weak_lookup_witness_activation_count") or 0),
        "memory_activation_argument_creation_count": int(report.get("argument_creation_count") or 0),
        "memory_activation_runtime_enabled": bool(report.get("runtime_enabled")),
        "memory_activation_next_required_action": report.get("next_required_action"),
    }



def memory_runtime_smoke_status(path: Path = DEFAULT_MEMORY_RUNTIME_SMOKE) -> dict[str, Any]:
    report = _load_json(path, {}) or {}
    return {
        "memory_runtime_adapter_ready": bool(report.get("memory_runtime_adapter_ready")),
        "memory_dev_smoke_ready": bool(report.get("memory_dev_smoke_ready")),
        "memory_runtime_loaded_rule_count": int(report.get("loaded_runtime_rule_count") or 0),
        "memory_runtime_loaded_memory_rule_count": int(report.get("loaded_memory_runtime_rule_count") or 0),
        "memory_runtime_smoke_next_required_action": report.get("next_required_action"),
    }


def postcondition_smoke_status(
    result_path: Path = DEFAULT_POSTCONDITION_SMOKE_RESULT,
    failure_path: Path = DEFAULT_POSTCONDITION_SMOKE_FAILURE,
    satisfaction_path: Path = DEFAULT_POSTCONDITION_SATISFACTION,
    protocol_path: Path = DEFAULT_POSTCONDITION_PROTOCOL,
) -> dict[str, Any]:
    result = _load_json(result_path, {}) or {}
    failure = _load_json(failure_path, {}) or {}
    satisfaction = _load_json(satisfaction_path, {}) or {}
    protocol = _load_json(protocol_path, {}) or {}
    return {
        "postcondition_smoke_result_ready": bool(result.get("report_scope") == "postcondition_guided_dev_smoke_result"),
        "postcondition_smoke_stop_loss_passed": bool(result.get("stop_loss_passed")),
        "postcondition_smoke_case_count": int(result.get("case_count") or 0),
        "postcondition_smoke_activated_case_count": int(result.get("activated_case_count") or 0),
        "postcondition_smoke_diagnostic_inactive_case_count": int(result.get("diagnostic_inactive_case_count") or 0),
        "postcondition_smoke_case_fixed_count": int(result.get("case_fixed_count") or 0),
        "postcondition_smoke_case_regressed_count": int(result.get("case_regressed_count") or 0),
        "postcondition_smoke_net_case_gain": int(result.get("net_case_gain") or 0),
        "postcondition_smoke_candidate_recommended_tool_match_count": int(result.get("candidate_recommended_tool_match_count") or 0),
        "postcondition_smoke_baseline_recommended_tool_match_count": int(result.get("baseline_recommended_tool_match_count") or 0),
        "postcondition_smoke_next_required_action": result.get("next_required_action"),
        "postcondition_smoke_failure_diagnosis_ready": bool(failure.get("report_scope") == "postcondition_guided_dev_smoke_failure_diagnosis"),
        "postcondition_smoke_primary_failure_source": failure.get("primary_failure_source"),
        "postcondition_smoke_activated_candidate_no_tool_count": int(failure.get("activated_candidate_no_tool_count") or 0),
        "postcondition_smoke_failure_source_distribution": failure.get("failure_source_distribution") or {},
        "postcondition_satisfaction_audit_ready": bool(satisfaction.get("report_scope") == "postcondition_satisfaction_audit"),
        "postcondition_candidate_mining_gap_filter_passed": bool(satisfaction.get("candidate_mining_gap_filter_passed")),
        "postcondition_already_satisfied_in_smoke_count": int(satisfaction.get("postcondition_already_satisfied_count") or 0),
        "postcondition_unmet_strong_in_smoke_count": int(satisfaction.get("postcondition_unmet_strong_count") or 0),
        "postcondition_satisfaction_recommended_next_action": satisfaction.get("recommended_next_action"),
        "postcondition_smoke_protocol_ready_for_review": bool(protocol.get("smoke_protocol_ready_for_review")),
        "postcondition_smoke_protocol_selected_case_count": int(protocol.get("selected_case_count") or 0),
        "postcondition_smoke_protocol_runtime_replay_activation_count": int(protocol.get("runtime_replay_activation_count") or 0),
        "postcondition_smoke_protocol_first_failure": protocol.get("first_failure"),
        "postcondition_protocol_gating_state": "ready_for_review" if protocol.get("smoke_protocol_ready_for_review") else "fail_closed",
        "postcondition_smoke_evidence_classification": "negative_evidence_blocked_claim"
        if result.get("report_scope") == "postcondition_guided_dev_smoke_result" and not result.get("stop_loss_passed")
        else "not_run_or_positive_pending",
    }


def unmet_postcondition_source_status(path: Path = DEFAULT_UNMET_POSTCONDITION_AUDIT) -> dict[str, Any]:
    report = _load_json(path, {}) or {}
    return {
        "unmet_postcondition_source_expansion_audit_ready": bool(report.get("unmet_postcondition_source_expansion_audit_ready")),
        "typed_satisfaction_distribution": report.get("typed_satisfaction_distribution") or {},
        "strong_unmet_candidate_count": int(report.get("strong_unmet_candidate_count") or 0),
        "low_risk_strong_unmet_candidate_count": int(report.get("low_risk_strong_unmet_candidate_count") or 0),
        "high_risk_strong_unmet_candidate_count": int(report.get("high_risk_strong_unmet_candidate_count") or 0),
        "strong_unmet_capability_distribution": report.get("strong_unmet_capability_distribution") or {},
        "strong_unmet_risk_lane_distribution": report.get("strong_unmet_risk_lane_distribution") or {},
        "unmet_postcondition_next_required_action": report.get("next_required_action"),
    }

def source_result_layout_status(low_risk_root: Path = DEFAULT_LOW_RISK) -> dict[str, Any]:
    availability = _load_json(low_risk_root / "m28pre_source_result_availability_audit.json", {}) or {}
    alias = _load_json(low_risk_root / "wrong_arg_key_alias_coverage_audit.json", {}) or {}
    deterministic = _load_json(low_risk_root / "deterministic_schema_local_coverage_audit.json", {}) or {}
    issue_counts = availability.get("issue_counts") or {}
    hard_issue_counts = availability.get("hard_issue_counts") or {}
    alias_rejections = alias.get("rejection_reason_counts") or {}
    deterministic_rejections = deterministic.get("rejection_reason_counts") or {}
    source_scope_mismatch_count = int(issue_counts.get("source_result_case_not_collected") or 0)
    audit_missing_source_result_count = max(
        int(alias_rejections.get("missing_source_result") or 0),
        int(deterministic_rejections.get("missing_source_result") or 0),
    )
    if source_scope_mismatch_count and not hard_issue_counts:
        root_cause = "source_collection_subset_vs_full_dataset_audit_scope_mismatch"
        route = "align_audit_scope_with_source_collection_subset"
    elif hard_issue_counts:
        root_cause = "source_result_parser_or_layout_hard_issue"
        route = "fix_parser_or_source_result_layout"
    else:
        root_cause = "true_low_family_coverage_or_non_unique_mapping"
        route = deterministic.get("route_recommendation") or alias.get("route_recommendation")
    return {
        "source_result_availability_ready": availability.get("source_result_availability_ready"),
        "availability_hard_issue_counts": hard_issue_counts,
        "availability_issue_counts": issue_counts,
        "source_scope_mismatch_count": source_scope_mismatch_count,
        "audit_missing_source_result_count": audit_missing_source_result_count,
        "source_result_root_cause": root_cause,
        "wrong_arg_key_alias_family_coverage_zero": alias.get("wrong_arg_key_alias_family_coverage_zero"),
        "wrong_arg_key_alias_rejection_reason_counts": alias_rejections,
        "deterministic_schema_local_family_coverage_zero": deterministic.get("deterministic_schema_local_family_coverage_zero"),
        "deterministic_schema_local_rejection_reason_counts": deterministic_rejections,
        "route_recommendation": route,
    }


def evaluate(
    subset_root: Path = DEFAULT_SUBSET,
    low_risk_root: Path = DEFAULT_LOW_RISK,
    phase2_validation_root: Path = DEFAULT_PHASE2_VALIDATION,
) -> dict[str, Any]:
    m28 = evaluate_m28pre(subset_root, low_risk_root)
    ctspc_status = _load_json(subset_root / "m27ae_ctspc_v0_status.json", {}) or {}
    ctspc_summary = _load_json(subset_root / "subset_summary.json", {}) or {}
    boundary = artifact_boundary_status()
    policy = policy_conversion_counters(phase2_validation_root)
    source_layout = source_result_layout_status(low_risk_root)
    policy_opportunity = policy_opportunity_status()
    memory_obligation = memory_obligation_status()
    memory_dry_run = memory_dry_run_status()
    memory_resolver = memory_resolver_status()
    memory_activation = memory_activation_status()
    memory_runtime_smoke = memory_runtime_smoke_status()
    postcondition_smoke = postcondition_smoke_status()
    unmet_postcondition = unmet_postcondition_source_status()
    p0_blockers: list[str] = []
    if not boundary["artifact_boundary_passed"]:
        p0_blockers.append("artifact_boundary_not_clean")
    if not m28.get("m2_8pre_offline_passed"):
        p0_blockers.append("m2_8pre_offline_not_passed")
    if not m28.get("scorer_authorization_ready"):
        p0_blockers.append("scorer_authorization_not_ready")
    if not policy.get("policy_conversion_observed"):
        p0_blockers.append("policy_conversion_not_observed_in_existing_traces")
    if not policy_opportunity.get("policy_conversion_opportunity_audit_ready"):
        p0_blockers.append("policy_conversion_opportunity_audit_missing")
    if not policy_opportunity.get("runtime_dry_run_compiler_ready"):
        p0_blockers.append("runtime_dry_run_compiler_not_ready")
    if ctspc_status.get("retain") != 0:
        p0_blockers.append("ctspc_v0_retain_not_zero")
    if ctspc_status.get("scorer_default") != "off":
        p0_blockers.append("ctspc_v0_not_off_by_default")
    if postcondition_smoke.get("postcondition_smoke_result_ready") and not postcondition_smoke.get("postcondition_smoke_stop_loss_passed"):
        p0_blockers.append("postcondition_dev_smoke_stop_loss_failed")
    if postcondition_smoke.get("postcondition_satisfaction_audit_ready") and not postcondition_smoke.get("postcondition_candidate_mining_gap_filter_passed"):
        p0_blockers.append("postcondition_candidate_mining_gap_filter_not_passed")
    if postcondition_smoke.get("postcondition_smoke_protocol_selected_case_count") and not postcondition_smoke.get("postcondition_smoke_protocol_ready_for_review"):
        p0_blockers.append("postcondition_smoke_protocol_not_ready")
    if unmet_postcondition.get("unmet_postcondition_source_expansion_audit_ready") and unmet_postcondition.get("low_risk_strong_unmet_candidate_count", 0) < 9:
        p0_blockers.append("low_risk_unmet_postcondition_pool_too_small")
    if memory_activation.get("memory_activation_simulation_passed") and not memory_runtime_smoke.get("memory_runtime_adapter_ready"):
        p0_blockers.append("memory_runtime_adapter_not_ready")
    return {
        "report_scope": "first_stage_delivery_evidence_audit",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "delivery_claim_status": "scaffold_and_diagnostic_package_only",
        "sota_3pp_claim_ready": False,
        "p0_blockers": p0_blockers,
        "artifact_boundary": boundary,
        "m28pre_gate": {
            "m2_8pre_offline_passed": m28.get("m2_8pre_offline_passed"),
            "scorer_authorization_ready": m28.get("scorer_authorization_ready"),
            "remaining_gap_to_35_demote_candidates": m28.get("remaining_gap_to_35_demote_candidates"),
            "blockers": m28.get("blockers"),
            "route_recommendation": m28.get("route_recommendation"),
        },
        "ctspc_v0": {
            "status": ctspc_status.get("status"),
            "ctspc_v0_frozen": ctspc_status.get("ctspc_v0_frozen"),
            "scorer_default": ctspc_status.get("scorer_default"),
            "retain": ctspc_status.get("retain"),
            "dev_rerun_authorized": ctspc_status.get("dev_rerun_authorized"),
            "holdout_authorized": ctspc_status.get("holdout_authorized"),
            "latest_candidate_accuracy": ctspc_summary.get("candidate_accuracy"),
            "latest_baseline_accuracy": ctspc_summary.get("baseline_accuracy"),
            "latest_net_case_gain": ctspc_summary.get("net_case_gain"),
        },
        "policy_conversion": policy,
        "policy_conversion_opportunity": policy_opportunity,
        "postcondition_smoke": postcondition_smoke,
        "unmet_postcondition_source_expansion": unmet_postcondition,
        "memory_operation_obligation": memory_obligation,
        "memory_operation_dry_run": memory_dry_run,
        "memory_tool_family_resolver": memory_resolver,
        "memory_activation_simulation": memory_activation,
        "memory_runtime_smoke": memory_runtime_smoke,
        "source_result_layout": source_layout,
        "next_required_action": "root_cause_audit_before_any_scorer",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# First-Stage Delivery Evidence Audit",
        "",
        f"- Claim status: `{report['delivery_claim_status']}`",
        f"- SOTA +3pp claim ready: `{report['sota_3pp_claim_ready']}`",
        f"- Offline only: `{report['offline_only']}`",
        f"- P0 blockers: `{report['p0_blockers']}`",
        "",
        "## Gate Snapshot",
        "",
        f"- Artifact boundary passed: `{report['artifact_boundary']['artifact_boundary_passed']}`",
        f"- Forbidden artifact count: `{report['artifact_boundary']['forbidden_artifact_count']}`",
        f"- M2.8-pre passed: `{report['m28pre_gate']['m2_8pre_offline_passed']}`",
        f"- Scorer authorization ready: `{report['m28pre_gate']['scorer_authorization_ready']}`",
        f"- Remaining gap to 35 demote candidates: `{report['m28pre_gate']['remaining_gap_to_35_demote_candidates']}`",
        "",
        "## Policy Conversion Evidence",
        "",
        f"- Trace files scanned: `{report['policy_conversion']['trace_files_scanned']}`",
        f"- Rule hits: `{report['policy_conversion']['rule_hits']}`",
        f"- Policy hits: `{report['policy_conversion']['policy_hits']}`",
        f"- Recommended tools: `{report['policy_conversion']['recommended_tools']}`",
        f"- Selected next tool: `{report['policy_conversion']['selected_next_tool']}`",
        f"- Next tool emitted: `{report['policy_conversion']['next_tool_emitted']}`",
        f"- Policy conversion observed: `{report['policy_conversion']['policy_conversion_observed']}`",
        f"- Rule hits without policy hits: `{report['policy_conversion']['rule_hits_without_policy_hits']}`",
        f"- Policy conversion absent reason: `{report['policy_conversion']['policy_conversion_absent_reason']}`",
        "",
        "## Policy Opportunity Evidence",
        "",
        f"- Opportunity audit ready: `{report['policy_conversion_opportunity']['policy_conversion_opportunity_audit_ready']}`",
        f"- Policy candidate count: `{report['policy_conversion_opportunity']['policy_candidate_count']}`",
        f"- Recommended tools count: `{report['policy_conversion_opportunity']['recommended_tools_count']}`",
        f"- Candidate capability distribution: `{report['policy_conversion_opportunity']['candidate_capability_distribution']}`",
        f"- Postcondition low-risk review eligible: `{report['policy_conversion_opportunity']['postcondition_low_risk_review_eligible_count']}`",
        f"- Postcondition already satisfied filtered: `{report['policy_conversion_opportunity']['postcondition_already_satisfied_count']}`",
        f"- Postcondition negative controls ready: `{report['policy_conversion_opportunity']['postcondition_negative_control_ready']}`",
        f"- Postcondition negative-control activation count: `{report['policy_conversion_opportunity']['postcondition_negative_control_activation_count']}`",
        f"- Runtime dry-run compiler ready: `{report['policy_conversion_opportunity']['runtime_dry_run_compiler_ready']}`",
        f"- Runtime dry-run compiler blocker: `{report['policy_conversion_opportunity']['runtime_dry_run_compiler_blocker']}`",
        "",

        "## Postcondition Dev Smoke Evidence",
        "",
        f"- Smoke result ready: `{report['postcondition_smoke']['postcondition_smoke_result_ready']}`",
        f"- Smoke stop-loss passed: `{report['postcondition_smoke']['postcondition_smoke_stop_loss_passed']}`",
        f"- Smoke cases / activated / diagnostic inactive: `{report['postcondition_smoke']['postcondition_smoke_case_count']}` / `{report['postcondition_smoke']['postcondition_smoke_activated_case_count']}` / `{report['postcondition_smoke']['postcondition_smoke_diagnostic_inactive_case_count']}`",
        f"- Fixed / regressed / net gain: `{report['postcondition_smoke']['postcondition_smoke_case_fixed_count']}` / `{report['postcondition_smoke']['postcondition_smoke_case_regressed_count']}` / `{report['postcondition_smoke']['postcondition_smoke_net_case_gain']}`",
        f"- Candidate recommended-tool matches: `{report['postcondition_smoke']['postcondition_smoke_candidate_recommended_tool_match_count']}`",
        f"- Primary failure source: `{report['postcondition_smoke']['postcondition_smoke_primary_failure_source']}`",
        f"- Activated candidate no-tool count: `{report['postcondition_smoke']['postcondition_smoke_activated_candidate_no_tool_count']}`",
        f"- Satisfaction audit ready: `{report['postcondition_smoke']['postcondition_satisfaction_audit_ready']}`",
        f"- Candidate mining gap filter passed: `{report['postcondition_smoke']['postcondition_candidate_mining_gap_filter_passed']}`",
        f"- Already satisfied in smoke: `{report['postcondition_smoke']['postcondition_already_satisfied_in_smoke_count']}`",
        f"- Strong unmet in smoke: `{report['postcondition_smoke']['postcondition_unmet_strong_in_smoke_count']}`",
        f"- Current smoke protocol ready: `{report['postcondition_smoke']['postcondition_smoke_protocol_ready_for_review']}`",
        f"- Current selected cases / runtime replay activation: `{report['postcondition_smoke']['postcondition_smoke_protocol_selected_case_count']}` / `{report['postcondition_smoke']['postcondition_smoke_protocol_runtime_replay_activation_count']}`",
        f"- Current protocol first failure: `{report['postcondition_smoke']['postcondition_smoke_protocol_first_failure']}`",
        f"- Protocol gating state: `{report['postcondition_smoke']['postcondition_protocol_gating_state']}`",
        f"- Evidence classification: `{report['postcondition_smoke']['postcondition_smoke_evidence_classification']}`",
        "",

        "## Unmet Postcondition Source Expansion",
        "",
        f"- Audit ready: `{report['unmet_postcondition_source_expansion']['unmet_postcondition_source_expansion_audit_ready']}`",
        f"- Typed satisfaction distribution: `{report['unmet_postcondition_source_expansion']['typed_satisfaction_distribution']}`",
        f"- Strong unmet candidates: `{report['unmet_postcondition_source_expansion']['strong_unmet_candidate_count']}`",
        f"- Low-risk strong unmet candidates: `{report['unmet_postcondition_source_expansion']['low_risk_strong_unmet_candidate_count']}`",
        f"- High-risk strong unmet candidates: `{report['unmet_postcondition_source_expansion']['high_risk_strong_unmet_candidate_count']}`",
        f"- Strong unmet capability distribution: `{report['unmet_postcondition_source_expansion']['strong_unmet_capability_distribution']}`",
        f"- Strong unmet risk lane distribution: `{report['unmet_postcondition_source_expansion']['strong_unmet_risk_lane_distribution']}`",
        f"- Next action: `{report['unmet_postcondition_source_expansion']['unmet_postcondition_next_required_action']}`",
        "",
        "## Memory Operation Obligation Evidence",
        "",
        f"- Memory audit ready: `{report['memory_operation_obligation']['memory_operation_obligation_audit_ready']}`",
        f"- Memory operation candidates: `{report['memory_operation_obligation']['memory_operation_candidate_count']}`",
        f"- Memory candidate operations: `{report['memory_operation_obligation']['memory_operation_candidate_distribution']}`",
        f"- Memory candidate categories: `{report['memory_operation_obligation']['memory_operation_category_distribution']}`",
        f"- Memory runtime enabled: `{report['memory_operation_obligation']['memory_operation_runtime_enabled']}`",
        f"- Memory negative controls passed: `{report['memory_operation_obligation']['memory_operation_negative_control_audit_passed']}`",
        f"- Memory approval manifest ready: `{report['memory_operation_obligation']['memory_operation_approval_manifest_ready_for_review']}`",
        f"- Memory approval manifest sanitized: `{report['memory_operation_obligation']['memory_operation_approval_manifest_sanitized']}`",
        f"- Memory review manifest compiler input eligible count: `{report['memory_operation_obligation']['memory_operation_review_manifest_compiler_input_eligible_count']}`",
        f"- Memory compiler allowlist ready: `{report['memory_operation_obligation']['memory_operation_compiler_allowlist_ready']}`",
        f"- Memory compiler allowlist input count: `{report['memory_operation_obligation']['memory_operation_compiler_allowlist_input_count']}`",
        f"- Memory first-pass review candidates: `{report['memory_operation_obligation']['memory_operation_first_pass_review_candidate_count']}`",
        f"- Memory second-pass review candidates: `{report['memory_operation_obligation']['memory_operation_second_pass_review_candidate_count']}`",
        f"- Memory dry-run policy ready: `{report['memory_operation_dry_run']['memory_dry_run_policy_ready']}`",
        f"- Memory dry-run policy units: `{report['memory_operation_dry_run']['memory_dry_run_policy_unit_count']}`",
        f"- Memory dry-run first-pass support: `{report['memory_operation_dry_run']['memory_dry_run_selected_first_pass_count']}`",
        f"- Memory dry-run argument creation count: `{report['memory_operation_dry_run']['memory_dry_run_argument_creation_count']}`",
        f"- Memory resolver audit passed: `{report['memory_tool_family_resolver']['memory_resolver_audit_passed']}`",
        f"- Memory resolver resolved schemas: `{report['memory_tool_family_resolver']['memory_resolver_resolved_schema_count']}`",
        f"- Memory resolver blocked destructive tools: `{report['memory_tool_family_resolver']['memory_resolver_blocked_destructive_tool_count']}`",
        f"- Memory resolver forbidden mutation resolved count: `{report['memory_tool_family_resolver']['memory_resolver_forbidden_mutation_resolved_count']}`",
        f"- Memory activation simulation passed: `{report['memory_activation_simulation']['memory_activation_simulation_passed']}`",
        f"- Memory activation count: `{report['memory_activation_simulation']['memory_activation_count']}`",
        f"- Memory activation negative-control count: `{report['memory_activation_simulation']['memory_activation_negative_control_count']}`",
        f"- Memory activation argument creation count: `{report['memory_activation_simulation']['memory_activation_argument_creation_count']}`",
        f"- Memory runtime adapter ready: `{report['memory_runtime_smoke']['memory_runtime_adapter_ready']}`",
        f"- Memory dev smoke ready: `{report['memory_runtime_smoke']['memory_dev_smoke_ready']}`",
        f"- Memory runtime loaded memory rules: `{report['memory_runtime_smoke']['memory_runtime_loaded_memory_rule_count']}`",
        f"- Memory runtime smoke next action: `{report['memory_runtime_smoke']['memory_runtime_smoke_next_required_action']}`",
        "",
        "## Source/Layout Evidence",
        "",
        f"- Source result availability ready: `{report['source_result_layout']['source_result_availability_ready']}`",
        f"- Alias family coverage zero: `{report['source_result_layout']['wrong_arg_key_alias_family_coverage_zero']}`",
        f"- Deterministic family coverage zero: `{report['source_result_layout']['deterministic_schema_local_family_coverage_zero']}`",
        f"- Source result root cause: `{report['source_result_layout']['source_result_root_cause']}`",
        f"- Source scope mismatch count: `{report['source_result_layout']['source_scope_mismatch_count']}`",
        f"- Audit missing source result count: `{report['source_result_layout']['audit_missing_source_result_count']}`",
        f"- Route recommendation: `{report['source_result_layout']['route_recommendation']}`",
        "",
        "This audit is diagnostic. It does not authorize BFCL/model/scorer runs.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset-root", type=Path, default=DEFAULT_SUBSET)
    parser.add_argument("--low-risk-root", type=Path, default=DEFAULT_LOW_RISK)
    parser.add_argument("--phase2-validation-root", type=Path, default=DEFAULT_PHASE2_VALIDATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.subset_root, args.low_risk_root, args.phase2_validation_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "delivery_claim_status": report["delivery_claim_status"],
            "sota_3pp_claim_ready": report["sota_3pp_claim_ready"],
            "p0_blockers": report["p0_blockers"],
            "artifact_boundary_passed": report["artifact_boundary"]["artifact_boundary_passed"],
            "m2_8pre_offline_passed": report["m28pre_gate"]["m2_8pre_offline_passed"],
            "scorer_authorization_ready": report["m28pre_gate"]["scorer_authorization_ready"],
            "policy_conversion_observed": report["policy_conversion"]["policy_conversion_observed"],
            "postcondition_policy_candidate_count": report["policy_conversion_opportunity"]["policy_candidate_count"],
            "postcondition_low_risk_review_eligible_count": report["policy_conversion_opportunity"]["postcondition_low_risk_review_eligible_count"],
            "postcondition_already_satisfied_count": report["policy_conversion_opportunity"]["postcondition_already_satisfied_count"],
            "postcondition_negative_control_ready": report["policy_conversion_opportunity"]["postcondition_negative_control_ready"],
            "runtime_dry_run_compiler_ready": report["policy_conversion_opportunity"]["runtime_dry_run_compiler_ready"],
            "postcondition_smoke_stop_loss_passed": report["postcondition_smoke"]["postcondition_smoke_stop_loss_passed"],
            "postcondition_smoke_net_case_gain": report["postcondition_smoke"]["postcondition_smoke_net_case_gain"],
            "postcondition_candidate_mining_gap_filter_passed": report["postcondition_smoke"]["postcondition_candidate_mining_gap_filter_passed"],
            "postcondition_already_satisfied_in_smoke_count": report["postcondition_smoke"]["postcondition_already_satisfied_in_smoke_count"],
            "postcondition_unmet_strong_in_smoke_count": report["postcondition_smoke"]["postcondition_unmet_strong_in_smoke_count"],
            "postcondition_smoke_protocol_ready_for_review": report["postcondition_smoke"]["postcondition_smoke_protocol_ready_for_review"],
            "postcondition_protocol_gating_state": report["postcondition_smoke"]["postcondition_protocol_gating_state"],
            "postcondition_smoke_evidence_classification": report["postcondition_smoke"]["postcondition_smoke_evidence_classification"],
            "low_risk_strong_unmet_postcondition_count": report["unmet_postcondition_source_expansion"]["low_risk_strong_unmet_candidate_count"],
            "high_risk_strong_unmet_postcondition_count": report["unmet_postcondition_source_expansion"]["high_risk_strong_unmet_candidate_count"],
            "memory_operation_candidate_count": report["memory_operation_obligation"]["memory_operation_candidate_count"],
            "memory_operation_runtime_enabled": report["memory_operation_obligation"]["memory_operation_runtime_enabled"],
            "memory_operation_negative_control_audit_passed": report["memory_operation_obligation"]["memory_operation_negative_control_audit_passed"],
            "memory_operation_approval_manifest_ready_for_review": report["memory_operation_obligation"]["memory_operation_approval_manifest_ready_for_review"],
            "memory_operation_review_manifest_compiler_input_eligible_count": report["memory_operation_obligation"]["memory_operation_review_manifest_compiler_input_eligible_count"],
            "memory_operation_compiler_allowlist_ready": report["memory_operation_obligation"]["memory_operation_compiler_allowlist_ready"],
            "memory_operation_compiler_allowlist_input_count": report["memory_operation_obligation"]["memory_operation_compiler_allowlist_input_count"],
            "memory_dry_run_policy_ready": report["memory_operation_dry_run"]["memory_dry_run_policy_ready"],
            "memory_dry_run_policy_unit_count": report["memory_operation_dry_run"]["memory_dry_run_policy_unit_count"],
            "memory_dry_run_selected_first_pass_count": report["memory_operation_dry_run"]["memory_dry_run_selected_first_pass_count"],
            "memory_resolver_audit_passed": report["memory_tool_family_resolver"]["memory_resolver_audit_passed"],
            "memory_resolver_resolved_schema_count": report["memory_tool_family_resolver"]["memory_resolver_resolved_schema_count"],
            "memory_activation_simulation_passed": report["memory_activation_simulation"]["memory_activation_simulation_passed"],
            "memory_activation_count": report["memory_activation_simulation"]["memory_activation_count"],
            "memory_runtime_adapter_ready": report["memory_runtime_smoke"]["memory_runtime_adapter_ready"],
            "memory_dev_smoke_ready": report["memory_runtime_smoke"]["memory_dev_smoke_ready"],
            "memory_runtime_loaded_memory_rule_count": report["memory_runtime_smoke"]["memory_runtime_loaded_memory_rule_count"],
            "policy_opportunity_candidate_count": report["policy_conversion_opportunity"]["policy_candidate_count"],
            "next_required_action": report["next_required_action"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
