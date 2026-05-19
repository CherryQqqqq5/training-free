#!/usr/bin/env python3
"""Check reduced-batch dataset alignment ledger for ABHE runtime-slot retry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_reduced_batch_alignment_ledger.json")
EXPECTED_NEXT_ACTION = "review_reduced_batch_alignment_ledger_then_request_retry_approval_if_provider_stable"
PARENT_HASH = "sha256:9b26ba3d24c54562f6a5058877a24f15d2e4ef71ee9ea781bcae168307f7d14c"
REDUCED_HASH = "sha256:aa341bfc1d78a406f9f3a25967a03d88849dc42fc64e49625eae1993f33ddece"
FORBIDDEN_TRUE = [
    "authorized",
    "approved_packet_present",
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
FORBIDDEN_ROW_KEYS = {"case_identifier_hash", "scorer_unit_hash", "raw_id", "raw_run_id", "run_id_hash"}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_reduced_batch_alignment_ledger":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_reduced_batch_alignment_ledger_v0":
        blockers.append("schema_version_invalid")
    if data.get("run_scope") != "offline_dataset_side_scorer_unit_alignment_only_no_provider_no_bfcl_no_scorer":
        blockers.append("run_scope_invalid")
    if data.get("approval_status") != "pending":
        blockers.append("approval_status_not_pending")
    if data.get("alignment_ledger_ready") is not True:
        blockers.append("alignment_ledger_not_ready")
    if data.get("parent_selected_case_ids_hash") != PARENT_HASH:
        blockers.append("parent_hash_mismatch")
    if data.get("selected_case_ids_hash") != REDUCED_HASH or data.get("recomputed_selected_case_ids_hash") != REDUCED_HASH:
        blockers.append("selected_case_ids_hash_mismatch")
    if data.get("target_category") != "multi_turn_miss_param":
        blockers.append("target_category_invalid")
    if data.get("selected_case_count") != 6:
        blockers.append("selected_case_count_not_six")
    if data.get("mapped_run_id_count") != 6 or data.get("unique_run_id_count") != 6 or data.get("duplicate_run_id_count") != 0:
        blockers.append("run_id_count_summary_invalid")
    if data.get("run_id_group_size_histogram") != {"1": 6}:
        blockers.append("run_id_group_histogram_invalid")
    if data.get("per_selected_valid_labels_available") is not False or data.get("per_turn_valid_labels_available") is not False:
        blockers.append("valid_labels_unexpectedly_available")
    if data.get("true_per_selected_id_scoring_available_from_dataset_only") is not False:
        blockers.append("true_per_selected_scoring_from_dataset_not_false")
    if data.get("true_per_turn_scoring_available_from_dataset_only") is not False:
        blockers.append("true_per_turn_scoring_from_dataset_not_false")
    if data.get("scorer_output_contract_still_required") is not True:
        blockers.append("scorer_output_contract_requirement_missing")
    if data.get("next_required_action") != EXPECTED_NEXT_ACTION:
        blockers.append("next_required_action_invalid")
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    if len(rows) != 6:
        blockers.append("row_count_not_six")
    seen_indices = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            blockers.append(f"row_not_object:{index}")
            continue
        forbidden = FORBIDDEN_ROW_KEYS.intersection(row)
        if forbidden:
            blockers.append(f"row_forbidden_keys:{index}:{','.join(sorted(forbidden))}")
        seen_indices.add(row.get("selected_index"))
        if row.get("bfcl_category") != "multi_turn_miss_param":
            blockers.append(f"row_target_category_invalid:{index}")
        if row.get("dataset_match_count") != 1:
            blockers.append(f"row_dataset_match_count_not_one:{index}")
        if row.get("scorer_unit_distinct_proxy") is not True:
            blockers.append(f"row_scorer_unit_distinct_proxy_not_true:{index}")
        if row.get("per_selected_valid_label_available") is not False or row.get("per_turn_valid_labels_available") is not False:
            blockers.append(f"row_valid_labels_unexpected:{index}")
        if row.get("raw_material_absent") is not True:
            blockers.append(f"row_raw_material_absent_not_true:{index}")
        if row.get("raw_ids_persisted") is not False or row.get("raw_id_hashes_persisted") is not False:
            blockers.append(f"row_raw_id_boundary_failed:{index}")
    if seen_indices != set(range(6)):
        blockers.append("selected_indices_invalid")
    for field in FORBIDDEN_TRUE:
        if data.get(field) is not False:
            blockers.append(f"{field}_not_false")
    blockers.extend(scan_value(data, label="abhe_v0_runtime_slot_controller_reduced_batch_alignment_ledger"))
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
        "report_scope": "abhe_v0_runtime_slot_controller_reduced_batch_alignment_ledger_check",
        "artifact_path": str(path),
        "alignment_ledger_check_passed": not blockers,
        "alignment_ledger_ready": data.get("alignment_ledger_ready") is True,
        "selected_case_ids_hash": data.get("selected_case_ids_hash"),
        "selected_case_count": data.get("selected_case_count"),
        "mapped_run_id_count": data.get("mapped_run_id_count"),
        "unique_run_id_count": data.get("unique_run_id_count"),
        "duplicate_run_id_count": data.get("duplicate_run_id_count"),
        "per_selected_valid_labels_available": data.get("per_selected_valid_labels_available"),
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
    return 1 if args.strict and not report["alignment_ledger_check_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
