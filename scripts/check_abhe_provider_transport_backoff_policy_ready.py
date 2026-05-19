#!/usr/bin/env python3
"""
check_abhe_provider_transport_backoff_policy_ready
===================================================

Fail-closed gate for the declarative-only backoff policy artifact.

Exit 0 ONLY when ALL of:
  - artifact present, schema_version + artifact_kind match
  - top-level keys are within whitelist
  - policy_enabled == False (master switch off)
  - policy_wired_into_proxy == False (never wired until packet signoff)
  - all attestation booleans in MUST_FALSE are False
  - all validation booleans are True
  - blockers list empty
  - no forbidden substring in non-attestation keys

This is intentionally NOT registered into the ABHE core 6-checker gate
list (yet). It is an additional declarative-only gate for the new
backoff policy. Promotion requires P1.5b signoff + actual proxy wiring
+ a wired-rerun packet.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_provider_transport_backoff_policy.json"

EXPECTED_KIND = "abhe_v0_provider_transport_backoff_policy"
EXPECTED_SCHEMA = "abhe_v0_provider_transport_backoff_policy_v0"

ATTESTATION_MUST_FALSE = [
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called",
    "scorer_called",
    "policy_enabled", "policy_wired_into_proxy",
    "huawei_acceptance_ready", "sota_3pp_claim_ready",
]
ATTESTATION_MUST_TRUE = ["bounded_dev_smoke_only", "raw_material_absent"]

ALLOWED_TOP_KEYS = {
    "artifact_kind", "schema_version", "run_scope", "bounded_dev_smoke_only",
    "raw_material_absent",
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called",
    "scorer_called",
    "policy_enabled", "policy_wired_into_proxy",
    "huawei_acceptance_ready", "sota_3pp_claim_ready",
    "source_policy_yaml_path", "source_policy_yaml_sha256",
    "source_runtime_yaml_path", "source_runtime_yaml_sha256",
    "runtime_timeout_sec", "policy_per_request_timeout_sec",
    "policy_summary", "validation", "blockers",
}

FORBIDDEN_SUBSTRINGS = ("prompt", "gold", "expected_argument",
                       "argument_value", "raw_response", "raw_payload", "scorer_diff")
ATTESTATION_ALLOWLIST_KEYS = {
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
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
            "abhe_v0_provider_transport_backoff_policy_ready": False,
            "blockers": ["artifact_missing:" + str(ARTIFACT.relative_to(REPO_ROOT))],
            "report_scope": "abhe_v0_provider_transport_backoff_policy_ready_check",
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
    validation = art.get("validation") or {}
    for k, v in validation.items():
        if v is not True:
            blockers.append(f"validation_{k}_not_true")
    if art.get("blockers"):
        blockers.append("builder_reported_blockers:" + ",".join(map(str, art["blockers"])))
    _scan_forbidden(art, "$", blockers)
    ready = len(blockers) == 0
    return {
        "abhe_v0_provider_transport_backoff_policy_ready": ready,
        "policy_enabled": art.get("policy_enabled"),
        "policy_wired_into_proxy": art.get("policy_wired_into_proxy"),
        "policy_per_request_timeout_sec": art.get("policy_per_request_timeout_sec"),
        "runtime_timeout_sec": art.get("runtime_timeout_sec"),
        "performance_evidence": art.get("performance_evidence"),
        "holdout_touched": art.get("holdout_touched"),
        "full_suite_touched": art.get("full_suite_touched"),
        "archive_updated": art.get("archive_updated"),
        "validation": validation,
        "blockers": blockers,
        "report_scope": "abhe_v0_provider_transport_backoff_policy_ready_check",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    r = check(strict=args.strict)
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r["abhe_v0_provider_transport_backoff_policy_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
