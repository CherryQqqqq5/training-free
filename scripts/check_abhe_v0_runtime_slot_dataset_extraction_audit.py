#!/usr/bin/env python3
"""Check compact BFCL dataset extraction audit for runtime-slot alignment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_dataset_extraction_audit.json")
EXPECTED_NEXT_ACTION = "review_dataset_extraction_audit_then_request_reduced_batch_retry_approval_if_provider_stable"
FORBIDDEN_TRUE = [
    "authorized",
    "provider_calls_made",
    "bfcl_generate_called",
    "bfcl_evaluate_called",
    "scorer_called",
    "prompt_literal_committed",
    "tool_schema_body_committed",
    "raw_ids_persisted",
    "raw_id_hashes_persisted",
    "raw_run_ids_persisted",
    "raw_run_id_hashes_persisted",
    "model_output_text_committed",
    "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed",
    "gold_expected_committed",
    "scorer_diff_committed",
    "holdout_touched",
    "full_suite_touched",
    "archive_updated",
    "performance_evidence",
]
REQUIRED_CATEGORIES = {
    "multi_turn_base",
    "multi_turn_long_context",
    "multi_turn_miss_func",
    "multi_turn_miss_param",
    "irrelevance",
    "live_irrelevance",
    "live_relevance",
}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_dataset_extraction_audit":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_dataset_extraction_audit_v0":
        blockers.append("schema_version_invalid")
    if data.get("run_scope") != "offline_bfcl_dataset_extraction_audit_only_no_provider_no_bfcl_no_scorer":
        blockers.append("run_scope_invalid")
    if data.get("approval_status") != "pending":
        blockers.append("approval_status_not_pending")
    if data.get("dataset_extraction_audit_ready") is not True:
        blockers.append("dataset_extraction_audit_not_ready")
    if data.get("target_category") != "multi_turn_miss_param":
        blockers.append("target_category_invalid")
    if data.get("next_required_action") != EXPECTED_NEXT_ACTION:
        blockers.append("next_required_action_invalid")
    if data.get("true_per_selected_id_scoring_available_from_dataset_only") is not False:
        blockers.append("true_per_selected_id_scoring_from_dataset_not_false")
    if data.get("true_per_turn_scoring_available_from_dataset_only") is not False:
        blockers.append("true_per_turn_scoring_from_dataset_not_false")
    if data.get("scorer_output_contract_still_required") is not True:
        blockers.append("scorer_output_contract_requirement_missing")
    categories = data.get("category_summaries") if isinstance(data.get("category_summaries"), dict) else {}
    missing = REQUIRED_CATEGORIES - set(categories)
    if missing:
        blockers.append("category_summary_missing:" + ",".join(sorted(missing)))
    for category in REQUIRED_CATEGORIES.intersection(categories):
        summary = categories.get(category)
        if not isinstance(summary, dict):
            blockers.append(f"category_summary_not_object:{category}")
            continue
        if summary.get("category_file_present") is not True:
            blockers.append(f"category_file_not_present:{category}")
        if int(summary.get("row_count") or 0) <= 0:
            blockers.append(f"category_row_count_missing:{category}")
        if int(summary.get("unique_scorer_unit_count") or 0) < int(summary.get("requested_distinct_count") or 0):
            blockers.append(f"category_unique_scorer_units_insufficient:{category}")
        for flag in ("raw_ids_persisted", "raw_id_hashes_persisted", "prompt_literal_committed", "tool_schema_body_committed", "gold_expected_committed", "scorer_diff_committed"):
            if summary.get(flag) is not False:
                blockers.append(f"category_{flag}_not_false:{category}")
    for section_name in ("distinct_manifest_mapping", "reduced_batch_manifest_mapping"):
        section = data.get(section_name) if isinstance(data.get(section_name), dict) else {}
        if section.get("mapping_one_to_one") is not True:
            blockers.append(f"{section_name}_not_one_to_one")
        if int(section.get("selected_case_count") or 0) != int(section.get("mapped_run_id_count") or -1):
            blockers.append(f"{section_name}_mapped_count_mismatch")
        if int(section.get("selected_case_count") or 0) != int(section.get("unique_run_id_count") or -1):
            blockers.append(f"{section_name}_unique_count_mismatch")
        if int(section.get("duplicate_run_id_count") or 0) != 0:
            blockers.append(f"{section_name}_duplicate_count_nonzero")
        if section.get("raw_ids_persisted") is not False or section.get("raw_id_hashes_persisted") is not False:
            blockers.append(f"{section_name}_raw_id_boundary_failed")
    reduced = data.get("reduced_batch_manifest_mapping") if isinstance(data.get("reduced_batch_manifest_mapping"), dict) else {}
    if reduced.get("selected_case_count") != 6:
        blockers.append("reduced_batch_selected_count_not_six")
    if reduced.get("selected_count_by_category") != {"multi_turn_miss_param": 6}:
        blockers.append("reduced_batch_category_count_invalid")
    for field in FORBIDDEN_TRUE:
        if data.get(field) is not False:
            blockers.append(f"{field}_not_false")
    blockers.extend(scan_value(data, label="abhe_v0_runtime_slot_controller_dataset_extraction_audit"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    blockers: List[str] = []
    try:
        data = _load(path)
        blockers.extend(validate(data))
    except Exception as exc:
        data = {}
        blockers.append(f"load_failed:{exc.__class__.__name__}")
    return {
        "report_scope": "abhe_v0_runtime_slot_controller_dataset_extraction_audit_check",
        "artifact_path": str(path),
        "dataset_extraction_audit_check_passed": not blockers,
        "dataset_extraction_audit_ready": data.get("dataset_extraction_audit_ready") is True,
        "target_category": data.get("target_category"),
        "target_dataset_unique_scorer_unit_count": data.get("target_dataset_unique_scorer_unit_count"),
        "target_requested_distinct_count": data.get("target_requested_distinct_count"),
        "reduced_batch_selected_case_count": (data.get("reduced_batch_manifest_mapping") or {}).get("selected_case_count") if isinstance(data.get("reduced_batch_manifest_mapping"), dict) else None,
        "true_per_selected_id_scoring_available_from_dataset_only": data.get("true_per_selected_id_scoring_available_from_dataset_only"),
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
    return 1 if args.strict and not report["dataset_extraction_audit_check_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
