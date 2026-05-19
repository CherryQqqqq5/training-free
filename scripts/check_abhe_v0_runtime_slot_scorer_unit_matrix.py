#!/usr/bin/env python3
"""Check compact scorer-unit matrix for ABHE runtime slot residual runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_scorer_unit_matrix.json")
FALSE_FIELDS = ["prompt_literal_committed", "argument_values_committed", "raw_provider_payload_committed", "raw_bfcl_result_tree_committed", "gold_expected_committed", "scorer_diff_committed", "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called", "scorer_called", "holdout_touched", "full_suite_touched", "archive_updated", "performance_evidence"]


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_scorer_unit_matrix":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_scorer_unit_matrix_v0":
        blockers.append("schema_version_invalid")
    if data.get("raw_material_absent") is not True:
        blockers.append("raw_material_absent_not_true")
    for key in FALSE_FIELDS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false")
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    if int(summary.get("target_score_record_count") or 0) <= 0:
        blockers.append("target_score_record_count_missing")
    if summary.get("target_strict_per_compact_case_pairing_available") is not False:
        blockers.append("target_pairing_not_marked_unavailable")
    if summary.get("more_bfcl_before_alignment_recommended") is not False:
        blockers.append("more_bfcl_before_alignment_not_blocked")
    rows = data.get("scorer_unit_rows") if isinstance(data.get("scorer_unit_rows"), list) else []
    if not rows:
        blockers.append("scorer_unit_rows_missing")
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
        "report_scope": "abhe_v0_runtime_slot_controller_scorer_unit_matrix_check",
        "artifact_path": str(path),
        "scorer_unit_matrix_check_passed": not blockers,
        "blockers": blockers,
        "target_selected_scorer_unit_count": summary.get("target_selected_scorer_unit_count"),
        "target_observed_score_record_count": summary.get("target_observed_score_record_count"),
        "target_score_record_count": summary.get("target_score_record_count"),
        "target_compact_to_observed_score_record_factor": summary.get("target_compact_to_observed_score_record_factor"),
        "target_compact_to_score_record_factor": summary.get("target_compact_to_score_record_factor"),
        "target_strict_per_compact_case_pairing_available": summary.get("target_strict_per_compact_case_pairing_available"),
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
    return 1 if args.strict and not report["scorer_unit_matrix_check_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
