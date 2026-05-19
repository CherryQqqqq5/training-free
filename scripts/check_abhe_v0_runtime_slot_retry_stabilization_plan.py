#!/usr/bin/env python3
"""Check ABHE runtime-slot retry stabilization plan before any further provider run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value
from scripts.check_abhe_v0_runtime_slot_distinct_rerun_failure import check as check_failure

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_retry_stabilization_plan.json")
EXPECTED_HASH = "sha256:9b26ba3d24c54562f6a5058877a24f15d2e4ef71ee9ea781bcae168307f7d14c"
EXPECTED_ACTION = "request_reduced_batch_retry_approval_after_provider_stability_preflight"
FORCED_FALSE = [
    "authorized",
    "execution_started",
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "archive_update_authorized",
    "holdout_authorized",
    "full_suite_authorized",
    "performance_claim_authorized",
    "performance_evidence",
    "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed",
    "gold_expected_committed",
    "scorer_diff_committed",
]
REQUIRED_TRUE = [
    "prior_attempt_failed",
    "provider_stability_required",
    "provider_stability_preflight_required",
    "fresh_run_root_required",
    "reduced_batch_retry_required",
    "scorer_unit_distinct_required",
    "rerun_approval_required",
    "raw_material_absent",
]
REQUIRED_STOP_LOSS = {
    "provider_stability_preflight_failed",
    "fresh_run_root_not_empty",
    "reduced_batch_case_count_exceeded",
    "case_list_hash_mismatch",
    "raw_leakage",
    "bfcl_generate_timeout_or_504",
    "scorer_artifact_schema_failure",
}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_retry_stabilization_plan":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_retry_stabilization_plan_v0":
        blockers.append("schema_version_invalid")
    if data.get("selected_case_ids_hash") != EXPECTED_HASH:
        blockers.append("selected_case_ids_hash_invalid")
    if data.get("prior_failed_arm") != "baseline":
        blockers.append("prior_failed_arm_invalid")
    if data.get("prior_failed_category") != "multi_turn_miss_param":
        blockers.append("prior_failed_category_invalid")
    if data.get("prior_failure_kind") != "bfcl_generate_failed_or_timed_out_after_provider_504s":
        blockers.append("prior_failure_kind_invalid")
    if data.get("proposed_retry_scope") != "approval_required_before_any_provider_call":
        blockers.append("proposed_retry_scope_invalid")
    for key in REQUIRED_TRUE:
        if data.get(key) is not True:
            blockers.append(f"{key}_not_true")
    for key in FORCED_FALSE:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false")
    first_batch = data.get("proposed_first_batch") if isinstance(data.get("proposed_first_batch"), dict) else {}
    if first_batch.get("target_category") != "multi_turn_miss_param":
        blockers.append("first_batch_target_category_invalid")
    max_count = first_batch.get("max_selected_case_count")
    if not isinstance(max_count, int) or max_count <= 0 or max_count > 6:
        blockers.append("first_batch_max_selected_case_count_invalid")
    if first_batch.get("must_use_exact_selected_compact_identifiers_from_existing_distinct_slice") is not True:
        blockers.append("first_batch_exact_identifiers_required_missing")
    if first_batch.get("must_not_expand_case_list") is not True:
        blockers.append("first_batch_must_not_expand_case_list_missing")
    if not REQUIRED_STOP_LOSS.issubset(set(data.get("stop_loss") or [])):
        blockers.append("stop_loss_incomplete")
    failure_report = check_failure(Path(str(data.get("based_on_failure_artifact") or "")))
    if failure_report.get("distinct_rerun_failure_check_passed") is not True:
        blockers.append("source_failure_artifact_check_not_passed")
    if failure_report.get("selected_case_ids_hash") != data.get("selected_case_ids_hash"):
        blockers.append("source_failure_hash_mismatch")
    if data.get("next_required_action") != EXPECTED_ACTION:
        blockers.append("next_required_action_invalid")
    blockers.extend(scan_value(data, label="abhe_v0_runtime_slot_controller_retry_stabilization_plan"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    try:
        data = _load(path)
        blockers = validate(data)
    except Exception as exc:
        data = {}
        blockers = [f"load_failed:{exc.__class__.__name__}"]
    first_batch = data.get("proposed_first_batch") if isinstance(data.get("proposed_first_batch"), dict) else {}
    return {
        "report_scope": "abhe_v0_runtime_slot_controller_retry_stabilization_plan_check",
        "artifact_path": str(path),
        "retry_stabilization_plan_passed": not blockers,
        "provider_stability_required": data.get("provider_stability_required") is True,
        "fresh_run_root_required": data.get("fresh_run_root_required") is True,
        "reduced_batch_retry_required": data.get("reduced_batch_retry_required") is True,
        "max_selected_case_count": first_batch.get("max_selected_case_count"),
        "target_category": first_batch.get("target_category"),
        "authorized": data.get("authorized") is True,
        "performance_evidence": data.get("performance_evidence"),
        "next_required_action": data.get("next_required_action"),
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = check(args.path)
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["retry_stabilization_plan_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
