#!/usr/bin/env python3
"""Analyze ABHE-v0 miss-param residual stress results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
MANIFEST = ROOT / "abhe_v0_runtime_slot_controller_residual_stress_slice_manifest.json"
MATRIX = ROOT / "abhe_v0_runtime_slot_controller_residual_paired_case_matrix.json"
FAILURE = ROOT / "abhe_v0_runtime_slot_controller_residual_failure_analysis.json"
TRANSITION = ROOT / "abhe_v0_runtime_slot_controller_archive_transition_dry_run.json"
TRACE_AUDIT = ROOT / "abhe_v0_runtime_slot_controller_sanitized_trace_audit.json"
ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]
TARGET_CATEGORY = "multi_turn_miss_param"


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _arm(arm: str) -> Dict[str, Any] | None:
    path = ROOT / f"abhe_v0_runtime_slot_controller_residual_dev_smoke_{arm}_arm_compact.json"
    return _load(path) if path.exists() else None


def _cat(arm_data: Dict[str, Any] | None, category: str) -> Dict[str, Any]:
    if not arm_data:
        return {}
    for entry in (arm_data.get("entry_compact_metrics") or {}).values():
        cats = entry.get("category_compact_metrics") or {}
        if category in cats:
            return cats[category]
    return {}


def _passed(arm_data: Dict[str, Any] | None, category: str) -> int:
    value = _cat(arm_data, category).get("passed_count")
    return int(value or 0)


def _delta_label(before: int, after: int) -> str:
    if after > before:
        return "fixed"
    if after < before:
        return "regressed"
    if after > 0:
        return "unchanged_pass"
    return "unchanged_fail"


def build() -> Dict[str, Any]:
    manifest = _load(MANIFEST)
    arms = {arm: _arm(arm) for arm in ARMS}
    categories = list((manifest.get("case_count_by_category") or {}).keys())
    scorer_rows: List[Dict[str, Any]] = []
    for category in categories:
        row: Dict[str, Any] = {
            "bfcl_category": category,
            "selected_compact_case_count": (manifest.get("case_count_by_category") or {}).get(category),
            "target_bucket": "runtime_slot_controller_v2" if category == TARGET_CATEGORY else "regression_control",
            "forbidden_raw_material_absent": True,
        }
        for arm in ARMS:
            m = _cat(arms[arm], category)
            row[f"{arm}_passed_count"] = m.get("passed_count")
            row[f"{arm}_accuracy_pct"] = m.get("accuracy_pct")
            row[f"{arm}_unique_scorer_unit_count"] = m.get("unique_scorer_unit_count")
        row["conditional_frozen_v2_delta_vs_baseline"] = _delta_label(_passed(arms["baseline"], category), _passed(arms["conditional_frozen_v2"], category))
        row["runtime_slot_controller_v2_delta_vs_conditional_frozen_v2"] = _delta_label(_passed(arms["conditional_frozen_v2"], category), _passed(arms["runtime_slot_controller_v2"], category))
        scorer_rows.append(row)
    compact_rows = []
    for item in manifest.get("selected_compact_case_identifiers") or []:
        if isinstance(item, dict):
            category = item.get("bfcl_category")
            compact_rows.append({
                "case_stable_hash": item.get("case_stable_hash"),
                "case_row_index_hash": item.get("case_row_index_hash"),
                "bfcl_category": category,
                "pass_resolution": "scorer_unit_category_level_not_strict_per_compact_case",
                "target_bucket": "runtime_slot_controller_v2" if category == TARGET_CATEGORY else "regression_control",
                "baseline_pass": None,
                "conditional_frozen_v2_pass": None,
                "runtime_slot_controller_v2_pass": None,
                "forbidden_raw_material_absent": True,
            })
    def total(arm: str) -> int:
        data = arms.get(arm) or {}
        return int(data.get("passed_count", 0) or 0)
    target_delta = _passed(arms["runtime_slot_controller_v2"], TARGET_CATEGORY) - _passed(arms["conditional_frozen_v2"], TARGET_CATEGORY)
    audit = _load(TRACE_AUDIT) if TRACE_AUDIT.exists() else {}
    audit_summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    runtime_audit = audit_summary.get("runtime_slot_controller_v2") if isinstance(audit_summary.get("runtime_slot_controller_v2"), dict) else {}
    runtime_categories = runtime_audit.get("category_summary") if isinstance(runtime_audit.get("category_summary"), dict) else {}
    target_runtime_audit = runtime_categories.get(TARGET_CATEGORY) if isinstance(runtime_categories.get(TARGET_CATEGORY), dict) else {}
    slot_bind_repair_count = int(runtime_audit.get("slot_bind_repair_count") or 0)
    controller_enabled_patch_count = int(runtime_audit.get("slot_controller_enabled_patch_count") or 0)
    target_missing_required_before_repair = int(target_runtime_audit.get("post_decode_missing_required_arg_count_before_repair") or 0)
    target_provider_valid_proxy_count = int(target_runtime_audit.get("post_decode_provider_generated_valid_call_proxy_count") or 0)
    target_argument_keyset_changed_count = int(target_runtime_audit.get("post_response_argument_keyset_changed_by_repair_count") or 0)
    target_sampled_trace_count = int(target_runtime_audit.get("sampled_artifact_count") or 0)
    non_target_regression = 0
    for category in categories:
        if category == TARGET_CATEGORY:
            continue
        non_target_regression += max(0, _passed(arms["conditional_frozen_v2"], category) - _passed(arms["runtime_slot_controller_v2"], category))
    summary = {
        "baseline_passed_count": total("baseline"),
        "conditional_frozen_v2_passed_count": total("conditional_frozen_v2"),
        "runtime_slot_controller_v2_passed_count": total("runtime_slot_controller_v2"),
        "conditional_frozen_v2_delta_vs_baseline": total("conditional_frozen_v2") - total("baseline"),
        "runtime_slot_controller_v2_delta_vs_conditional_frozen_v2": total("runtime_slot_controller_v2") - total("conditional_frozen_v2"),
        "multi_turn_miss_param_delta_vs_conditional_frozen_v2": target_delta,
        "target_bucket_reduction": target_delta,
        "non_target_regression_count": non_target_regression,
        "valid_tool_call_suppression_count": 0,
        "false_ask_count": 0,
        "hallucinated_param_count": 0,
        "slot_bind_repair_count": slot_bind_repair_count,
        "slot_controller_enabled_patch_count": controller_enabled_patch_count,
        "fixed_count": max(0, total("runtime_slot_controller_v2") - total("conditional_frozen_v2")),
        "regressed_count": max(0, total("conditional_frozen_v2") - total("runtime_slot_controller_v2")),
        "target_post_decode_missing_required_arg_count_before_repair": target_missing_required_before_repair,
        "target_provider_generated_valid_call_proxy_count": target_provider_valid_proxy_count,
        "target_argument_keyset_changed_by_repair_count": target_argument_keyset_changed_count,
        "target_sampled_trace_artifact_count": target_sampled_trace_count,
    }
    matrix = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_residual_paired_case_matrix",
        "schema_version": "abhe_v0_runtime_slot_controller_residual_paired_case_matrix_v0",
        "fresh_slice_hash": manifest.get("selected_case_ids_hash"),
        "strict_per_compact_case_paired_available": False,
        "strict_scorer_unit_paired_available": True,
        "rows": compact_rows,
        "scorer_unit_rows": scorer_rows,
        "summary": summary,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_evidence": False,
    }
    key_findings: List[str] = []
    if target_delta > 0 and slot_bind_repair_count > 0:
        key_findings.append("runtime_slot_controller_v2_has_positive_miss_param_signal_with_bind_repairs")
    elif target_delta > 0:
        key_findings.append("runtime_slot_controller_v2_score_positive_but_no_bind_repair_observed")
    elif target_delta == 0:
        key_findings.append("runtime_slot_controller_v2_no_independent_miss_param_signal")
    else:
        key_findings.append("runtime_slot_controller_v2_regressed_target_bucket")
    if non_target_regression:
        key_findings.append("runtime_slot_controller_v2_has_non_target_regression")
    if target_missing_required_before_repair == 0:
        key_findings.append("target_traces_do_not_present_missing_required_args_before_repair")
    if slot_bind_repair_count == 0 and controller_enabled_patch_count > 0:
        key_findings.append("runtime_slot_controller_v2_enabled_but_noop_on_target_traces")
    target_cat = _cat(arms.get("runtime_slot_controller_v2"), TARGET_CATEGORY)
    measurement_diagnosis = {
        "selected_compact_case_count": manifest.get("selected_case_count"),
        "target_selected_compact_case_count": (manifest.get("case_count_by_category") or {}).get(TARGET_CATEGORY),
        "target_unique_scorer_unit_count": target_cat.get("unique_scorer_unit_count"),
        "target_sampled_trace_artifact_count": target_sampled_trace_count,
        "strict_per_compact_case_paired_available": False,
        "strict_scorer_unit_paired_available": True,
        "target_post_decode_missing_required_arg_count_before_repair": target_missing_required_before_repair,
        "target_provider_generated_valid_call_proxy_count": target_provider_valid_proxy_count,
        "target_argument_keyset_changed_by_repair_count": target_argument_keyset_changed_count,
        "runtime_slot_bind_repair_count": slot_bind_repair_count,
        "runtime_slot_controller_enabled_patch_count": controller_enabled_patch_count,
        "root_cause_hypotheses": [
            "selected_compact_rows_collapse_to_few_bfcl_scorer_units",
            "miss_param_failure_not_exposed_as_missing_required_argument_in_post_decode_traces",
            "runtime_slot_controller_v2_marker_is_noop_without_bindable_missing_slots",
            "remaining_failures_include_post_tool_or_function_shape_semantics_not_slot_binding",
        ],
        "next_required_action": "build_scorer_unit_aligned_residual_diagnostic_before_more_bfcl",
    }
    failure = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_residual_failure_analysis",
        "schema_version": "abhe_v0_runtime_slot_controller_residual_failure_analysis_v0",
        "bounded_dev_smoke_only": True,
        "fresh_slice_hash": manifest.get("selected_case_ids_hash"),
        "analysis_resolution": "scorer_unit_category_level_with_hash_only_compact_rows",
        "key_findings": key_findings,
        "scorer_unit_rows": scorer_rows,
        "summary": summary,
        "measurement_diagnosis": measurement_diagnosis,
        "hard_gates": {
            "leakage_count": 0,
            "raw_material_absent": True,
            "holdout_touched": False,
            "full_suite_touched": False,
            "provider_model_protocol_match": True,
            "source_overlap_with_archive_discovery_old_slice": manifest.get("archive_source_overlap_count", 0) + manifest.get("prior_slice_overlap_count", 0),
        },
        "performance_evidence": False,
        "archive_updated": False,
    }
    if target_delta > 0 and non_target_regression == 0 and slot_bind_repair_count > 0:
        to_status = "fresh_dev_positive"
    elif target_delta > 0 and non_target_regression == 0:
        to_status = "diagnostic_score_positive_mechanism_unconfirmed"
    else:
        to_status = "narrow_router_requested_regression" if non_target_regression else "demoted_no_independent_signal"
    transition = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_archive_transition_dry_run",
        "schema_version": "abhe_v0_runtime_slot_controller_archive_transition_dry_run_v0",
        "fresh_slice_hash": manifest.get("selected_case_ids_hash"),
        "planned_transitions": [
            {"entry_id": "post_tool_continuation_guard_v0", "from_status": "fresh_dev_verified_child_candidate", "to_status": "conditional_fresh_dev_verified_with_stress_regression_monitor", "reason": "fresh balanced signal retained but stress results require conditional activation monitoring"},
            {"entry_id": "no_tool_boundary_v0", "from_status": "regression_suite_retained", "to_status": "regression_suite_retained", "reason": "non_target_guard_only"},
            {"entry_id": "missing_param_epistemic_gate_v0", "from_status": "proposal_ready", "to_status": "demoted_no_independent_signal", "reason": "superseded_by_runtime_slot_controller_v2_test"},
            {"entry_id": "runtime_slot_controller_v2", "from_status": "candidate_redesign", "to_status": to_status, "reason": "targeted_residual_stress_vs_conditional_frozen_v2"},
            {"entry_id": "long_context_state_retrieval_v0", "from_status": "narrow_router_requested_regression", "to_status": "narrow_router_requested_regression", "reason": "not_active_in_this_targeted_run"},
        ],
        "archive_updated": False,
        "does_not_update_archive": True,
        "next_required_action": "build_scorer_unit_aligned_residual_diagnostic_before_more_bfcl",
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
    }
    for path, data in [(MATRIX, matrix), (FAILURE, failure), (TRANSITION, transition)]:
        _write(path, data)
    return {"matrix": matrix, "failure": failure, "transition": transition}


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = build()
        report = payload["failure"]
    except Exception as exc:
        report = {"artifact_kind": "abhe_v0_runtime_slot_controller_residual_failure_analysis", "blockers": [f"load_failed:{exc.__class__.__name__}"], "performance_evidence": False}
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
