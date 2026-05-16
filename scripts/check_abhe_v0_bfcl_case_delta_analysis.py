#!/usr/bin/env python3
"""Validate compact ABHE-v0 BFCL case delta analysis artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_ANALYSIS = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_case_delta_analysis.json")
EXPECTED_HASH = "sha256:8e28826895c76afd14fb2ec07550b871ea50df25c0666881dad39be86450991f"
EXPECTED_ENTRIES = {"state_tracking_v0", "hallucination_abstain_v0"}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate_analysis(analysis: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if analysis.get("artifact_kind") != "abhe_v0_bfcl_case_delta_analysis":
        blockers.append("artifact_kind_invalid")
    if analysis.get("schema_version") != "abhe_v0_bfcl_case_delta_analysis_v0":
        blockers.append("schema_version_invalid")
    if analysis.get("bounded_dev_smoke_only") is not True:
        blockers.append("bounded_dev_smoke_only_not_true")
    if analysis.get("selected_case_ids_hash") != EXPECTED_HASH:
        blockers.append("selected_case_ids_hash_invalid")
    if analysis.get("selected_compact_case_count") != 20:
        blockers.append("selected_compact_case_count_invalid")
    if not isinstance(analysis.get("unique_bfcl_scorer_unit_count"), int):
        blockers.append("unique_bfcl_scorer_unit_count_missing")
    if analysis.get("aggregate_feedback_fixed_count_is_scaled_category_delta") is not True:
        blockers.append("scaled_category_delta_flag_not_true")
    if analysis.get("raw_material_absent") is not True:
        blockers.append("raw_material_absent_not_true")
    for key in ["raw_provider_payload_committed", "raw_bfcl_result_tree_committed", "gold_expected_committed", "scorer_diff_committed", "holdout_touched", "full_suite_touched", "archive_updated", "performance_evidence"]:
        if analysis.get(key) is not False:
            blockers.append(f"{key}_not_false")
    category_rows = analysis.get("category_delta_rows")
    if not isinstance(category_rows, list) or not category_rows:
        blockers.append("category_delta_rows_missing")
        category_rows = []
    entries = {row.get("entry_id") for row in category_rows if isinstance(row, dict)}
    if not entries.issubset(EXPECTED_ENTRIES):
        blockers.append("category_delta_entries_invalid")
    for index, row in enumerate(category_rows):
        if not isinstance(row, dict):
            blockers.append(f"category_row_{index}_not_object")
            continue
        for field in ["entry_id", "bfcl_category", "selected_compact_case_count", "unique_scorer_unit_count", "baseline_pass", "candidate_pass", "delta"]:
            if field not in row:
                blockers.append(f"category_row_{index}_missing_{field}")
        if row.get("delta") not in {"fixed", "regressed", "unchanged_pass", "unchanged_fail", "unknown_score_unavailable"}:
            blockers.append(f"category_row_{index}_delta_invalid")
    compact_rows = analysis.get("compact_case_delta_rows")
    if not isinstance(compact_rows, list) or len(compact_rows) != 20:
        blockers.append("compact_case_delta_rows_count_invalid")
    telemetry = analysis.get("candidate_activation_telemetry")
    if not isinstance(telemetry, dict):
        blockers.append("candidate_activation_telemetry_missing")
    blockers.extend(scan_value(analysis, label="abhe_v0_bfcl_case_delta_analysis"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ANALYSIS) -> Dict[str, Any]:
    if not path.exists():
        return {"report_scope": "abhe_v0_bfcl_case_delta_analysis_check", "analysis_path": str(path), "analysis_present": False, "abhe_v0_bfcl_case_delta_analysis_check_passed": False, "blockers": ["case_delta_analysis_missing"]}
    analysis = _load(path)
    blockers = validate_analysis(analysis)
    return {
        "report_scope": "abhe_v0_bfcl_case_delta_analysis_check",
        "analysis_path": str(path),
        "analysis_present": True,
        "abhe_v0_bfcl_case_delta_analysis_check_passed": not blockers,
        "strict_per_compact_case_paired_available": analysis.get("strict_per_compact_case_paired_available"),
        "unique_bfcl_scorer_unit_count": analysis.get("unique_bfcl_scorer_unit_count"),
        "strict_scorer_unit_fixed_count": analysis.get("strict_scorer_unit_fixed_count"),
        "scaled_compact_fixed_count": analysis.get("scaled_compact_fixed_count"),
        "entry_specific_guidance_detected": (analysis.get("candidate_activation_telemetry") or {}).get("entry_specific_guidance_detected"),
        "global_guidance_detected": (analysis.get("candidate_activation_telemetry") or {}).get("global_guidance_detected"),
        "performance_evidence": analysis.get("performance_evidence"),
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, default=DEFAULT_ANALYSIS)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.analysis)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "abhe_v0_bfcl_case_delta_analysis_check", "abhe_v0_bfcl_case_delta_analysis_check_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 1 if args.strict and not summary.get("abhe_v0_bfcl_case_delta_analysis_check_passed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
