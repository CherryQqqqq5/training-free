#!/usr/bin/env python3
"""Check compact score-output contract gap audit for ABHE runtime-slot reruns."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_score_output_contract_gap_audit.json")
NEXT_ACTION = "instrument_runner_scorer_to_emit_compact_alignment_sidecar_before_more_bfcl"
FALSE_FIELDS = [
    "provider_calls_made",
    "bfcl_generate_called",
    "bfcl_evaluate_called",
    "scorer_called",
    "score_rows_committed",
    "provider_payload_committed",
    "bfcl_result_tree_committed",
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


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_score_output_contract_gap_audit":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_score_output_contract_gap_audit_v0":
        blockers.append("schema_version_invalid")
    if data.get("raw_material_absent") is not True:
        blockers.append("raw_material_absent_not_true")
    if data.get("next_required_action") != NEXT_ACTION:
        blockers.append("next_required_action_invalid")
    for key in FALSE_FIELDS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false")
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    if summary.get("contract_gap_confirmed") is not True:
        blockers.append("contract_gap_not_confirmed")
    if summary.get("per_selected_labels_recoverable") is not False:
        blockers.append("per_selected_labels_must_not_be_recoverable")
    if summary.get("per_turn_labels_recoverable") is not False:
        blockers.append("per_turn_labels_must_not_be_recoverable")
    if summary.get("more_bfcl_before_contract_fix_recommended") is not False:
        blockers.append("more_bfcl_before_contract_fix_not_blocked")
    if int(summary.get("target_selected_compact_count") or 0) <= 0:
        blockers.append("target_selected_compact_count_missing")
    if int(summary.get("target_score_total_count") or 0) <= 0:
        blockers.append("target_score_total_count_missing")
    if float(summary.get("target_selected_to_score_total_factor") or 0) <= 1.0:
        blockers.append("target_contract_gap_factor_not_greater_than_one")
    requirements = data.get("contract_requirements_for_next_rerun") if isinstance(data.get("contract_requirements_for_next_rerun"), dict) else {}
    for key in [
        "score_output_must_emit_selected_identifier_hash",
        "score_output_must_emit_selected_index",
        "score_output_must_emit_scorer_unit_hash",
        "score_output_must_emit_valid_label_per_selected_or_explicit_aggregation_map",
        "multi_turn_output_must_emit_turn_index_and_verdict_for_true_per_turn_claim",
        "sidecar_must_be_compact_only",
        "sidecar_must_not_include_prompt_or_answer_material",
    ]:
        if requirements.get(key) is not True:
            blockers.append(f"contract_requirement_missing:{key}")
    rows = data.get("arm_category_rows") if isinstance(data.get("arm_category_rows"), list) else []
    if not rows:
        blockers.append("arm_category_rows_missing")
    for row in rows:
        if not isinstance(row, dict):
            blockers.append("arm_category_row_not_object")
            continue
        if row.get("raw_material_absent") is not True:
            blockers.append("row_raw_material_absent_not_true")
        if row.get("per_turn_label_recoverable") is not False:
            blockers.append("row_per_turn_label_recoverable_not_false")
        if row.get("bfcl_category") == "multi_turn_miss_param" and row.get("per_selected_label_recoverable") is not False:
            blockers.append("target_row_per_selected_label_recoverable_not_false")
        missing = row.get("missing_contract_fields") if isinstance(row.get("missing_contract_fields"), list) else []
        if "selected_case_identifier_hash" not in missing:
            blockers.append("row_missing_selected_case_identifier_hash_contract")
        if "per_turn_valid_label" not in missing:
            blockers.append("row_missing_per_turn_valid_label_contract")
    blockers.extend(str(item) for item in data.get("blockers") or [])
    blockers.extend(scan_value(data, label="abhe_v0_runtime_slot_controller_score_output_contract_gap_audit"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    try:
        data = _load(path)
        blockers = validate(data)
    except Exception as exc:
        data = {}
        blockers = [f"load_failed:{exc.__class__.__name__}"]
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return {
        "report_scope": "abhe_v0_runtime_slot_controller_score_output_contract_gap_audit_check",
        "artifact_path": str(path),
        "score_output_contract_gap_audit_passed": not blockers,
        "blockers": blockers,
        "contract_gap_confirmed": summary.get("contract_gap_confirmed"),
        "target_selected_compact_count": summary.get("target_selected_compact_count"),
        "target_score_total_count": summary.get("target_score_total_count"),
        "target_result_record_count": summary.get("target_result_record_count"),
        "target_selected_to_score_total_factor": summary.get("target_selected_to_score_total_factor"),
        "per_selected_labels_recoverable": summary.get("per_selected_labels_recoverable"),
        "per_turn_labels_recoverable": summary.get("per_turn_labels_recoverable"),
        "next_required_action": data.get("next_required_action"),
        "performance_evidence": data.get("performance_evidence", False),
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = check(args.path)
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["score_output_contract_gap_audit_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
