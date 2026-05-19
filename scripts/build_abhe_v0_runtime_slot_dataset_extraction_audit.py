#!/usr/bin/env python3
"""Build a compact BFCL dataset extraction audit for runtime-slot scorer alignment.

This is an offline dataset-side audit only. It may inspect installed BFCL JSON
rows locally, but it persists only compact counts, field-shape summaries, and
manifest mapping status. It does not call provider, BFCL generate/evaluate, or
scorer, and it does not persist raw BFCL ids, id hashes, prompts, tool schemas,
gold, scorer diffs, provider payloads, or model outputs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import scripts.run_abhe_v0_bfcl_dev_smoke as base
from scripts.build_abhe_v0_bfcl_fresh_dev_slice import _category_file, _iter_json_rows
from scripts.build_abhe_v0_runtime_slot_controller_residual_stress import DEFAULT_DATASET, STRESS_COUNTS

AUDIT_COUNTS = dict(STRESS_COUNTS)
AUDIT_COUNTS.setdefault("live_relevance", 4)
from scripts.check_abhe_no_leakage_boundary import scan_value
from scripts.run_abhe_v0_runtime_slot_controller_residual_dev_smoke import _configure

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
OUTPUT = ROOT / "abhe_v0_runtime_slot_controller_dataset_extraction_audit.json"
DISTINCT_MANIFEST = ROOT / "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json"
REDUCED_MANIFEST = ROOT / "abhe_v0_runtime_slot_controller_reduced_batch_slice_manifest.json"
TARGET_CATEGORY = "multi_turn_miss_param"
NEXT_ACTION = "review_dataset_extraction_audit_then_request_reduced_batch_retry_approval_if_provider_stable"
FALSE_FIELDS = [
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


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _shape_counts(rows: List[Tuple[int, Any]]) -> Dict[str, Any]:
    id_values: List[str] = []
    question_turn_lengths: List[int] = []
    path_lengths: List[int] = []
    function_counts: List[int] = []
    initial_config_present = 0
    involved_classes_present = 0
    excluded_function_present = 0
    unsupported_rows = 0
    for _, raw in rows:
        if not isinstance(raw, dict):
            unsupported_rows += 1
            continue
        raw_id = raw.get("id")
        if isinstance(raw_id, str) and raw_id:
            id_values.append(raw_id)
        question = raw.get("question")
        if isinstance(question, list):
            question_turn_lengths.append(len(question))
        path = raw.get("path")
        if isinstance(path, list):
            path_lengths.append(len(path))
        function = raw.get("function")
        if isinstance(function, list):
            function_counts.append(len(function))
        if isinstance(raw.get("initial_config"), dict):
            initial_config_present += 1
        if isinstance(raw.get("involved_classes"), list):
            involved_classes_present += 1
        if isinstance(raw.get("excluded_function"), list):
            excluded_function_present += 1
    unique_ids = len(set(id_values))
    duplicate_ids = len(id_values) - unique_ids
    return {
        "row_count": len(rows),
        "unsupported_row_count": unsupported_rows,
        "raw_id_present_count": len(id_values),
        "unique_scorer_unit_count": unique_ids,
        "duplicate_scorer_unit_count": duplicate_ids,
        "question_list_row_count": len(question_turn_lengths),
        "question_turn_count_min": min(question_turn_lengths) if question_turn_lengths else 0,
        "question_turn_count_max": max(question_turn_lengths) if question_turn_lengths else 0,
        "path_list_row_count": len(path_lengths),
        "path_length_min": min(path_lengths) if path_lengths else 0,
        "path_length_max": max(path_lengths) if path_lengths else 0,
        "function_list_row_count": len(function_counts),
        "function_count_min": min(function_counts) if function_counts else 0,
        "function_count_max": max(function_counts) if function_counts else 0,
        "initial_config_present_count": initial_config_present,
        "involved_classes_present_count": involved_classes_present,
        "excluded_function_present_count": excluded_function_present,
        "raw_ids_persisted": False,
        "raw_id_hashes_persisted": False,
        "prompt_literal_committed": False,
        "tool_schema_body_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
    }


def _manifest_mapping_summary(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"manifest_path": str(path), "manifest_present": False, "mapping_ready": False, "blockers": ["manifest_missing"]}
    blockers: List[str] = []
    manifest = _load(path)
    selected_count = int(manifest.get("selected_case_count") or 0)
    selected_rows = manifest.get("selected_compact_case_identifiers") if isinstance(manifest.get("selected_compact_case_identifiers"), list) else []
    _configure(path)
    ids_by_category, _, _ = base._selected_raw_ids()
    mapped_by_category = {category: len(ids) for category, ids in sorted(ids_by_category.items())}
    unique_by_category = {category: len(set(ids)) for category, ids in sorted(ids_by_category.items())}
    duplicate_by_category = {category: mapped_by_category[category] - unique_by_category[category] for category in mapped_by_category}
    selected_by_category: Dict[str, int] = {}
    for row in selected_rows:
        if isinstance(row, dict):
            category = str(row.get("bfcl_category"))
            selected_by_category[category] = selected_by_category.get(category, 0) + 1
    for category, count in sorted(selected_by_category.items()):
        if mapped_by_category.get(category, 0) != count:
            blockers.append(f"mapped_count_mismatch:{category}")
        if unique_by_category.get(category, 0) != count:
            blockers.append(f"unique_count_mismatch:{category}")
        if duplicate_by_category.get(category, 0) != 0:
            blockers.append(f"duplicate_scorer_unit_detected:{category}")
    mapped_total = sum(mapped_by_category.values())
    unique_total = sum(unique_by_category.values())
    if mapped_total != selected_count:
        blockers.append("mapped_total_mismatch")
    if unique_total != selected_count:
        blockers.append("unique_total_mismatch")
    return {
        "manifest_path": str(path),
        "manifest_present": True,
        "artifact_kind": manifest.get("artifact_kind"),
        "selected_case_ids_hash": manifest.get("selected_case_ids_hash"),
        "selected_case_count": selected_count,
        "selected_count_by_category": selected_by_category,
        "mapped_run_id_count": mapped_total,
        "unique_run_id_count": unique_total,
        "duplicate_run_id_count": mapped_total - unique_total,
        "mapped_count_by_category": mapped_by_category,
        "unique_count_by_category": unique_by_category,
        "duplicate_count_by_category": duplicate_by_category,
        "mapping_one_to_one": not blockers,
        "raw_ids_persisted": False,
        "raw_id_hashes_persisted": False,
        "blockers": blockers,
    }


def build(dataset_path: Optional[Path] = None) -> Dict[str, Any]:
    dataset_path = dataset_path or DEFAULT_DATASET
    blockers: List[str] = []
    category_summaries: Dict[str, Any] = {}
    if not dataset_path.exists():
        blockers.append("bfcl_dataset_path_missing")
    else:
        for category, requested_count in sorted(AUDIT_COUNTS.items()):
            path = _category_file(dataset_path, category)
            if not path.exists():
                category_summaries[category] = {"category_file_present": False, "requested_distinct_count": requested_count}
                blockers.append(f"bfcl_category_file_missing:{category}")
                continue
            rows = _iter_json_rows(path)
            summary = _shape_counts(rows)
            summary.update({
                "category_file_present": True,
                "requested_distinct_count": requested_count,
                "distinct_scorer_units_sufficient_for_request": summary["unique_scorer_unit_count"] >= requested_count,
            })
            if summary["unique_scorer_unit_count"] < requested_count:
                blockers.append(f"insufficient_dataset_scorer_units:{category}")
            category_summaries[category] = summary
    distinct_mapping = _manifest_mapping_summary(DISTINCT_MANIFEST)
    reduced_mapping = _manifest_mapping_summary(REDUCED_MANIFEST)
    if distinct_mapping.get("mapping_one_to_one") is not True:
        blockers.append("distinct_manifest_mapping_not_one_to_one")
    if reduced_mapping.get("mapping_one_to_one") is not True:
        blockers.append("reduced_manifest_mapping_not_one_to_one")
    target_summary = category_summaries.get(TARGET_CATEGORY, {})
    report: Dict[str, Any] = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_dataset_extraction_audit",
        "schema_version": "abhe_v0_runtime_slot_controller_dataset_extraction_audit_v0",
        "run_scope": "offline_bfcl_dataset_extraction_audit_only_no_provider_no_bfcl_no_scorer",
        "approval_status": "pending",
        "authorized": False,
        "dataset_extraction_audit_ready": not blockers,
        "selected_dataset_path": str(dataset_path),
        "target_category": TARGET_CATEGORY,
        "category_summaries": category_summaries,
        "distinct_manifest_mapping": distinct_mapping,
        "reduced_batch_manifest_mapping": reduced_mapping,
        "target_dataset_unique_scorer_unit_count": target_summary.get("unique_scorer_unit_count"),
        "target_requested_distinct_count": target_summary.get("requested_distinct_count"),
        "target_distinct_scorer_units_sufficient_for_request": target_summary.get("distinct_scorer_units_sufficient_for_request") is True,
        "dataset_side_distinct_scorer_units_available": not blockers,
        "true_per_selected_id_scoring_available_from_dataset_only": False,
        "true_per_turn_scoring_available_from_dataset_only": False,
        "scorer_output_contract_still_required": True,
        "next_required_action": NEXT_ACTION if not blockers else "fix_dataset_extraction_audit_blockers_before_any_bfcl_retry",
        "raw_material_absent": True,
        "raw_ids_persisted": False,
        "raw_id_hashes_persisted": False,
        "raw_run_ids_persisted": False,
        "raw_run_id_hashes_persisted": False,
        "prompt_literal_committed": False,
        "tool_schema_body_committed": False,
        "model_output_text_committed": False,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "performance_evidence": False,
        "blockers": blockers,
    }
    for field in FALSE_FIELDS:
        if report.get(field) is not False:
            report["blockers"].append(f"{field}_not_false")
    leakage = scan_value(report, label="abhe_v0_runtime_slot_controller_dataset_extraction_audit")
    if leakage:
        report["blockers"] = sorted(set(report["blockers"] + leakage))
        report["dataset_extraction_audit_ready"] = False
    return report


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=None)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build(args.dataset_path)
        if args.write:
            _write(OUTPUT, report)
    except Exception as exc:
        report = {
            "artifact_kind": "abhe_v0_runtime_slot_controller_dataset_extraction_audit",
            "dataset_extraction_audit_ready": False,
            "blockers": [f"build_failed:{exc.__class__.__name__}"],
            "performance_evidence": False,
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
