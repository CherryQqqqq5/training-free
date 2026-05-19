#!/usr/bin/env python3
"""
build_abhe_v0_provider_transport_backoff_policy
================================================

P3 (declarative-only) — read configs/runtime_bfcl_provider_transport_backoff_policy.yaml,
cross-validate it against configs/runtime_bfcl_structured.yaml, and emit a
compact validation artifact.

This script:
  - does NOT call any provider
  - does NOT call BFCL generate/evaluate
  - does NOT call any scorer
  - does NOT modify any existing artifact
  - does NOT modify configs/runtime_bfcl_structured.yaml
  - asserts policy.enabled == False (master switch)

LITERATURE
----------
  - Marc Brooker (AWS), "Exponential Backoff and Jitter" (2015):
    Full Jitter == sleep ~ Uniform(0, min(cap, base*2^n)).
  - "Beyond Max Tokens" (arxiv 2025): multi-turn tool-call chains can
    amplify cost 100-658x; bounded retry envelopes are mandatory.
  - BFCL-v3 multi-turn blog: timeouts and 504s are the dominant transient
    failure mode on extended categories like multi_turn_miss_param.

INPUTS
------
  configs/runtime_bfcl_provider_transport_backoff_policy.yaml
  configs/runtime_bfcl_structured.yaml

OUTPUT
------
  outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_provider_transport_backoff_policy.json

USAGE
-----
  PYTHONPATH=. .venv/bin/python \\
    scripts/build_abhe_v0_provider_transport_backoff_policy.py \\
    --compact --strict --write
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
POLICY_YAML = REPO_ROOT / "configs/runtime_bfcl_provider_transport_backoff_policy.yaml"
RUNTIME_YAML = REPO_ROOT / "configs/runtime_bfcl_structured.yaml"
OUTPUT_PATH = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_provider_transport_backoff_policy.json"

# Sane bounds (defense in depth)
BOUNDS = {
    "max_retries": (0, 10),
    "initial_delay_ms": (50, 30_000),
    "max_delay_ms": (100, 120_000),
    "multiplier": (1.0, 10.0),
    "per_request_timeout_sec": (1, 600),
    "max_total_retry_time_sec": (1, 600),
    "max_concurrent_in_flight_requests": (1, 32),
    "abort_run_after_consecutive_504s": (1, 100),
}
ALLOWED_JITTER = {"none", "equal_jitter", "full_jitter", "decorrelated_jitter"}
ALLOWED_RETRY_CODES = {408, 425, 429, 500, 502, 503, 504, 522, 524}

# Allowed top-level fields under policy block (whitelist)
ALLOWED_POLICY_KEYS = {
    "schema_version", "enabled", "max_retries", "initial_delay_ms",
    "max_delay_ms", "multiplier", "jitter_strategy",
    "per_request_timeout_sec", "retry_on_status_codes",
    "hard_caps", "applies_to",
    "provider_calls_authorized_by_this_policy",
    "bfcl_generate_authorized_by_this_policy",
    "bfcl_evaluate_authorized_by_this_policy",
    "scorer_authorized_by_this_policy",
    "performance_evidence_authorized_by_this_policy",
    "archive_update_authorized_by_this_policy",
    "holdout_authorized_by_this_policy",
    "full_suite_authorized_by_this_policy",
    "huawei_acceptance_authorized_by_this_policy",
    "sota_3pp_claim_authorized_by_this_policy",
}
ALLOWED_HARD_CAP_KEYS = {
    "max_total_retry_time_sec",
    "max_concurrent_in_flight_requests",
    "abort_run_after_consecutive_504s",
}
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
ALLOWED_VALIDATION_KEYS = {
    "policy_block_present", "policy_keys_within_whitelist",
    "policy_enabled_is_false", "bounds_checks_passed",
    "jitter_strategy_valid", "retry_status_codes_subset",
    "per_request_timeout_under_runtime_timeout",
    "hard_caps_present", "hard_caps_within_whitelist",
    "applies_to_present_and_nonempty",
    "authorization_attestations_all_false",
}
ALLOWED_SUMMARY_KEYS = {
    "policy_schema_version", "max_retries", "initial_delay_ms",
    "max_delay_ms", "multiplier", "jitter_strategy",
    "per_request_timeout_sec", "retry_on_status_codes",
    "max_total_retry_time_sec", "max_concurrent_in_flight_requests",
    "abort_run_after_consecutive_504s", "applies_to",
}

FORBIDDEN_SUBSTRINGS = ("prompt", "gold", "expected_argument",
                       "argument_value", "raw_response", "raw_payload", "scorer_diff")
ATTESTATION_ALLOWLIST = {
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return "sha256:" + h.hexdigest()


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


def _load_yaml_minimal(path: Path) -> dict:
    """Minimal YAML loader using PyYAML if available, else fail loudly."""
    try:
        import yaml  # type: ignore
    except ImportError as e:
        raise RuntimeError(f"pyyaml_required:{e}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"yaml_root_not_dict:{path}")
    return data


def validate_policy(policy: dict, runtime_timeout_sec: int) -> tuple[dict, list]:
    blockers = []
    v = {}
    v["policy_block_present"] = isinstance(policy, dict) and bool(policy)
    if not v["policy_block_present"]:
        blockers.append("policy_block_missing_or_empty")
        return v, blockers
    extra = set(policy.keys()) - ALLOWED_POLICY_KEYS
    v["policy_keys_within_whitelist"] = not extra
    if extra:
        blockers.append("policy_extra_keys:" + ",".join(sorted(extra)))
    v["policy_enabled_is_false"] = policy.get("enabled") is False
    if not v["policy_enabled_is_false"]:
        blockers.append("policy_enabled_not_false")
    # Bounds
    bounds_ok = True
    for key, (lo, hi) in BOUNDS.items():
        if key in {"max_total_retry_time_sec", "max_concurrent_in_flight_requests", "abort_run_after_consecutive_504s"}:
            continue  # checked in hard_caps section
        val = policy.get(key)
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            bounds_ok = False
            blockers.append(f"{key}_not_numeric")
        elif not (lo <= val <= hi):
            bounds_ok = False
            blockers.append(f"{key}_out_of_bounds:{val}_not_in_[{lo},{hi}]")
    v["bounds_checks_passed"] = bounds_ok
    # jitter
    v["jitter_strategy_valid"] = policy.get("jitter_strategy") in ALLOWED_JITTER
    if not v["jitter_strategy_valid"]:
        blockers.append("jitter_strategy_invalid:" + str(policy.get("jitter_strategy")))
    # retry codes
    codes = policy.get("retry_on_status_codes")
    v["retry_status_codes_subset"] = (
        isinstance(codes, list) and bool(codes)
        and all(isinstance(c, int) for c in codes)
        and set(codes).issubset(ALLOWED_RETRY_CODES)
    )
    if not v["retry_status_codes_subset"]:
        blockers.append("retry_on_status_codes_invalid")
    # per_request_timeout vs runtime.timeout_sec
    prt = policy.get("per_request_timeout_sec")
    v["per_request_timeout_under_runtime_timeout"] = (
        isinstance(prt, (int, float)) and not isinstance(prt, bool)
        and isinstance(runtime_timeout_sec, (int, float))
        and prt < runtime_timeout_sec
    )
    if not v["per_request_timeout_under_runtime_timeout"]:
        blockers.append(f"per_request_timeout_not_less_than_runtime_timeout:{prt}_vs_{runtime_timeout_sec}")
    # hard_caps
    hc = policy.get("hard_caps") if isinstance(policy.get("hard_caps"), dict) else {}
    v["hard_caps_present"] = bool(hc)
    if not v["hard_caps_present"]:
        blockers.append("hard_caps_missing")
    extra_hc = set(hc.keys()) - ALLOWED_HARD_CAP_KEYS
    v["hard_caps_within_whitelist"] = not extra_hc
    if extra_hc:
        blockers.append("hard_caps_extra_keys:" + ",".join(sorted(extra_hc)))
    for key in ALLOWED_HARD_CAP_KEYS:
        val = hc.get(key)
        lo, hi = BOUNDS[key]
        if not isinstance(val, int) or isinstance(val, bool):
            blockers.append(f"hard_cap_{key}_not_int")
        elif not (lo <= val <= hi):
            blockers.append(f"hard_cap_{key}_out_of_bounds:{val}_not_in_[{lo},{hi}]")
    # applies_to
    at = policy.get("applies_to")
    v["applies_to_present_and_nonempty"] = isinstance(at, list) and bool(at)
    if not v["applies_to_present_and_nonempty"]:
        blockers.append("applies_to_missing_or_empty")
    # authorization attestations
    auth_keys = [
        "provider_calls_authorized_by_this_policy",
        "bfcl_generate_authorized_by_this_policy",
        "bfcl_evaluate_authorized_by_this_policy",
        "scorer_authorized_by_this_policy",
        "performance_evidence_authorized_by_this_policy",
        "archive_update_authorized_by_this_policy",
        "holdout_authorized_by_this_policy",
        "full_suite_authorized_by_this_policy",
        "huawei_acceptance_authorized_by_this_policy",
        "sota_3pp_claim_authorized_by_this_policy",
    ]
    all_false = all(policy.get(k) is False for k in auth_keys)
    v["authorization_attestations_all_false"] = all_false
    if not all_false:
        blockers.append("authorization_attestation_not_all_false")
    return v, blockers


def build(strict: bool) -> dict:
    policy_yaml = _load_yaml_minimal(POLICY_YAML)
    runtime_yaml = _load_yaml_minimal(RUNTIME_YAML)
    policy = policy_yaml.get("provider_transport_backoff_policy") or {}
    runtime_timeout_sec = runtime_yaml.get("timeout_sec")
    validation, blockers = validate_policy(policy, runtime_timeout_sec)
    summary = {
        "policy_schema_version": policy.get("schema_version"),
        "max_retries": policy.get("max_retries"),
        "initial_delay_ms": policy.get("initial_delay_ms"),
        "max_delay_ms": policy.get("max_delay_ms"),
        "multiplier": policy.get("multiplier"),
        "jitter_strategy": policy.get("jitter_strategy"),
        "per_request_timeout_sec": policy.get("per_request_timeout_sec"),
        "retry_on_status_codes": list(policy.get("retry_on_status_codes") or []),
        "max_total_retry_time_sec": (policy.get("hard_caps") or {}).get("max_total_retry_time_sec"),
        "max_concurrent_in_flight_requests": (policy.get("hard_caps") or {}).get("max_concurrent_in_flight_requests"),
        "abort_run_after_consecutive_504s": (policy.get("hard_caps") or {}).get("abort_run_after_consecutive_504s"),
        "applies_to": list(policy.get("applies_to") or []),
    }
    artifact = {
        "artifact_kind": "abhe_v0_provider_transport_backoff_policy",
        "schema_version": "abhe_v0_provider_transport_backoff_policy_v0",
        "run_scope": "offline_declarative_policy_validation_only_no_provider_no_proxy_wiring",
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
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "policy_enabled": bool(policy.get("enabled", False)),
        "policy_wired_into_proxy": False,
        "huawei_acceptance_ready": False,
        "sota_3pp_claim_ready": False,
        "source_policy_yaml_path": str(POLICY_YAML.relative_to(REPO_ROOT)),
        "source_policy_yaml_sha256": _sha256(POLICY_YAML),
        "source_runtime_yaml_path": str(RUNTIME_YAML.relative_to(REPO_ROOT)),
        "source_runtime_yaml_sha256": _sha256(RUNTIME_YAML),
        "runtime_timeout_sec": runtime_timeout_sec,
        "policy_per_request_timeout_sec": policy.get("per_request_timeout_sec"),
        "policy_summary": summary,
        "validation": validation,
        "blockers": blockers,
    }
    if strict:
        bad = set(artifact.keys()) - ALLOWED_TOP_KEYS
        if bad:
            raise ValueError("non_whitelisted_top_keys:" + ",".join(sorted(bad)))
        sbad = set(summary.keys()) - ALLOWED_SUMMARY_KEYS
        if sbad:
            raise ValueError("non_whitelisted_summary_keys:" + ",".join(sorted(sbad)))
        vbad = set(validation.keys()) - ALLOWED_VALIDATION_KEYS
        if vbad:
            raise ValueError("non_whitelisted_validation_keys:" + ",".join(sorted(vbad)))
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
        print(json.dumps({
            "abhe_v0_provider_transport_backoff_policy_passed": (
                not art["blockers"]
                and art["policy_enabled"] is False
                and art["policy_wired_into_proxy"] is False
                and all(art["validation"].values())
            ),
            "policy_enabled": art["policy_enabled"],
            "policy_wired_into_proxy": art["policy_wired_into_proxy"],
            "blockers": art["blockers"],
            "report_scope": "abhe_v0_provider_transport_backoff_policy_build",
        }, ensure_ascii=False))
    else:
        print(json.dumps(art, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
