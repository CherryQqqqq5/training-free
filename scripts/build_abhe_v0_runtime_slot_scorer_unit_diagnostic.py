#!/usr/bin/env python3
"""Build compact scorer-unit alignment diagnostic for ABHE runtime slot residual runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
MANIFEST = ROOT / "abhe_v0_runtime_slot_controller_residual_stress_slice_manifest.json"
FAILURE = ROOT / "abhe_v0_runtime_slot_controller_residual_failure_analysis.json"
OUTPUT = ROOT / "abhe_v0_runtime_slot_controller_scorer_unit_diagnostic.json"
ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]
TARGET_CATEGORY = "multi_turn_miss_param"
NEXT_ACTION = "implement_scorer_unit_aligned_result_parser_or_slice_before_more_bfcl"


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _arm_path(arm: str) -> Path:
    return ROOT / f"abhe_v0_runtime_slot_controller_residual_dev_smoke_{arm}_arm_compact.json"


def _category_metric(arm_data: Dict[str, Any], category: str) -> Dict[str, Any]:
    for entry in (arm_data.get("entry_compact_metrics") or {}).values():
        cats = entry.get("category_compact_metrics") if isinstance(entry, dict) else None
        if isinstance(cats, dict) and category in cats and isinstance(cats[category], dict):
            return cats[category]
    return {}


def _manifest_hash_counts(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    counts: Dict[str, Dict[str, set[str]]] = {}
    for row in manifest.get("selected_compact_case_identifiers") or []:
        if not isinstance(row, dict):
            continue
        category = str(row.get("bfcl_category"))
        bucket = counts.setdefault(category, {"case_hashes": set(), "row_index_hashes": set(), "identifier_hashes": set()})
        for src, key in [("case_hashes", "case_stable_hash"), ("row_index_hashes", "case_row_index_hash"), ("identifier_hashes", "case_identifier_hash")]:
            value = row.get(key)
            if isinstance(value, str) and value.startswith("sha256:"):
                bucket[src].add(value)
    return {
        category: {
            "selected_case_hash_count": len(bucket["case_hashes"]),
            "selected_row_index_hash_count": len(bucket["row_index_hashes"]),
            "selected_identifier_hash_count": len(bucket["identifier_hashes"]),
        }
        for category, bucket in counts.items()
    }


def build() -> Dict[str, Any]:
    manifest = _load(MANIFEST)
    failure = _load(FAILURE) if FAILURE.exists() else {}
    arms = {arm: _load(_arm_path(arm)) for arm in ARMS if _arm_path(arm).exists()}
    hash_counts = _manifest_hash_counts(manifest)
    categories = list((manifest.get("case_count_by_category") or {}).keys())
    rows: List[Dict[str, Any]] = []
    max_factor = 0.0
    target_row: Dict[str, Any] | None = None
    for category in categories:
        selected_count = int((manifest.get("case_count_by_category") or {}).get(category) or 0)
        score_unit_counts: Dict[str, Any] = {}
        score_available: Dict[str, bool] = {}
        passed_counts: Dict[str, Any] = {}
        accuracies: Dict[str, Any] = {}
        for arm in ARMS:
            metric = _category_metric(arms.get(arm, {}), category)
            score_unit_counts[arm] = metric.get("unique_scorer_unit_count")
            score_available[arm] = metric.get("score_available") is True
            passed_counts[arm] = metric.get("passed_count")
            accuracies[arm] = metric.get("accuracy_pct")
        numeric_units = [int(v) for v in score_unit_counts.values() if isinstance(v, int) or (isinstance(v, str) and str(v).isdigit())]
        min_units = min(numeric_units) if numeric_units else 0
        max_units = max(numeric_units) if numeric_units else 0
        factor = round(selected_count / max(1, min_units), 6) if selected_count else 0.0
        max_factor = max(max_factor, factor)
        diagnosis = "score_units_align_with_selected_compact_rows"
        if min_units and selected_count > min_units:
            diagnosis = "category_score_collapses_multiple_selected_compact_rows"
        elif not min_units:
            diagnosis = "score_unit_count_unavailable"
        row: Dict[str, Any] = {
            "bfcl_category": category,
            "target_bucket": "runtime_slot_controller_v2" if category == TARGET_CATEGORY else "regression_control",
            "selected_compact_case_count": selected_count,
            "selected_hash_counts": hash_counts.get(category, {}),
            "score_unit_count_by_arm": score_unit_counts,
            "score_available_by_arm": score_available,
            "passed_count_by_arm": passed_counts,
            "accuracy_pct_by_arm": accuracies,
            "minimum_scorer_unit_count": min_units,
            "maximum_scorer_unit_count": max_units,
            "compact_to_min_scorer_unit_collapse_factor": factor,
            "scorer_unit_hashes_available": False,
            "strict_per_compact_case_pairing_available": selected_count == min_units and selected_count > 0,
            "diagnosis": diagnosis,
            "raw_material_absent": True,
        }
        if category == TARGET_CATEGORY:
            target_row = row
        rows.append(row)
    target_factor = (target_row or {}).get("compact_to_min_scorer_unit_collapse_factor", 0.0)
    target_units = (target_row or {}).get("minimum_scorer_unit_count", 0)
    target_selected = (target_row or {}).get("selected_compact_case_count", 0)
    measurement = failure.get("measurement_diagnosis") if isinstance(failure.get("measurement_diagnosis"), dict) else {}
    summary = {
        "selected_case_ids_hash": manifest.get("selected_case_ids_hash"),
        "selected_compact_case_count": manifest.get("selected_case_count"),
        "category_count": len(categories),
        "max_compact_to_scorer_unit_collapse_factor": max_factor,
        "target_category": TARGET_CATEGORY,
        "target_selected_compact_case_count": target_selected,
        "target_minimum_scorer_unit_count": target_units,
        "target_compact_to_scorer_unit_collapse_factor": target_factor,
        "target_strict_per_compact_case_pairing_available": bool((target_row or {}).get("strict_per_compact_case_pairing_available")),
        "prior_measurement_diagnosis_next_action": measurement.get("next_required_action"),
        "more_bfcl_before_alignment_recommended": False,
    }
    blockers: List[str] = []
    if not rows:
        blockers.append("category_alignment_rows_missing")
    if not target_row:
        blockers.append("target_category_missing")
    if target_row and target_factor <= 1:
        blockers.append("target_scorer_unit_collapse_not_detected")
    report: Dict[str, Any] = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_scorer_unit_diagnostic",
        "schema_version": "abhe_v0_runtime_slot_controller_scorer_unit_diagnostic_v0",
        "run_scope": "offline_compact_diagnostic_only_no_provider_no_bfcl_no_scorer",
        "bounded_dev_smoke_only": True,
        "summary": summary,
        "category_alignment_rows": rows,
        "recommendations": [
            "do_not_run_more_bfcl_until_result_parser_or_slice_exposes_distinct_scorer_units",
            "prefer_scorer_unit_distinct_slice_or_per_result_record_parser_over_more_compact_rows",
            "keep_runtime_slot_controller_v2_demoted_until_bind_repairs_and_target_scorer_units_both_move",
        ],
        "next_required_action": NEXT_ACTION,
        "raw_material_absent": True,
        "prompt_literal_committed": False,
        "argument_values_committed": False,
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
    leakage_blockers = scan_value(report, label="abhe_v0_runtime_slot_controller_scorer_unit_diagnostic")
    if leakage_blockers:
        report["blockers"] = sorted(set(blockers + leakage_blockers))
    _write(OUTPUT, report)
    return report


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build()
    except Exception as exc:
        report = {
            "artifact_kind": "abhe_v0_runtime_slot_controller_scorer_unit_diagnostic",
            "schema_version": "abhe_v0_runtime_slot_controller_scorer_unit_diagnostic_v0",
            "blockers": [f"load_failed:{exc.__class__.__name__}"],
            "performance_evidence": False,
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
