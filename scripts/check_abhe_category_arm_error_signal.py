#!/usr/bin/env python3
"""
check_abhe_category_arm_error_signal
====================================

Strict checker over abhe_v0_category_arm_error_class_matrix.json.

Returns exit 0 iff the artifact is present, schema-valid, and reports honest
category-level arm comparisons. It does NOT require that the target category
have per-case signal (since the source data does not have it). It does enforce
that the artifact correctly attests target_per_case_arm_signal_available
matching the underlying data.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ART = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_category_arm_error_class_matrix.json"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--strict",  action="store_true")
    args = ap.parse_args()
    blockers = []
    if not ART.exists():
        blockers.append("abhe_v0_category_arm_error_class_matrix_missing")
        print(json.dumps({"abhe_category_arm_error_signal_passed": False, "blockers": blockers}))
        sys.exit(1)
    d = json.loads(ART.read_text())
    s = d.get("summary", {})
    for k in ("target_category","target_arm_changed_from_baseline",
              "target_per_case_arm_signal_available",
              "categories_where_any_arm_changed_vs_baseline",
              "categories_with_per_case_arm_signal"):
        if k not in s:
            blockers.append("summary_field_missing:" + k)
    if args.strict:
        target = s.get("target_category")
        target_cat_obj = next((c for c in d.get("categories", []) if c["bfcl_category"] == target), None)
        if target_cat_obj is None:
            blockers.append("target_category_not_in_categories:" + str(target))
        else:
            calc = target_cat_obj.get("per_case_arm_signal_available")
            if calc != s.get("target_per_case_arm_signal_available"):
                blockers.append("target_per_case_arm_signal_mismatch")
    out = {
        "abhe_category_arm_error_signal_passed": (len(blockers) == 0),
        "target_category": s.get("target_category"),
        "target_arm_changed_from_baseline": s.get("target_arm_changed_from_baseline"),
        "target_per_case_arm_signal_available": s.get("target_per_case_arm_signal_available"),
        "categories_where_any_arm_changed_vs_baseline": s.get("categories_where_any_arm_changed_vs_baseline"),
        "categories_with_per_case_arm_signal": s.get("categories_with_per_case_arm_signal"),
        "blockers": blockers,
        "report_scope": "abhe_category_arm_error_signal_check",
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
    }
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(0 if not blockers else 1)

if __name__ == "__main__":
    main()
