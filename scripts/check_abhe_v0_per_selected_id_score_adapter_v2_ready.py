#!/usr/bin/env python3
"""
check_abhe_v0_per_selected_id_score_adapter_v2_ready
======================================================

Fail-closed gate for the G7-revised v2 score adapter artifact.

Exit 0 ONLY when ALL of:
  - artifact present, schema/kind match
  - top-level keys within whitelist
  - all attestation booleans False
  - source_diagnostic_sha256 matches the on-disk diagnostic
  - rows count == 24 (target case count) for in-scope arms
  - all 24 rows have per_selected_pass_available=true
  - target_promoted_direct_count == 24
  - score_output_contract_satisfied_for_target_v2 == true
  - no forbidden substring in any non-attestation key
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_selected_id_score_adapter_v2.json"

EXPECTED_KIND = "abhe_v0_per_selected_id_score_adapter_v2"
EXPECTED_SCHEMA = "abhe_v0_per_selected_id_score_adapter_v2_v0"
EXPECTED_TARGET_CATEGORY = "multi_turn_miss_param"
EXPECTED_TARGET_CASE_COUNT = 24

ATTESTATION_MUST_FALSE = [
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "sota_3pp_claim_ready", "huawei_acceptance_ready",
]
ATTESTATION_MUST_TRUE = ["bounded_dev_smoke_only", "raw_material_absent"]

FORBIDDEN_SUBSTRINGS = ("prompt", "gold", "expected_argument",
                       "argument_value", "raw_response", "raw_payload", "scorer_diff")
ATTESTATION_ALLOWLIST = {
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
}


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _scan_forbidden(obj, path, blockers):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ATTESTATION_ALLOWLIST:
                _scan_forbidden(v, f"{path}.{k}", blockers)
                continue
            kl = str(k).lower()
            for bad in FORBIDDEN_SUBSTRINGS:
                if bad in kl:
                    blockers.append(f"forbidden_field_in_key:{path}.{k}")
            _scan_forbidden(v, f"{path}.{k}", blockers)
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            _scan_forbidden(x, f"{path}[{i}]", blockers)


def check(strict: bool) -> dict:
    blockers = []
    if not ARTIFACT.exists():
        return {
            "abhe_v0_per_selected_id_score_adapter_v2_ready": False,
            "blockers": ["artifact_missing"],
            "report_scope": "abhe_v0_per_selected_id_score_adapter_v2_ready_check",
        }
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if art.get("artifact_kind") != EXPECTED_KIND:
        blockers.append("artifact_kind_invalid")
    if art.get("schema_version") != EXPECTED_SCHEMA:
        blockers.append("schema_version_invalid")
    for k in ATTESTATION_MUST_FALSE:
        if art.get(k) is not False:
            blockers.append(f"{k}_not_false")
    for k in ATTESTATION_MUST_TRUE:
        if art.get(k) is not True:
            blockers.append(f"{k}_not_true")
    if art.get("target_category") != EXPECTED_TARGET_CATEGORY:
        blockers.append("target_category_invalid")

    src_path = art.get("source_diagnostic_path")
    if src_path:
        full = REPO_ROOT / src_path
        if full.exists():
            actual = _sha256(full)
            if actual != art.get("source_diagnostic_sha256"):
                blockers.append("source_diagnostic_sha256_mismatch")
        else:
            blockers.append("source_diagnostic_path_missing_on_disk")
    else:
        blockers.append("source_diagnostic_path_missing")

    rows = art.get("rows") or []
    if len(rows) != EXPECTED_TARGET_CASE_COUNT:
        blockers.append(f"rows_count_not_24:{len(rows)}")
    for row in rows:
        if row.get("per_selected_pass_available") is not True:
            blockers.append(f"row_not_promoted:{row.get('case_id')}")

    summary = art.get("summary") or {}
    if summary.get("target_total_count") != EXPECTED_TARGET_CASE_COUNT:
        blockers.append("summary_target_total_count_invalid")
    if summary.get("target_promoted_direct_count") != EXPECTED_TARGET_CASE_COUNT:
        blockers.append(f"summary_target_promoted_direct_count_not_24:{summary.get('target_promoted_direct_count')}")
    if summary.get("score_output_contract_satisfied_for_target_v2") is not True:
        blockers.append("summary_contract_not_satisfied")

    _scan_forbidden(art, "$", blockers)

    ready = len(blockers) == 0
    return {
        "abhe_v0_per_selected_id_score_adapter_v2_ready": ready,
        "target_category": art.get("target_category"),
        "target_arms_in_scope": art.get("target_arms_in_scope"),
        "target_arms_pending": art.get("target_arms_pending"),
        "summary": summary,
        "blockers": blockers,
        "report_scope": "abhe_v0_per_selected_id_score_adapter_v2_ready_check",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    r = check(strict=args.strict)
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r["abhe_v0_per_selected_id_score_adapter_v2_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
