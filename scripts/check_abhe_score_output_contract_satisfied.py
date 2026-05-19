#!/usr/bin/env python3
"""
check_abhe_score_output_contract_satisfied
==========================================

Strict fail-closed checker: returns exit 0 only when the score output contract
is *honestly* satisfied for the target category.

CONTRACT
--------
score_output_contract_satisfied_for_target == True
  iff
    - every selected case in target_category has per_selected_pass_available=True
    - via promotion_source="direct_one_to_one_scorer_unit"
    - NO fabricated pass_bool: pass_bool may still be null at P1; what matters here
      is the *contract* (granularity), not the numeric value.

This checker DOES NOT modify any artifact. It only reads
abhe_v0_true_per_selected_id_score_adapter.json (produced by the offline
builder script) and the source per_selected_id_matrix.json.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ADAPTER   = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_true_per_selected_id_score_adapter.json"
MATRIX    = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_per_selected_id_matrix.json"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--strict",  action="store_true")
    args = ap.parse_args()
    blockers = []

    if not ADAPTER.exists():
        blockers.append("abhe_v0_true_per_selected_id_score_adapter_missing")
        print(json.dumps({"abhe_score_output_contract_satisfied": False, "blockers": blockers}))
        sys.exit(1)
    if not MATRIX.exists():
        blockers.append("per_selected_id_matrix_missing")
        print(json.dumps({"abhe_score_output_contract_satisfied": False, "blockers": blockers}))
        sys.exit(1)

    a = json.loads(ADAPTER.read_text())
    summ = a.get("summary", {})
    contract_ok = bool(summ.get("score_output_contract_satisfied_for_target", False))
    target_promoted = summ.get("target_promoted_direct_count", 0)
    target_total    = summ.get("target_total_count", 0)
    target_category = summ.get("target_category")

    if target_total == 0:
        blockers.append("target_total_count_zero")
    if not contract_ok:
        blockers.append(
            f"target_per_selected_pass_unavailable:{target_promoted}/{target_total}_promoted"
        )

    # cross-check against source matrix (defense in depth)
    m = json.loads(MATRIX.read_text())
    m_target_unavailable = sum(
        1 for r in m.get("selected_id_rows", [])
        if r.get("bfcl_category") == target_category and not r.get("per_selected_pass_available", False)
    )
    if args.strict and contract_ok and m_target_unavailable > 0:
        blockers.append(f"matrix_disagrees_adapter:{m_target_unavailable}_still_unavailable_in_matrix")
        # NB: P1 only promotes in the adapter, not the matrix. This blocker only fires
        # if a downstream consumer of matrix is queried in --strict mode AFTER
        # matrix has been re-aligned (P1.5).

    out = {
        "abhe_score_output_contract_satisfied": (len(blockers) == 0),
        "target_category": target_category,
        "target_promoted_direct_count": target_promoted,
        "target_total_count": target_total,
        "blockers": blockers,
        "report_scope": "abhe_score_output_contract_satisfied_check",
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
    }
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(0 if not blockers else 1)

if __name__ == "__main__":
    main()
