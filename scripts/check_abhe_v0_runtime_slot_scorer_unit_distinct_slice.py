#!/usr/bin/env python3
"""Check ABHE runtime slot scorer-unit-distinct residual slice proposal."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json")
TARGET_CATEGORY = "multi_turn_miss_param"
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
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan_v0":
        blockers.append("schema_version_invalid")
    if data.get("raw_material_absent") is not True:
        blockers.append("raw_material_absent_not_true")
    if data.get("scorer_unit_distinct_slice_ready") is not True:
        blockers.append("scorer_unit_distinct_slice_not_ready")
    if data.get("true_per_selected_id_scoring_enabled") is not False:
        blockers.append("true_per_selected_id_scoring_unexpectedly_enabled")
    if int(data.get("archive_source_overlap_count") or 0) != 0:
        blockers.append("archive_source_overlap_nonzero")
    if int(data.get("prior_slice_overlap_count") or 0) != 0:
        blockers.append("prior_slice_overlap_nonzero")
    for key in FALSE_FIELDS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false")
    rows = data.get("selected_compact_case_identifiers") if isinstance(data.get("selected_compact_case_identifiers"), list) else []
    if not rows:
        blockers.append("selected_compact_case_identifiers_missing")
    by_category: Dict[str, set[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            blockers.append("selected_row_not_object")
            continue
        if row.get("raw_material_absent") is not True:
            blockers.append("selected_row_raw_material_absent_not_true")
        if row.get("scorer_unit_distinct") is not True:
            blockers.append("selected_row_scorer_unit_distinct_not_true")
        unit_hash = row.get("scorer_unit_hash")
        if not isinstance(unit_hash, str) or not unit_hash.startswith("sha256:"):
            blockers.append("selected_row_scorer_unit_hash_invalid")
        by_category.setdefault(str(row.get("bfcl_category")), set()).add(str(unit_hash))
    case_counts = data.get("case_count_by_category") if isinstance(data.get("case_count_by_category"), dict) else {}
    scorer_counts = data.get("scorer_unit_count_by_category") if isinstance(data.get("scorer_unit_count_by_category"), dict) else {}
    for category, count in case_counts.items():
        if int(count or 0) != int(scorer_counts.get(category) or -1):
            blockers.append(f"category_scorer_unit_count_mismatch:{category}")
        if int(count or 0) != len(by_category.get(str(category), set())):
            blockers.append(f"category_selected_unit_hash_count_mismatch:{category}")
    if data.get("target_category") != TARGET_CATEGORY:
        blockers.append("target_category_invalid")
    if data.get("target_compact_to_scorer_unit_factor") != 1.0:
        blockers.append("target_compact_to_scorer_unit_factor_not_one")
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
    return {
        "report_scope": "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_check",
        "artifact_path": str(path),
        "scorer_unit_distinct_slice_check_passed": not blockers,
        "scorer_unit_distinct_slice_ready": data.get("scorer_unit_distinct_slice_ready") is True,
        "blockers": blockers,
        "selected_case_ids_hash": data.get("selected_case_ids_hash"),
        "selected_case_count": data.get("selected_case_count"),
        "target_selected_compact_case_count": data.get("target_selected_compact_case_count"),
        "target_unique_scorer_unit_count": data.get("target_unique_scorer_unit_count"),
        "target_compact_to_scorer_unit_factor": data.get("target_compact_to_scorer_unit_factor"),
        "true_per_selected_id_scoring_enabled": data.get("true_per_selected_id_scoring_enabled"),
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
    return 1 if args.strict and not report["scorer_unit_distinct_slice_check_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
