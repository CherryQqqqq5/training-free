#!/usr/bin/env python3
"""Build ABHE runtime-slot scoring contract audit from compact artifacts.

This is an offline compact audit. It does not call provider, BFCL, or scorer.
It distinguishes the selected BFCL scorer-unit plan from the score records that
current compact BFCL outputs expose after the bounded rerun.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
MANIFEST = ROOT / "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json"
SCORER_MATRIX = ROOT / "abhe_v0_runtime_slot_controller_scorer_unit_matrix.json"
PER_SELECTED_MATRIX = ROOT / "abhe_v0_runtime_slot_controller_per_selected_id_matrix.json"
RESULT = ROOT / "abhe_v0_runtime_slot_controller_distinct_rerun_result.json"
OUTPUT = ROOT / "abhe_v0_runtime_slot_controller_scoring_contract_audit.json"
TARGET_CATEGORY = "multi_turn_miss_param"
NEXT_ACTION = "fix_score_output_contract_or_enable_true_per_selected_or_per_turn_scoring_before_more_bfcl"
FALSE_FIELDS = [
    "provider_calls_made",
    "bfcl_generate_called",
    "bfcl_evaluate_called",
    "scorer_called",
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


def build() -> Dict[str, Any]:
    manifest = _load(MANIFEST)
    scorer = _load(SCORER_MATRIX)
    per_selected = _load(PER_SELECTED_MATRIX)
    result = _load(RESULT)

    case_counts = manifest.get("case_count_by_category") if isinstance(manifest.get("case_count_by_category"), dict) else {}
    selected_units = manifest.get("scorer_unit_count_by_category") if isinstance(manifest.get("scorer_unit_count_by_category"), dict) else {}
    score_rows = scorer.get("category_alignment_rows") if isinstance(scorer.get("category_alignment_rows"), list) else []
    score_by_category = {row.get("bfcl_category"): row for row in score_rows if isinstance(row, dict)}
    per_rows = per_selected.get("category_summaries") if isinstance(per_selected.get("category_summaries"), list) else []
    per_by_category = {row.get("bfcl_category"): row for row in per_rows if isinstance(row, dict)}

    rows: List[Dict[str, Any]] = []
    for category in sorted(case_counts):
        selected_compact = int(case_counts.get(category) or 0)
        selected_scorer_unit_count = int(selected_units.get(category) or selected_compact)
        score_row = score_by_category.get(category, {})
        per_row = per_by_category.get(category, {})
        observed_score_record_count = int(score_row.get("score_record_count") or per_row.get("observed_score_record_count") or per_row.get("unique_scorer_unit_count") or 0)
        rows.append({
            "bfcl_category": category,
            "selected_compact_case_count": selected_compact,
            "selected_scorer_unit_count": selected_scorer_unit_count,
            "observed_score_record_count": observed_score_record_count,
            "compact_to_observed_score_record_factor": round(selected_compact / max(1, observed_score_record_count), 6) if selected_compact else 0.0,
            "selected_scorer_unit_to_observed_score_record_factor": round(selected_scorer_unit_count / max(1, observed_score_record_count), 6) if selected_scorer_unit_count else 0.0,
            "per_selected_id_pass_available": False,
            "per_turn_pass_available": False,
            "pass_labels_are_score_record_inherited": observed_score_record_count < selected_compact,
            "raw_material_absent": True,
        })

    target = next((row for row in rows if row["bfcl_category"] == TARGET_CATEGORY), {})
    summary = {
        "selected_case_ids_hash": manifest.get("selected_case_ids_hash"),
        "selected_compact_case_count": manifest.get("selected_case_count"),
        "target_category": TARGET_CATEGORY,
        "target_selected_compact_case_count": target.get("selected_compact_case_count"),
        "target_selected_scorer_unit_count": target.get("selected_scorer_unit_count"),
        "target_observed_score_record_count": target.get("observed_score_record_count"),
        "target_selected_scorer_unit_to_observed_score_record_factor": target.get("selected_scorer_unit_to_observed_score_record_factor"),
        "distinct_selection_gate_claimed_target_scorer_units": manifest.get("target_unique_scorer_unit_count"),
        "score_output_contract_satisfied_for_target": False,
        "true_per_selected_or_per_turn_scoring_available": False,
        "more_bfcl_before_contract_fix_recommended": False,
    }
    report: Dict[str, Any] = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_scoring_contract_audit",
        "schema_version": "abhe_v0_runtime_slot_controller_scoring_contract_audit_v0",
        "run_scope": "offline_compact_scoring_contract_audit_only_no_provider_no_bfcl_no_scorer",
        "bounded_dev_smoke_only": True,
        "summary": summary,
        "category_rows": rows,
        "interpretation": {
            "selected_distinct_scorer_units_available": True,
            "observed_score_records_are_category_level_for_target": target.get("observed_score_record_count") == 1,
            "do_not_interpret_target_as_true_per_selected_pass_fail": True,
            "root_cause": "score_output_contract_does_not_expose_target_per_selected_or_per_turn_pass_labels",
        },
        "distinct_rerun_result_path": str(RESULT),
        "arm_compact_metrics": result.get("arm_compact_metrics"),
        "next_required_action": NEXT_ACTION,
        "raw_material_absent": True,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "performance_evidence": False,
        "blockers": [],
    }
    if int(summary.get("target_selected_scorer_unit_count") or 0) <= 1:
        report["blockers"].append("target_selected_scorer_unit_count_not_distinct")
    if int(summary.get("target_observed_score_record_count") or 0) <= 0:
        report["blockers"].append("target_observed_score_record_missing")
    if summary.get("true_per_selected_or_per_turn_scoring_available") is not False:
        report["blockers"].append("true_per_selected_scoring_must_be_false")
    for key in FALSE_FIELDS:
        if report.get(key) is not False:
            report["blockers"].append(f"{key}_not_false")
    leakage = scan_value(report, label="abhe_v0_runtime_slot_controller_scoring_contract_audit")
    if leakage:
        report["blockers"] = sorted(set(report["blockers"] + leakage))
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
            "artifact_kind": "abhe_v0_runtime_slot_controller_scoring_contract_audit",
            "blockers": [f"load_failed:{exc.__class__.__name__}"],
            "performance_evidence": False,
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
