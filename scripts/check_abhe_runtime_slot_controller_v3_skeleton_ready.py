#!/usr/bin/env python3
"""
check_abhe_runtime_slot_controller_v3_skeleton_ready
=====================================================

Fail-closed gate checker for the v3 skeleton artifact.

Exit 0 ONLY when ALL of:
  - artifact present, schema_version matches, artifact_kind matches
  - all top-level keys are in the whitelist (no surprise fields)
  - every attestation boolean below is False
  - runtime_wired_into_proxy is False (skeleton-only invariant)
  - every case decision_matches_expectation is True
  - no would_block_valid_tool_call across all cases
  - no forbidden substring in any non-attestation key
  - blockers list is empty

This is intentionally NOT registered into the ABHE core 6-checker gate
list (yet). It is an *additional* skeleton-only gate for the new
mechanism on its feature branch. Promotion to the core gate requires
runtime wiring + approved rerun packet (P1.5b / future P2-wire).
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_v3_skeleton.json"

EXPECTED_KIND = "abhe_v0_runtime_slot_controller_v3_skeleton"
EXPECTED_SCHEMA = "abhe_v0_runtime_slot_controller_v3_skeleton_v0"

ATTESTATION_MUST_FALSE = [
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called",
    "scorer_called", "runtime_wired_into_proxy",
    "huawei_acceptance_ready", "sota_3pp_claim_ready",
]
ATTESTATION_MUST_TRUE = [
    "bounded_dev_smoke_only", "raw_material_absent",
]

ALLOWED_TOP_KEYS = {
    "artifact_kind", "schema_version", "run_scope", "bounded_dev_smoke_only",
    "raw_material_absent",
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called",
    "scorer_called", "runtime_wired_into_proxy",
    "huawei_acceptance_ready", "sota_3pp_claim_ready",
    "source_fixture_path", "source_fixture_sha256",
    "cases", "summary", "blockers",
}

FORBIDDEN_SUBSTRINGS = ("prompt", "gold", "expected_argument", "argument_value",
                       "raw_response", "raw_payload", "scorer_diff")
ATTESTATION_ALLOWLIST_KEYS = {
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "expected_decision_class", "decision_matches_expectation",
    "decisions_matching_expectation",
}


def _scan_forbidden(obj, path, blockers):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ATTESTATION_ALLOWLIST_KEYS:
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
            "abhe_v0_runtime_slot_controller_v3_skeleton_ready": False,
            "blockers": ["artifact_missing:" + str(ARTIFACT.relative_to(REPO_ROOT))],
            "report_scope": "abhe_v0_runtime_slot_controller_v3_skeleton_ready_check",
        }
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if art.get("artifact_kind") != EXPECTED_KIND:
        blockers.append("artifact_kind_invalid")
    if art.get("schema_version") != EXPECTED_SCHEMA:
        blockers.append("schema_version_invalid")
    bad_top = set(art.keys()) - ALLOWED_TOP_KEYS
    if bad_top:
        blockers.append("non_whitelisted_top_keys:" + ",".join(sorted(bad_top)))
    for key in ATTESTATION_MUST_FALSE:
        if art.get(key) is not False:
            blockers.append(f"{key}_not_false")
    for key in ATTESTATION_MUST_TRUE:
        if art.get(key) is not True:
            blockers.append(f"{key}_not_true")
    cases = art.get("cases") or []
    if not isinstance(cases, list) or not cases:
        blockers.append("cases_empty_or_invalid")
    else:
        for cr in cases:
            if not cr.get("decision_matches_expectation"):
                blockers.append("decision_mismatch:" + str(cr.get("case_id_synthetic")))
            if cr.get("would_block_valid_tool_call"):
                blockers.append("would_block_valid_tool_call:" + str(cr.get("case_id_synthetic")))
    summary = art.get("summary") or {}
    if summary.get("total_cases") != len(cases):
        blockers.append("summary_total_cases_mismatch")
    if summary.get("decisions_matching_expectation") != len(cases):
        blockers.append("summary_decisions_matching_expectation_mismatch")
    if summary.get("any_would_block_valid_tool_call") is not False:
        blockers.append("summary_any_would_block_valid_tool_call_not_false")
    if art.get("blockers"):
        blockers.append("builder_reported_blockers:" + ",".join(map(str, art["blockers"])))
    _scan_forbidden(art, "$", blockers)

    ready = len(blockers) == 0
    return {
        "abhe_v0_runtime_slot_controller_v3_skeleton_ready": ready,
        "total_cases": summary.get("total_cases"),
        "decisions_matching_expectation": summary.get("decisions_matching_expectation"),
        "decisions_by_class": summary.get("decisions_by_class") or {},
        "runtime_wired_into_proxy": art.get("runtime_wired_into_proxy"),
        "performance_evidence": art.get("performance_evidence"),
        "holdout_touched": art.get("holdout_touched"),
        "full_suite_touched": art.get("full_suite_touched"),
        "archive_updated": art.get("archive_updated"),
        "blockers": blockers,
        "report_scope": "abhe_v0_runtime_slot_controller_v3_skeleton_ready_check",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    r = check(strict=args.strict)
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r["abhe_v0_runtime_slot_controller_v3_skeleton_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
