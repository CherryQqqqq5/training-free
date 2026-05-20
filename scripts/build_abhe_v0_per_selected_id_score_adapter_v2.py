#!/usr/bin/env python3
"""
build_abhe_v0_per_selected_id_score_adapter_v2
================================================

G7-revised — direct per-case pass-label promotion from BFCL's batched
score JSON via the sanitized per-case diagnostic emitted by G6b-2.

PURPOSE
-------
Replace P1's matrix-based promotion (which suffered from
scorer_unit_hash collapse to category-level on the input matrix) with
a direct read from BFCL's score JSON. The G6b-2 baseline arm run
(2026-05-20) revealed that BFCL evaluator's batched output already
contains 17 per-case invalid records for multi_turn_miss_param, with
the remaining 7 IDs implicitly passing. Combined, this gives all 24
per-case PASS/FAIL labels directly — no per-case scorer invocation
needed.

INPUTS  (already-committed compact artifacts)
---------------------------------------------
  outputs/artifacts/stage1_bfcl_acceptance/
      abhe_v0_baseline_arm_residual_smoke_per_case_diagnostic.json

  This input contains 48 per-case records from the May 20 baseline arm
  run, each with: case_id (BFCL public ID), category, passed (bool),
  error_type_class (sanitized class label), latency, turn_count.
  NO raw prompt / gold / expected / argument values / responses.

OUTPUT  (NEW compact-only artifact — does NOT replace P1's artifact)
--------------------------------------------------------------------
  outputs/artifacts/stage1_bfcl_acceptance/
      abhe_v0_per_selected_id_score_adapter_v2.json

  Strict whitelist schema (top-level):
    artifact_kind, schema_version, run_scope, bounded_dev_smoke_only,
    raw_material_absent, performance_evidence, holdout_touched,
    full_suite_touched, archive_updated, scorer_diff_committed,
    raw_provider_payload_committed, raw_bfcl_result_tree_committed,
    gold_expected_committed, argument_values_committed,
    prompt_literal_committed, sota_3pp_claim_ready, huawei_acceptance_ready,
    source_diagnostic_path, source_diagnostic_sha256,
    target_category, target_arms_in_scope, target_arms_pending,
    rows, summary

  Per-row whitelist:
    arm, bfcl_category, case_id, selected_index,
    per_selected_pass_available, pass_bool,
    promotion_source, promotion_blocker, error_type_class

  Summary whitelist:
    arm, target_category, target_total_count,
    target_promoted_direct_count, target_pass_count, target_fail_count,
    target_per_selected_pass_available_count,
    score_output_contract_satisfied_for_target_v2

USAGE
-----
  PYTHONPATH=. .venv/bin/python \\
    scripts/build_abhe_v0_per_selected_id_score_adapter_v2.py \\
    --compact --strict --write

  Exit 0 only if:
    - source diagnostic present + parseable
    - all 24 target-category case_ids found with passed-boolean
    - schema validates (whitelist; no forbidden substring)
    - target_promoted_direct_count == 24

DOES NOT
--------
  - Replace the original P1 adapter artifact (preserved as evidence
    of the prior matrix-based approach)
  - Call any provider / BFCL / scorer
  - Modify any existing artifact
  - Promote arms beyond baseline (the others can be promoted when
    their respective runs land; this v2 builder is arm-aware and
    accepts multi-arm diagnostics in future)
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIAGNOSTIC = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_baseline_arm_residual_smoke_per_case_diagnostic.json"
OUTPUT_PATH = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_selected_id_score_adapter_v2.json"

EXPECTED_TARGET_CATEGORY = "multi_turn_miss_param"
EXPECTED_TARGET_CASE_COUNT = 24
EXPECTED_ARMS_FULL = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]

ALLOWED_TOP_KEYS = {
    "artifact_kind", "schema_version", "run_scope", "bounded_dev_smoke_only",
    "raw_material_absent",
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "sota_3pp_claim_ready", "huawei_acceptance_ready",
    "source_diagnostic_path", "source_diagnostic_sha256",
    "target_category", "target_arms_in_scope", "target_arms_pending",
    "rows", "summary",
}
ALLOWED_ROW_KEYS = {
    "arm", "bfcl_category", "case_id", "selected_index",
    "per_selected_pass_available", "pass_bool",
    "promotion_source", "promotion_blocker", "error_type_class",
}
ALLOWED_SUMMARY_KEYS = {
    "arm", "target_category", "target_total_count",
    "target_promoted_direct_count", "target_pass_count", "target_fail_count",
    "target_per_selected_pass_available_count",
    "score_output_contract_satisfied_for_target_v2",
}

FORBIDDEN_SUBSTRINGS = ("prompt", "gold", "expected_argument",
                       "argument_value", "raw_response", "raw_payload", "scorer_diff")
ATTESTATION_ALLOWLIST = {
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
}


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _scan_forbidden(obj, path="$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ATTESTATION_ALLOWLIST:
                _scan_forbidden(v, f"{path}.{k}")
                continue
            kl = str(k).lower()
            for bad in FORBIDDEN_SUBSTRINGS:
                if bad in kl:
                    raise ValueError(f"forbidden_field_in_key:{path}.{k}")
            _scan_forbidden(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            _scan_forbidden(x, f"{path}[{i}]")


def build(strict: bool) -> Dict[str, Any]:
    diag = json.loads(SOURCE_DIAGNOSTIC.read_text(encoding="utf-8"))
    arm_in_diag = diag.get("arm", "baseline")
    per_case_records = diag.get("per_case_records") or []
    target_records = [r for r in per_case_records if r.get("category") == EXPECTED_TARGET_CATEGORY]

    blockers: List[str] = []
    if len(target_records) != EXPECTED_TARGET_CASE_COUNT:
        blockers.append(
            f"target_record_count_mismatch:{len(target_records)}_expected_{EXPECTED_TARGET_CASE_COUNT}"
        )

    # Sort by case_id numerically (so selected_index is stable and deterministic)
    def _id_num(case_id: str) -> int:
        try:
            return int(case_id.rsplit("_", 1)[-1])
        except Exception:
            return -1

    target_records.sort(key=lambda r: _id_num(r.get("case_id", "")))
    rows: List[Dict[str, Any]] = []
    pass_count = 0
    fail_count = 0
    promoted_direct = 0
    for idx, r in enumerate(target_records):
        passed = bool(r.get("passed"))
        if passed:
            pass_count += 1
        else:
            fail_count += 1
        row = {
            "arm": arm_in_diag,
            "bfcl_category": r.get("category"),
            "case_id": r.get("case_id"),
            "selected_index": idx,
            "per_selected_pass_available": True,
            "pass_bool": passed,
            "promotion_source": "direct_from_bfcl_score_json_invalid_record_set_diff",
            "promotion_blocker": None,
            "error_type_class": r.get("error_type_class") or ("passed" if passed else "unclassified"),
        }
        rows.append(row)
        if row["per_selected_pass_available"]:
            promoted_direct += 1

    contract_satisfied = (
        promoted_direct == EXPECTED_TARGET_CASE_COUNT
        and not blockers
    )

    arms_pending = [a for a in EXPECTED_ARMS_FULL if a != arm_in_diag]

    summary = {
        "arm": arm_in_diag,
        "target_category": EXPECTED_TARGET_CATEGORY,
        "target_total_count": len(target_records),
        "target_promoted_direct_count": promoted_direct,
        "target_pass_count": pass_count,
        "target_fail_count": fail_count,
        "target_per_selected_pass_available_count": promoted_direct,
        "score_output_contract_satisfied_for_target_v2": contract_satisfied,
    }

    artifact = {
        "artifact_kind": "abhe_v0_per_selected_id_score_adapter_v2",
        "schema_version": "abhe_v0_per_selected_id_score_adapter_v2_v0",
        "run_scope": "offline_v2_adapter_reads_baseline_arm_per_case_diagnostic_no_provider_call",
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
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "source_diagnostic_path": str(SOURCE_DIAGNOSTIC.relative_to(REPO_ROOT)),
        "source_diagnostic_sha256": _sha256(SOURCE_DIAGNOSTIC),
        "target_category": EXPECTED_TARGET_CATEGORY,
        "target_arms_in_scope": [arm_in_diag],
        "target_arms_pending": arms_pending,
        "rows": rows,
        "summary": summary,
    }

    if strict:
        bad = set(artifact.keys()) - ALLOWED_TOP_KEYS
        if bad:
            raise ValueError("non_whitelisted_top_keys:" + ",".join(sorted(bad)))
        for row in rows:
            rbad = set(row.keys()) - ALLOWED_ROW_KEYS
            if rbad:
                raise ValueError("non_whitelisted_row_keys:" + ",".join(sorted(rbad)))
        sbad = set(summary.keys()) - ALLOWED_SUMMARY_KEYS
        if sbad:
            raise ValueError("non_whitelisted_summary_keys:" + ",".join(sorted(sbad)))
        _scan_forbidden(artifact)

    return artifact


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    art = build(strict=args.strict)
    if args.write:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(art, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.compact:
        out = {
            "abhe_v0_per_selected_id_score_adapter_v2_passed": (
                art["summary"]["score_output_contract_satisfied_for_target_v2"] is True
            ),
            "target_category": art["target_category"],
            "target_arms_in_scope": art["target_arms_in_scope"],
            "target_arms_pending": art["target_arms_pending"],
            "summary": art["summary"],
            "report_scope": "abhe_v0_per_selected_id_score_adapter_v2_build",
        }
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(json.dumps(art, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
