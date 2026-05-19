#!/usr/bin/env python3
"""
build_abhe_v0_category_arm_error_class_matrix
==============================================

P1.5a — *honest* category-level arm comparison from existing offline evidence.

WHY
---
P1 (true-per-selected-id score adapter) revealed score_output_contract_satisfied
=False for the target category: every selected case is in an ambiguous_many_to_one
scorer_unit. P1.5b (per-case scorer invocation slicer) is the path to flip that
flag to True, but it requires re-invoking the scorer per case under a separate
approval packet.

Until P1.5b lands, the meaningful question is:
  "with the data we DO have, at *category* granularity, which arms moved the
   error_type_class away from baseline, and which did not?"

This script answers that question, strictly compact, no provider, no scorer.

INPUT  (already-tracked compact artifact)
----------------------------------------
  outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_per_selected_id_matrix.json

OUTPUT (NEW compact artifact)
-----------------------------
  outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_category_arm_error_class_matrix.json

  schema (strict whitelist):
    {
      artifact_kind, schema_version, run_scope, bounded_dev_smoke_only,
      raw_material_absent, performance_evidence, holdout_touched,
      full_suite_touched, archive_updated, scorer_diff_committed,
      raw_provider_payload_committed, raw_bfcl_result_tree_committed,
      gold_expected_committed, argument_values_committed, prompt_literal_committed,
      source_per_selected_id_matrix_path, source_per_selected_id_matrix_sha256,
      categories: [
        {
          bfcl_category, selected_case_count,
          arms: {
            <arm_name>: {
              error_type_class,                  # the (single) class assigned to this arm in this category
              error_type_class_per_case_unique,  # True iff this class is the only one observed for this arm in this category
              inherited_not_independent_count,   # how many cases were marked inherited
              scorer_unit_valid_count,           # how many cases had scorer_unit_valid=True
              independent_per_case_signal_available  # True iff per_case_unique=False (cases differ within this arm)
            }
          },
          arm_changed_from_baseline: [<arm_names where error_type_class differs from baseline arm>],
          baseline_arm_name: "baseline",
          per_case_arm_signal_available: bool   # True iff ANY arm has independent_per_case_signal_available=True
        }
      ],
      summary: {
        total_categories, total_selected_case_count,
        categories_with_per_case_arm_signal,
        categories_where_any_arm_changed_vs_baseline,
        target_category, target_arm_changed_from_baseline,
        target_per_case_arm_signal_available
      }
    }

CONTRACT
--------
This artifact ONLY exposes category-level arm comparisons. It DOES NOT claim
per-case pass labels. The downstream consumer must treat
target_per_case_arm_signal_available=False as "no per-case attribution
authorized at this granularity".
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_per_selected_id_matrix.json"
OUT = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_category_arm_error_class_matrix.json"

ATTESTATION_KEYS = {
    "scorer_diff_committed","raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed","gold_expected_committed",
    "argument_values_committed","prompt_literal_committed",
}
FORBIDDEN_SUBS = ("prompt","gold","expected","argument_value","raw_response","raw_payload","scorer_diff")

ALLOWED_TOP = {
    "artifact_kind","schema_version","run_scope","bounded_dev_smoke_only","raw_material_absent",
    "performance_evidence","holdout_touched","full_suite_touched","archive_updated",
    "scorer_diff_committed","raw_provider_payload_committed","raw_bfcl_result_tree_committed",
    "gold_expected_committed","argument_values_committed","prompt_literal_committed",
    "source_per_selected_id_matrix_path","source_per_selected_id_matrix_sha256",
    "categories","summary",
}
ALLOWED_CAT = {
    "bfcl_category","selected_case_count","arms","arm_changed_from_baseline",
    "baseline_arm_name","per_case_arm_signal_available",
}
ALLOWED_ARM = {
    "error_type_class","error_type_class_per_case_unique",
    "inherited_not_independent_count","scorer_unit_valid_count",
    "independent_per_case_signal_available",
}

def _sha(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()

def _scan_forbidden(obj, path="$"):
    if isinstance(obj, dict):
        for k,v in obj.items():
            if k not in ATTESTATION_KEYS:
                kl = k.lower()
                for bad in FORBIDDEN_SUBS:
                    if bad in kl:
                        raise ValueError(f"forbidden_key:{path}.{k}")
            _scan_forbidden(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i,x in enumerate(obj):
            _scan_forbidden(x, f"{path}[{i}]")

def build() -> dict:
    src = json.loads(SRC.read_text())
    rows = src.get("selected_id_rows", [])
    target_category = src.get("summary", {}).get("target_category", "multi_turn_miss_param")
    baseline_arm = "baseline"

    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r.get("bfcl_category")].append(r)

    cat_objs = []
    cats_with_signal = 0
    cats_changed = 0
    target_arm_changed = []
    target_signal = False
    total_cases = 0

    for cat in sorted(by_cat.keys()):
        cat_rows = by_cat[cat]
        total_cases += len(cat_rows)
        arm_names = set()
        for r in cat_rows:
            arm_names.update(r.get("arm_outcomes", {}).keys())
        arm_objs = {}
        per_case_signal_in_cat = False
        for arm in sorted(arm_names):
            ec_counter = Counter()
            inh_count = 0
            valid_count = 0
            for r in cat_rows:
                ao = r.get("arm_outcomes", {}).get(arm, {})
                ec_counter[ao.get("error_type_class")] += 1
                if ao.get("inherited_not_independent"):
                    inh_count += 1
                if ao.get("scorer_unit_valid"):
                    valid_count += 1
            unique = (len(ec_counter) == 1)
            ind_signal = (not unique)
            if ind_signal:
                per_case_signal_in_cat = True
            # collapse to single error_type_class only if unique; else string with breakdown
            arm_objs[arm] = {
                "error_type_class": list(ec_counter.keys())[0] if unique else
                                    "mixed:" + ",".join(f"{k}={v}" for k,v in ec_counter.most_common()),
                "error_type_class_per_case_unique": unique,
                "inherited_not_independent_count": inh_count,
                "scorer_unit_valid_count": valid_count,
                "independent_per_case_signal_available": ind_signal,
            }
        # arm vs baseline
        bl_class = arm_objs.get(baseline_arm, {}).get("error_type_class")
        changed_arms = sorted([a for a,o in arm_objs.items()
                               if a != baseline_arm and o["error_type_class"] != bl_class])
        if per_case_signal_in_cat:
            cats_with_signal += 1
        if changed_arms:
            cats_changed += 1
        if cat == target_category:
            target_arm_changed = changed_arms
            target_signal = per_case_signal_in_cat

        cat_objs.append({
            "bfcl_category": cat,
            "selected_case_count": len(cat_rows),
            "arms": arm_objs,
            "arm_changed_from_baseline": changed_arms,
            "baseline_arm_name": baseline_arm,
            "per_case_arm_signal_available": per_case_signal_in_cat,
        })

    artifact = {
        "artifact_kind": "abhe_v0_category_arm_error_class_matrix",
        "schema_version": "abhe_v0_category_arm_error_class_matrix_v0",
        "run_scope": "offline_category_aggregate_arm_comparison_only_no_provider_no_scorer",
        "bounded_dev_smoke_only": True,
        "raw_material_absent": True,
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "scorer_diff_committed": False,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "argument_values_committed": False,
        "prompt_literal_committed": False,
        "source_per_selected_id_matrix_path": str(SRC.relative_to(REPO)),
        "source_per_selected_id_matrix_sha256": _sha(SRC),
        "categories": cat_objs,
        "summary": {
            "total_categories": len(cat_objs),
            "total_selected_case_count": total_cases,
            "categories_with_per_case_arm_signal": cats_with_signal,
            "categories_where_any_arm_changed_vs_baseline": cats_changed,
            "target_category": target_category,
            "target_arm_changed_from_baseline": target_arm_changed,
            "target_per_case_arm_signal_available": target_signal,
        },
    }

    # whitelist enforcement
    extra_top = set(artifact.keys()) - ALLOWED_TOP
    if extra_top:
        raise ValueError(f"unwhitelisted_top:{sorted(extra_top)}")
    for c in cat_objs:
        extra_c = set(c.keys()) - ALLOWED_CAT
        if extra_c: raise ValueError(f"unwhitelisted_cat:{sorted(extra_c)}")
        for arm_obj in c["arms"].values():
            extra_a = set(arm_obj.keys()) - ALLOWED_ARM
            if extra_a: raise ValueError(f"unwhitelisted_arm:{sorted(extra_a)}")
    _scan_forbidden(artifact)
    return artifact

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--strict",  action="store_true")
    ap.add_argument("--write",   action="store_true")
    args = ap.parse_args()

    if not SRC.exists():
        print(json.dumps({"passed": False, "blockers":["source_per_selected_id_matrix_missing"]}))
        sys.exit(1)
    try:
        artifact = build()
    except ValueError as e:
        print(json.dumps({"passed": False, "blockers":[str(e)]}))
        sys.exit(1)
    if args.write:
        OUT.write_text(json.dumps(artifact, indent=2 if not args.compact else None, ensure_ascii=False))
    print(json.dumps({
        "abhe_v0_category_arm_error_class_matrix_passed": True,
        "wrote": bool(args.write),
        "output_path": str(OUT.relative_to(REPO)),
        **artifact["summary"],
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
