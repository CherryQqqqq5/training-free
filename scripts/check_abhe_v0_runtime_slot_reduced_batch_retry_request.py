#!/usr/bin/env python3
"""Check pending reduced-batch retry request for ABHE runtime-slot work."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value
from scripts.build_abhe_v0_bfcl_fresh_dev_slice import selected_case_ids_hash
from scripts.check_abhe_v0_runtime_slot_retry_stabilization_plan import check as check_stabilization

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_reduced_batch_retry_request.json")
PARENT_HASH = "sha256:9b26ba3d24c54562f6a5058877a24f15d2e4ef71ee9ea781bcae168307f7d14c"
EXPECTED_ACTION = "request_reduced_batch_retry_approval_packet_with_fresh_run_root"
FORCED_FALSE = [
    "authorized",
    "evaluate_after_generate_authorized",
    "scorer_after_generate_authorized",
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
    "approval_required",
    "bounded_dev_smoke_only",
    "must_use_exact_selected_compact_identifiers_from_existing_distinct_slice",
    "must_not_expand_case_list",
    "fresh_run_root_required",
    "provider_stability_preflight_required",
    "one_attempt_only",
    "future_execute_scope_requires_new_approval_packet",
    "raw_material_absent",
]


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_reduced_batch_retry_request":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_reduced_batch_retry_request_v0":
        blockers.append("schema_version_invalid")
    if data.get("approval_status") != "pending":
        blockers.append("approval_status_not_pending")
    if data.get("scope") != "mapping_fixed_reduced_batch_provider_stability_retry_review_only":
        blockers.append("scope_invalid")
    if data.get("parent_selected_case_ids_hash") != PARENT_HASH:
        blockers.append("parent_selected_case_ids_hash_invalid")
    if not isinstance(data.get("reduced_batch_case_ids_hash"), str) or not data.get("reduced_batch_case_ids_hash", "").startswith("sha256:"):
        blockers.append("reduced_batch_case_ids_hash_invalid")
    if data.get("target_category") != "multi_turn_miss_param":
        blockers.append("target_category_invalid")
    if data.get("selected_case_count") != 6 or data.get("max_selected_case_count") != 6:
        blockers.append("selected_case_count_invalid")
    if data.get("requested_arms") != ["baseline"]:
        blockers.append("requested_arms_invalid")
    rows = data.get("selected_compact_case_identifiers") if isinstance(data.get("selected_compact_case_identifiers"), list) else []
    if len(rows) != 6:
        blockers.append("selected_identifier_count_invalid")
    if rows and selected_case_ids_hash(rows) != data.get("reduced_batch_case_ids_hash"):
        blockers.append("reduced_batch_case_ids_hash_recomputed_mismatch")
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            blockers.append(f"selected_identifier_not_object:{index}")
            continue
        if row.get("bfcl_category") != "multi_turn_miss_param":
            blockers.append(f"selected_identifier_category_invalid:{index}")
        if row.get("raw_material_absent") is not True:
            blockers.append(f"selected_identifier_raw_material_absent_not_true:{index}")
    for key in REQUIRED_TRUE:
        if data.get(key) is not True:
            blockers.append(f"{key}_not_true")
    for key in FORCED_FALSE:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false")
    stabilization = check_stabilization(Path(str(data.get("based_on_stabilization_plan") or "")))
    if stabilization.get("retry_stabilization_plan_passed") is not True:
        blockers.append("stabilization_plan_not_passed")
    if stabilization.get("max_selected_case_count") != data.get("max_selected_case_count"):
        blockers.append("stabilization_case_count_mismatch")
    if data.get("next_required_action") != EXPECTED_ACTION:
        blockers.append("next_required_action_invalid")
    blockers.extend(str(item) for item in data.get("blockers") or [])
    blockers.extend(scan_value(data, label="abhe_v0_runtime_slot_controller_reduced_batch_retry_request"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    try:
        data = _load(path)
        blockers = validate(data)
    except Exception as exc:
        data = {}
        blockers = [f"load_failed:{exc.__class__.__name__}"]
    return {
        "report_scope": "abhe_v0_runtime_slot_controller_reduced_batch_retry_request_check",
        "artifact_path": str(path),
        "reduced_batch_retry_request_passed": not blockers,
        "authorized": data.get("authorized") is True,
        "parent_selected_case_ids_hash": data.get("parent_selected_case_ids_hash"),
        "reduced_batch_case_ids_hash": data.get("reduced_batch_case_ids_hash"),
        "selected_case_count": data.get("selected_case_count"),
        "target_category": data.get("target_category"),
        "requested_arms": data.get("requested_arms"),
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
    return 1 if args.strict and not report["reduced_batch_retry_request_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
