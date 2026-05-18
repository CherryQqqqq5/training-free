#!/usr/bin/env python3
"""Check compact per-selected-id matrix for ABHE runtime slot residual runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_per_selected_id_matrix.json")
FALSE_FIELDS = [
    "prompt_literal_committed",
    "argument_values_committed",
    "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed",
    "gold_expected_committed",
    "scorer_diff_committed",
    "provider_calls_made",
    "bfcl_generate_called",
    "bfcl_evaluate_called",
    "scorer_called",
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
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_per_selected_id_matrix":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_per_selected_id_matrix_v0":
        blockers.append("schema_version_invalid")
    if data.get("raw_material_absent") is not True:
        blockers.append("raw_material_absent_not_true")
    for key in FALSE_FIELDS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false")
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    if int(summary.get("selected_row_count") or 0) <= 0:
        blockers.append("selected_row_count_missing")
    if int(summary.get("per_turn_shape_row_count") or 0) <= 0:
        blockers.append("per_turn_shape_row_count_missing")
    if int(summary.get("target_unique_scorer_unit_count") or 0) <= 0:
        blockers.append("target_unique_scorer_unit_count_missing")
    if summary.get("target_per_selected_id_pass_available") is not False:
        blockers.append("target_per_selected_pass_not_marked_unavailable")
    if summary.get("target_pass_is_scorer_unit_inherited") is not True:
        blockers.append("target_pass_inheritance_not_declared")
    if summary.get("more_bfcl_before_alignment_recommended") is not False:
        blockers.append("more_bfcl_before_alignment_not_blocked")
    selected_rows = data.get("selected_id_rows") if isinstance(data.get("selected_id_rows"), list) else []
    if not selected_rows:
        blockers.append("selected_id_rows_missing")
    for row in selected_rows:
        if not isinstance(row, dict):
            blockers.append("selected_row_not_object")
            continue
        if row.get("raw_material_absent") is not True:
            blockers.append("selected_row_raw_material_absent_not_true")
        if row.get("per_selected_pass_available") is not False:
            blockers.append("selected_row_per_selected_pass_not_false")
        if row.get("pass_inherited_from_scorer_unit") is not True:
            blockers.append("selected_row_pass_inheritance_not_true")
        if row.get("turn_index_mapping_available") is not False:
            blockers.append("selected_row_turn_mapping_not_false")
    for row in data.get("per_turn_shape_rows") or []:
        if not isinstance(row, dict):
            blockers.append("turn_row_not_object")
            continue
        if row.get("raw_material_absent") is not True:
            blockers.append("turn_row_raw_material_absent_not_true")
        if row.get("per_turn_pass_available") is not False:
            blockers.append("turn_row_per_turn_pass_not_false")
    for item in data.get("blockers") or []:
        blockers.append(str(item))
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
        "report_scope": "abhe_v0_runtime_slot_controller_per_selected_id_matrix_check",
        "artifact_path": str(path),
        "per_selected_id_matrix_check_passed": not blockers,
        "blockers": blockers,
        "selected_row_count": summary.get("selected_row_count"),
        "per_turn_shape_row_count": summary.get("per_turn_shape_row_count"),
        "target_selected_compact_case_count": summary.get("target_selected_compact_case_count"),
        "target_unique_scorer_unit_count": summary.get("target_unique_scorer_unit_count"),
        "target_compact_to_scorer_unit_factor": summary.get("target_compact_to_scorer_unit_factor"),
        "target_per_selected_id_pass_available": summary.get("target_per_selected_id_pass_available"),
        "target_pass_is_scorer_unit_inherited": summary.get("target_pass_is_scorer_unit_inherited"),
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
    return 1 if args.strict and not report["per_selected_id_matrix_check_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
