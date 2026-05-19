#!/usr/bin/env python3
"""Check compact reduced-batch slice manifest stays fail-closed."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value
from scripts.check_abhe_v0_runtime_slot_reduced_batch_retry_request import check as check_request
from scripts.build_abhe_v0_bfcl_fresh_dev_slice import selected_case_ids_hash

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_reduced_batch_slice_manifest.json")
EXPECTED_PARENT_HASH = "sha256:9b26ba3d24c54562f6a5058877a24f15d2e4ef71ee9ea781bcae168307f7d14c"
EXPECTED_REDUCED_HASH = "sha256:aa341bfc1d78a406f9f3a25967a03d88849dc42fc64e49625eae1993f33ddece"
TARGET_CATEGORY = "multi_turn_miss_param"
EXPECTED_COUNT = 6
EXPECTED_ACTION = "build_reduced_batch_dry_run_manifest_before_approval_packet"
FORCED_FALSE = [
    "authorized", "provider_calls_authorized", "bfcl_generate_authorized", "bfcl_evaluate_authorized", "scorer_authorized",
    "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called", "scorer_called", "execution_started",
    "archive_update_authorized", "archive_updated", "holdout_authorized", "holdout_touched", "full_suite_authorized",
    "full_suite_touched", "performance_claim_authorized", "performance_evidence", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed", "scorer_diff_committed",
]
REQUIRED_TRUE = [
    "approval_required", "fresh_run_root_required", "one_attempt_only_after_future_approval", "reduced_batch_manifest_ready",
    "must_use_exact_selected_compact_identifiers_from_existing_distinct_slice", "must_not_expand_case_list",
    "scorer_unit_distinct_required", "raw_material_absent",
]


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_reduced_batch_slice_manifest":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_reduced_batch_slice_manifest_v0":
        blockers.append("schema_version_invalid")
    if data.get("run_scope") != "offline_reduced_batch_dataset_extraction_only_no_provider_no_bfcl_no_scorer":
        blockers.append("run_scope_invalid")
    if data.get("approval_status") != "pending":
        blockers.append("approval_status_not_pending")
    if data.get("parent_selected_case_ids_hash") != EXPECTED_PARENT_HASH:
        blockers.append("parent_selected_case_ids_hash_invalid")
    if data.get("selected_case_ids_hash") != EXPECTED_REDUCED_HASH:
        blockers.append("selected_case_ids_hash_invalid")
    if data.get("selected_case_count") != EXPECTED_COUNT or data.get("max_selected_case_count") != EXPECTED_COUNT:
        blockers.append("selected_case_count_invalid")
    if data.get("target_category") != TARGET_CATEGORY:
        blockers.append("target_category_invalid")
    if (data.get("case_count_by_category") or {}).get(TARGET_CATEGORY) != EXPECTED_COUNT:
        blockers.append("case_count_by_category_invalid")
    rows = data.get("selected_compact_case_identifiers") if isinstance(data.get("selected_compact_case_identifiers"), list) else []
    if len(rows) != EXPECTED_COUNT:
        blockers.append("selected_identifier_count_invalid")
    if rows and selected_case_ids_hash(rows) != data.get("selected_case_ids_hash"):
        blockers.append("selected_case_ids_hash_recomputed_mismatch")
    seen = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            blockers.append("selected_identifier_not_object:%d" % index)
            continue
        if row.get("bfcl_category") != TARGET_CATEGORY:
            blockers.append("selected_identifier_category_invalid:%d" % index)
        if row.get("raw_material_absent") is not True:
            blockers.append("selected_identifier_raw_material_absent_not_true:%d" % index)
        if row.get("scorer_unit_distinct") is not True:
            blockers.append("selected_identifier_not_scorer_unit_distinct:%d" % index)
        key = row.get("case_stable_hash")
        if not isinstance(key, str) or not key.startswith("sha256:"):
            blockers.append("selected_identifier_case_stable_hash_invalid:%d" % index)
        elif key in seen:
            blockers.append("selected_identifier_duplicate_case_stable_hash:%d" % index)
        else:
            seen.add(key)
    match_rows = data.get("dataset_match_count_by_selected_row") if isinstance(data.get("dataset_match_count_by_selected_row"), list) else []
    if len(match_rows) != EXPECTED_COUNT or any(not isinstance(row, dict) or row.get("dataset_match_count") != 1 for row in match_rows):
        blockers.append("dataset_match_count_by_selected_row_invalid")
    if data.get("mapped_run_id_count") != EXPECTED_COUNT or data.get("unique_run_id_count") != EXPECTED_COUNT or data.get("duplicate_run_id_count") != 0:
        blockers.append("mapped_run_id_count_invalid")
    for key in REQUIRED_TRUE:
        if data.get(key) is not True:
            blockers.append("%s_not_true" % key)
    for key in FORCED_FALSE:
        if data.get(key) is not False:
            blockers.append("%s_not_false" % key)
    if data.get("next_required_action") != EXPECTED_ACTION:
        blockers.append("next_required_action_invalid")
    request_report = check_request()
    if request_report.get("reduced_batch_retry_request_passed") is not True:
        blockers.append("reduced_batch_retry_request_not_passed")
    if request_report.get("reduced_batch_case_ids_hash") != data.get("selected_case_ids_hash"):
        blockers.append("request_hash_mismatch")
    if request_report.get("selected_case_count") != data.get("selected_case_count"):
        blockers.append("request_case_count_mismatch")
    blockers.extend(str(item) for item in data.get("blockers") or [])
    blockers.extend(scan_value(data, label="abhe_v0_runtime_slot_controller_reduced_batch_slice_manifest"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    try:
        data = _load(path)
        blockers = validate(data)
    except Exception as exc:
        data = {}
        blockers = ["load_failed:%s" % exc.__class__.__name__]
    return {
        "report_scope": "abhe_v0_runtime_slot_controller_reduced_batch_slice_manifest_check",
        "artifact_path": str(path),
        "reduced_batch_slice_manifest_passed": not blockers,
        "authorized": data.get("authorized") is True,
        "parent_selected_case_ids_hash": data.get("parent_selected_case_ids_hash"),
        "selected_case_ids_hash": data.get("selected_case_ids_hash"),
        "selected_case_count": data.get("selected_case_count"),
        "target_category": data.get("target_category"),
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
    return 1 if args.strict and not report["reduced_batch_slice_manifest_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
