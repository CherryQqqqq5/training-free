#!/usr/bin/env python3
"""Build compact reduced-batch slice manifest from the pending retry request.

This is BFCL dataset-side extraction only. It does not approve or execute
provider/BFCL/scorer work.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value
import scripts.run_abhe_v0_bfcl_dev_smoke as base

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
REQUEST = ROOT / "abhe_v0_runtime_slot_controller_reduced_batch_retry_request.json"
FULL_PLAN = ROOT / "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json"
OUTPUT = ROOT / "abhe_v0_runtime_slot_controller_reduced_batch_slice_manifest.json"
EXPECTED_PARENT_HASH = "sha256:9b26ba3d24c54562f6a5058877a24f15d2e4ef71ee9ea781bcae168307f7d14c"
EXPECTED_REDUCED_HASH = "sha256:aa341bfc1d78a406f9f3a25967a03d88849dc42fc64e49625eae1993f33ddece"
TARGET_CATEGORY = "multi_turn_miss_param"
EXPECTED_COUNT = 6
NEXT_ACTION = "build_reduced_batch_dry_run_manifest_before_approval_packet"


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _rows(request: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = request.get("selected_compact_case_identifiers")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _dataset_match_summary(dataset_path: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    match_counts: List[Dict[str, Any]] = []
    raw_ids: List[str] = []
    for index, row in enumerate(rows):
        category = str(row.get("bfcl_category"))
        source_path = base._category_file(Path(dataset_path), category)
        source_hash = base._source_file_hash(source_path)
        expected_key = (
            row.get("entry_id"),
            row.get("bfcl_category"),
            row.get("source_file_hash"),
            row.get("case_stable_hash"),
            row.get("case_row_index_hash"),
        )
        count = 0
        for row_index, raw in base._iter_json_rows(source_path):
            compact = base._compact_case(str(row.get("entry_id")), category, source_hash, row_index, raw)
            key = (compact["entry_id"], compact["bfcl_category"], compact["source_file_hash"], compact["case_stable_hash"], compact["case_row_index_hash"])
            if key == expected_key:
                count += 1
                raw_id = raw.get("id") if isinstance(raw, dict) else None
                if isinstance(raw_id, str) and raw_id:
                    raw_ids.append(raw_id)
        match_counts.append({"reduced_index": index, "dataset_match_count": count})
    return {
        "dataset_match_count_by_selected_row": match_counts,
        "mapped_run_id_count": len(raw_ids),
        "unique_run_id_count": len(set(raw_ids)),
        "duplicate_run_id_count": len(raw_ids) - len(set(raw_ids)),
    }


def build() -> Dict[str, Any]:
    request = _load(REQUEST)
    full_plan = _load(FULL_PLAN)
    rows = _rows(request)
    dataset_path = str(full_plan.get("selected_dataset_path") or "")
    dataset_summary = _dataset_match_summary(dataset_path, rows) if dataset_path else {"dataset_match_count_by_selected_row": [], "mapped_run_id_count": 0, "unique_run_id_count": 0, "duplicate_run_id_count": 0}
    manifest: Dict[str, Any] = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_reduced_batch_slice_manifest",
        "schema_version": "abhe_v0_runtime_slot_controller_reduced_batch_slice_manifest_v0",
        "run_scope": "offline_reduced_batch_dataset_extraction_only_no_provider_no_bfcl_no_scorer",
        "based_on_request": str(REQUEST),
        "approval_status": "pending",
        "approval_required": True,
        "authorized": False,
        "fresh_run_root_required": True,
        "one_attempt_only_after_future_approval": True,
        "selected_dataset_path": dataset_path,
        "parent_selected_case_ids_hash": request.get("parent_selected_case_ids_hash"),
        "selected_case_ids_hash": request.get("reduced_batch_case_ids_hash"),
        "selected_case_count": len(rows),
        "max_selected_case_count": EXPECTED_COUNT,
        "target_category": TARGET_CATEGORY,
        "case_count_by_category": {TARGET_CATEGORY: len([row for row in rows if row.get("bfcl_category") == TARGET_CATEGORY])},
        "selected_compact_case_identifiers": rows,
        "dataset_match_count_by_selected_row": dataset_summary["dataset_match_count_by_selected_row"],
        "mapped_run_id_count": dataset_summary["mapped_run_id_count"],
        "unique_run_id_count": dataset_summary["unique_run_id_count"],
        "duplicate_run_id_count": dataset_summary["duplicate_run_id_count"],
        "raw_run_ids_persisted": False,
        "raw_run_id_hashes_persisted": False,
        "reduced_batch_manifest_ready": True,
        "must_use_exact_selected_compact_identifiers_from_existing_distinct_slice": True,
        "must_not_expand_case_list": True,
        "scorer_unit_distinct_required": True,
        "provider_calls_authorized": False,
        "bfcl_generate_authorized": False,
        "bfcl_evaluate_authorized": False,
        "scorer_authorized": False,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "execution_started": False,
        "archive_update_authorized": False,
        "archive_updated": False,
        "holdout_authorized": False,
        "holdout_touched": False,
        "full_suite_authorized": False,
        "full_suite_touched": False,
        "performance_claim_authorized": False,
        "performance_evidence": False,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "next_required_action": NEXT_ACTION,
    }
    blockers: List[str] = []
    if request.get("authorized") is not False:
        blockers.append("request_authorized_unexpected")
    if request.get("approval_status") != "pending":
        blockers.append("request_not_pending")
    if manifest["parent_selected_case_ids_hash"] != EXPECTED_PARENT_HASH:
        blockers.append("parent_selected_case_ids_hash_invalid")
    if manifest["selected_case_ids_hash"] != EXPECTED_REDUCED_HASH:
        blockers.append("selected_case_ids_hash_invalid")
    if manifest["selected_case_count"] != EXPECTED_COUNT:
        blockers.append("selected_case_count_invalid")
    if manifest["case_count_by_category"].get(TARGET_CATEGORY) != EXPECTED_COUNT:
        blockers.append("target_category_count_invalid")
    if any(row.get("dataset_match_count") != 1 for row in manifest["dataset_match_count_by_selected_row"]):
        blockers.append("dataset_match_count_not_one_to_one")
    if manifest["mapped_run_id_count"] != EXPECTED_COUNT or manifest["unique_run_id_count"] != EXPECTED_COUNT or manifest["duplicate_run_id_count"] != 0:
        blockers.append("mapped_run_id_count_invalid")
    manifest["blockers"] = sorted(set(blockers + scan_value(manifest, label="abhe_v0_runtime_slot_controller_reduced_batch_slice_manifest")))
    return manifest


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build()
        if args.write:
            _write(OUTPUT, report)
    except Exception as exc:
        report = {"artifact_kind": "abhe_v0_runtime_slot_controller_reduced_batch_slice_manifest", "performance_evidence": False, "blockers": ["load_failed:%s" % exc.__class__.__name__]}
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
