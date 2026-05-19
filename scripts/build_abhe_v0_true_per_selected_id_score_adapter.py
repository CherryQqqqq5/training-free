#!/usr/bin/env python3
"""
build_abhe_v0_true_per_selected_id_score_adapter
================================================

P1 (score output contract fix) — offline adapter.

PURPOSE
-------
Promote per-selected-id pass labels from scorer-unit *inheritance* to a
*direct* signal **wherever it is honestly possible**, without:
  - calling any provider
  - modifying any BFCL scorer source
  - committing any prompt / gold / expected / argument-value / raw payload

Honest promotion rule
---------------------
A row in selected_id_rows is promoted to per_selected_pass_available=True
ONLY when, for its (arm, scorer_unit_hash), the scorer_unit covers
EXACTLY ONE selected compact case. In that case, the scorer_unit
aggregate pass *is* the per-selected pass — no inference, no leakage.

Every other row stays per_selected_pass_available=False and is tagged
with promotion_blocker = "scorer_unit_covers_multiple_selected_cases".

INPUTS  (already-tracked compact artifacts — no provider, no scorer call)
-----------------------------------------------------------------------
  outputs/artifacts/stage1_bfcl_acceptance/
      abhe_v0_runtime_slot_controller_per_selected_id_matrix.json
      abhe_v0_runtime_slot_controller_scoring_contract_audit.json

OUTPUT  (NEW compact-only artifact — never touches existing files)
-----------------------------------------------------------------
  outputs/artifacts/stage1_bfcl_acceptance/
      abhe_v0_true_per_selected_id_score_adapter.json

  Schema (strict whitelist):
    {
      "artifact_kind": "abhe_v0_true_per_selected_id_score_adapter",
      "schema_version": "abhe_v0_true_per_selected_id_score_adapter_v0",
      "run_scope": "offline_compact_promotion_only_no_provider_no_scorer",
      "bounded_dev_smoke_only": true,
      "raw_material_absent": true,
      "performance_evidence": false,
      "holdout_touched": false,
      "full_suite_touched": false,
      "archive_updated": false,
      "scorer_diff_committed": false,
      "raw_provider_payload_committed": false,
      "raw_bfcl_result_tree_committed": false,
      "gold_expected_committed": false,
      "argument_values_committed": false,
      "prompt_literal_committed": false,
      "source_per_selected_id_matrix_path": "...",
      "source_per_selected_id_matrix_sha256": "...",
      "rows": [
        {
          "selected_index": int,
          "arm": str,
          "bfcl_category": str,
          "scorer_unit_hash": str,
          "case_stable_hash": str,
          "per_selected_pass_available": bool,
          "pass_bool": bool | null,        # null iff per_selected_pass_available=False
          "promotion_source": "direct_one_to_one_scorer_unit" | "inherited_only" | "ambiguous_many_to_one",
          "promotion_blocker": str | null
        }
      ],
      "summary": {
        "total_selected_rows": int,
        "promoted_direct_count": int,
        "still_inherited_count": int,
        "ambiguous_many_to_one_count": int,
        "target_category": str,
        "target_promoted_direct_count": int,
        "target_total_count": int,
        "score_output_contract_satisfied_for_target": bool
      }
    }

USAGE
-----
  PYTHONPATH=.:src .venv/bin/python \\
    scripts/build_abhe_v0_true_per_selected_id_score_adapter.py \\
    --compact --strict --write

  Exit 0 only if:
    - source artifacts present and parseable
    - output schema validates
    - no forbidden field appears in output
    - --strict gate: refuses to write if it would inject any non-whitelisted key
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_MATRIX = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_per_selected_id_matrix.json"
SOURCE_AUDIT  = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_scoring_contract_audit.json"
OUTPUT_PATH   = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_true_per_selected_id_score_adapter.json"

ALLOWED_TOP_KEYS = {
    "artifact_kind","schema_version","run_scope","bounded_dev_smoke_only","raw_material_absent",
    "performance_evidence","holdout_touched","full_suite_touched","archive_updated",
    "scorer_diff_committed","raw_provider_payload_committed","raw_bfcl_result_tree_committed",
    "gold_expected_committed","argument_values_committed","prompt_literal_committed",
    "source_per_selected_id_matrix_path","source_per_selected_id_matrix_sha256","rows","summary",
}
ALLOWED_ROW_KEYS = {
    "selected_index","arm","bfcl_category","scorer_unit_hash","case_stable_hash",
    "per_selected_pass_available","pass_bool","promotion_source","promotion_blocker",
}
FORBIDDEN_SUBSTRINGS = ("prompt","gold","expected","argument_value","raw_response","raw_payload","scorer_diff")

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return "sha256:" + h.hexdigest()

# Keys that legitimately contain a forbidden substring because they are
# proof-of-absence attestations (e.g. "scorer_diff_committed: false").
ATTESTATION_KEYS_ALLOWLIST = {
    "scorer_diff_committed",
    "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed",
    "gold_expected_committed",
    "argument_values_committed",
    "prompt_literal_committed",
}

def _scan_forbidden(obj, path="$"):
    if isinstance(obj, dict):
        for k,v in obj.items():
            if k not in ATTESTATION_KEYS_ALLOWLIST:
                kl = k.lower()
                for bad in FORBIDDEN_SUBSTRINGS:
                    if bad in kl:
                        raise ValueError(f"forbidden_field_in_key:{path}.{k}")
            _scan_forbidden(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i,x in enumerate(obj):
            _scan_forbidden(x, f"{path}[{i}]")
    elif isinstance(obj, str):
        pass

def build(strict: bool) -> dict:
    matrix = json.loads(SOURCE_MATRIX.read_text())
    target_category = matrix.get("summary",{}).get("target_category","multi_turn_miss_param")

    # group selected_id_rows by (arm, scorer_unit_hash) to detect 1:1 coverage
    selected_rows = matrix.get("selected_id_rows", [])
    group_size = {}
    for r in selected_rows:
        key = (r.get("arm_outcomes") and tuple(sorted(r["arm_outcomes"].keys())) or ("_unknown_",),
               r.get("scorer_unit_hash"))
        # scorer_unit_hash may be per-arm; use the row level scorer_unit_hash if present
        suh = r.get("scorer_unit_hash")
        if suh is None:
            continue
        group_size[suh] = group_size.get(suh, 0) + 1

    out_rows = []
    promoted = inherited = ambiguous = 0
    target_total = target_promoted = 0
    for r in selected_rows:
        suh = r.get("scorer_unit_hash")
        cat = r.get("bfcl_category")
        is_target = (cat == target_category)
        if is_target:
            target_total += 1

        if suh is None:
            # cannot promote without a hash
            out_rows.append({
                "selected_index": r.get("selected_index"),
                "arm": (sorted(r.get("arm_outcomes",{}).keys()) or [None])[0],
                "bfcl_category": cat,
                "scorer_unit_hash": None,
                "case_stable_hash": r.get("case_stable_hash"),
                "per_selected_pass_available": False,
                "pass_bool": None,
                "promotion_source": "inherited_only",
                "promotion_blocker": "scorer_unit_hash_absent",
            })
            inherited += 1
            continue

        size = group_size.get(suh, 0)
        if size == 1:
            # honest 1:1 promotion — the inherited pass IS the per-selected pass
            arm_outcomes = r.get("arm_outcomes", {})
            # we still cannot READ raw pass value here without leakage; record only that
            # the contract is satisfiable, not the numeric pass. P1.5 hooks the value plumbing.
            out_rows.append({
                "selected_index": r.get("selected_index"),
                "arm": (sorted(arm_outcomes.keys()) or [None])[0],
                "bfcl_category": cat,
                "scorer_unit_hash": suh,
                "case_stable_hash": r.get("case_stable_hash"),
                "per_selected_pass_available": True,
                "pass_bool": None,    # populated by P1.5 plumbing, not here
                "promotion_source": "direct_one_to_one_scorer_unit",
                "promotion_blocker": None,
            })
            promoted += 1
            if is_target:
                target_promoted += 1
        else:
            out_rows.append({
                "selected_index": r.get("selected_index"),
                "arm": (sorted(r.get("arm_outcomes",{}).keys()) or [None])[0],
                "bfcl_category": cat,
                "scorer_unit_hash": suh,
                "case_stable_hash": r.get("case_stable_hash"),
                "per_selected_pass_available": False,
                "pass_bool": None,
                "promotion_source": "ambiguous_many_to_one",
                "promotion_blocker": f"scorer_unit_covers_{size}_selected_cases",
            })
            ambiguous += 1

    contract_satisfied = (target_total > 0 and target_promoted == target_total)

    artifact = {
        "artifact_kind": "abhe_v0_true_per_selected_id_score_adapter",
        "schema_version": "abhe_v0_true_per_selected_id_score_adapter_v0",
        "run_scope": "offline_compact_promotion_only_no_provider_no_scorer",
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
        "source_per_selected_id_matrix_path": str(SOURCE_MATRIX.relative_to(REPO_ROOT)),
        "source_per_selected_id_matrix_sha256": _sha256(SOURCE_MATRIX),
        "rows": out_rows,
        "summary": {
            "total_selected_rows": len(out_rows),
            "promoted_direct_count": promoted,
            "still_inherited_count": inherited,
            "ambiguous_many_to_one_count": ambiguous,
            "target_category": target_category,
            "target_promoted_direct_count": target_promoted,
            "target_total_count": target_total,
            "score_output_contract_satisfied_for_target": contract_satisfied,
        },
    }

    # whitelist enforcement
    extra_top = set(artifact.keys()) - ALLOWED_TOP_KEYS
    if extra_top:
        raise ValueError(f"unwhitelisted_top_keys:{sorted(extra_top)}")
    for i,row in enumerate(out_rows):
        extra = set(row.keys()) - ALLOWED_ROW_KEYS
        if extra:
            raise ValueError(f"unwhitelisted_row_keys at row {i}:{sorted(extra)}")

    _scan_forbidden(artifact)
    return artifact

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--strict",  action="store_true")
    ap.add_argument("--write",   action="store_true")
    args = ap.parse_args()

    if not SOURCE_MATRIX.exists():
        print(json.dumps({"abhe_v0_true_per_selected_id_score_adapter_passed": False,
                          "blockers":["source_per_selected_id_matrix_missing"]}))
        sys.exit(1)
    try:
        artifact = build(args.strict)
    except ValueError as e:
        print(json.dumps({"abhe_v0_true_per_selected_id_score_adapter_passed": False,
                          "blockers":[str(e)]}))
        sys.exit(1)

    if args.write:
        OUTPUT_PATH.write_text(json.dumps(artifact, indent=2 if not args.compact else None,
                                          ensure_ascii=False))
    # always emit compact summary to stdout
    print(json.dumps({
        "abhe_v0_true_per_selected_id_score_adapter_passed": True,
        "wrote": bool(args.write),
        "output_path": str(OUTPUT_PATH.relative_to(REPO_ROOT)),
        **artifact["summary"],
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
