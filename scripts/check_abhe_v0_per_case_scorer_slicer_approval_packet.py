#!/usr/bin/env python3
"""
check_abhe_v0_per_case_scorer_slicer_approval_packet
=====================================================

Validates the P1.5b per-case scorer slicer approval packet.

Two modes:
  --strict             exit 1 unless approval_status=='approved' AND
                       every required-true field is true AND every
                       forced-false field is false AND every signature
                       field is filled (no '<unsigned>' or null sentinels)
  (default, no flag)   exit 0; report blockers as data

By design: while the packet ships with approval_status='draft_pending_signature',
strict mode exits 1, which is the correct fail-closed default. Once a human
signs the packet (changes approval_status to 'approved' AND fills the
signature_block fields), strict mode exits 0 and downstream rerun scripts
may proceed.

This script does NOT trigger any provider call, BFCL invocation, or
scorer call. It only reads the packet JSON and validates its shape +
attestations.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACKET = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_approval_packet.json"

EXPECTED_KIND = "abhe_v0_per_case_scorer_slicer_approval_packet"
EXPECTED_SCHEMA = "abhe_v0_per_case_scorer_slicer_approval_packet_v0"
EXPECTED_SCOPE = "per_case_scorer_slicer_bounded_residual_dev_smoke_only"
EXPECTED_PROVIDER = "ToolCallingFunction/OpenAICompatible"
EXPECTED_PROFILE = "toolcallingfunction"
EXPECTED_MODEL = "gpt-4.1"
EXPECTED_ROUTE_POLICY = "toolcallingfunction_openai_compatible_only_openrouter_disabled"
EXPECTED_PROTOCOL = "bfcl_v4_abhe_v0_per_case_scorer_slicer_bounded_residual_dev_smoke_toolcallingfunction"
EXPECTED_HASH = "sha256:9b26ba3d24c54562f6a5058877a24f15d2e4ef71ee9ea781bcae168307f7d14c"
EXPECTED_ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]

# Required-true under approval_status='approved' (when signed). These are the
# specific authorizations the packet would grant.
AUTHORIZATION_FIELDS = [
    "authorized",
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "per_case_scorer_invocation_authorized",
]

# ALWAYS forced false (boundary discipline). Even when signed.
FORCED_FALSE = [
    "holdout_authorized",
    "full_suite_authorized",
    "archive_update_authorized",
    "performance_claim_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "raw_outputs_committed",
    "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed",
    "gold_expected_committed",
    "scorer_diff_committed",
    "prompt_literal_committed",
    "argument_values_committed",
]

REQUIRED_STOP_LOSS = {
    "raw_leakage",
    "provider_model_protocol_mismatch",
    "case_list_hash_mismatch",
    "scorer_unit_alignment_mismatch",
    "runner_manifest_incompatible",
    "runtime_config_missing_or_mismatch",
    "cost_latency_cap_exceeded",
    "regression_cap_exceeded",
    "scorer_artifact_schema_failure",
    "per_case_scorer_call_count_mismatch",
    "provider_504_rate_exceeded",
}

REQUIRED_SIGNATURE_FIELDS = [
    "signed_by",
    "signed_at_iso8601_utc",
    "signed_at_commit_sha",
    "cost_latency_cap_token_budget",
    "cost_latency_cap_wall_clock_s",
    "regression_cap_error_class_delta_max_cases",
    "cost_amplification_cap_factor",
    "provider_504_rate_cap_pct",
]


def _is_filled(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, str) and val.strip() in ("", "<unsigned>"):
        return False
    return True


def validate_packet(packet: Dict[str, Any], require_signed: bool) -> List[str]:
    blockers: List[str] = []

    if packet.get("artifact_kind") != EXPECTED_KIND:
        blockers.append("artifact_kind_invalid")
    if packet.get("schema_version") != EXPECTED_SCHEMA:
        blockers.append("schema_version_invalid")

    status = packet.get("approval_status")
    if status not in {"draft_pending_signature", "approved", "rejected"}:
        blockers.append("approval_status_invalid")

    if packet.get("approval_scope") != EXPECTED_SCOPE:
        blockers.append("approval_scope_invalid")

    # Authorization rules:
    #   draft_pending_signature OR rejected -> all AUTHORIZATION_FIELDS must be False
    #   approved                            -> all AUTHORIZATION_FIELDS must be True
    if status in ("draft_pending_signature", "rejected"):
        for k in AUTHORIZATION_FIELDS:
            if packet.get(k) is not False:
                blockers.append(f"{k}_must_be_false_while_{status}")
    elif status == "approved":
        for k in AUTHORIZATION_FIELDS:
            if packet.get(k) is not True:
                blockers.append(f"{k}_must_be_true_when_approved")

    # FORCED_FALSE always
    for k in FORCED_FALSE:
        if packet.get(k) is not False:
            blockers.append(f"{k}_not_false")

    # Hash / counts / scope identity
    if packet.get("approved_selected_case_ids_hash") != EXPECTED_HASH:
        blockers.append("approved_selected_case_ids_hash_invalid")
    if packet.get("approved_selected_case_count") != 48:
        blockers.append("approved_selected_case_count_invalid")
    if packet.get("approved_target_category") != "multi_turn_miss_param":
        blockers.append("approved_target_category_invalid")
    if packet.get("approved_target_selected_compact_case_count") != 24:
        blockers.append("approved_target_selected_compact_case_count_invalid")
    if packet.get("approved_target_unique_scorer_unit_count_post_slicing") != 24:
        blockers.append("approved_target_unique_scorer_unit_count_post_slicing_invalid")
    if packet.get("approved_target_compact_to_scorer_unit_factor_post_slicing") != 1.0:
        blockers.append("approved_target_compact_to_scorer_unit_factor_post_slicing_invalid")
    if packet.get("approved_provider") != EXPECTED_PROVIDER:
        blockers.append("approved_provider_invalid")
    if packet.get("approved_profile") != EXPECTED_PROFILE:
        blockers.append("approved_profile_invalid")
    if packet.get("approved_model") != EXPECTED_MODEL:
        blockers.append("approved_model_invalid")
    if packet.get("approved_provider_route_policy") != EXPECTED_ROUTE_POLICY:
        blockers.append("approved_provider_route_policy_invalid")
    if packet.get("approved_protocol") != EXPECTED_PROTOCOL:
        blockers.append("approved_protocol_invalid")
    if packet.get("approved_arms") != EXPECTED_ARMS:
        blockers.append("approved_arms_invalid")

    # Runtime config path exists
    rt = packet.get("approved_runtime_config_path")
    if not rt:
        blockers.append("approved_runtime_config_path_missing")
    else:
        if not (REPO_ROOT / rt).exists():
            blockers.append("approved_runtime_config_path_not_on_disk")

    # Stop-loss set
    stop_loss = packet.get("stop_loss")
    if not isinstance(stop_loss, list) or not REQUIRED_STOP_LOSS.issubset(set(stop_loss)):
        blockers.append("stop_loss_incomplete")

    # Artifact boundary block
    boundary = packet.get("artifact_boundary")
    if not isinstance(boundary, dict):
        blockers.append("artifact_boundary_missing")
    else:
        if boundary.get("compact_only") is not True:
            blockers.append("artifact_boundary_compact_only_not_true")
        for k in ["raw_outputs_committed", "raw_provider_payload_committed",
                  "raw_bfcl_result_tree_committed", "gold_expected_committed",
                  "scorer_diff_committed", "prompt_literal_committed",
                  "argument_values_committed"]:
            if boundary.get(k) is not False:
                blockers.append(f"artifact_boundary_{k}_not_false")

    # Pre-rerun dependencies
    pre = packet.get("pre_rerun_dependencies")
    if not isinstance(pre, dict):
        blockers.append("pre_rerun_dependencies_missing")
    else:
        for k in ["p2_v3_skeleton_merged", "p3_backoff_policy_declarative_only_merged",
                  "same_case_id_hash_as_p1", "p1_score_adapter_artifact_present"]:
            if pre.get(k) is not True:
                blockers.append(f"pre_rerun_dependencies_{k}_not_true")
        if pre.get("p3_backoff_policy_wired_into_proxy") is not False:
            blockers.append("pre_rerun_dependencies_p3_backoff_policy_wired_into_proxy_not_false")

    # Signature block
    sig = packet.get("signature_block")
    if not isinstance(sig, dict):
        blockers.append("signature_block_missing")
    else:
        for f in REQUIRED_SIGNATURE_FIELDS:
            if f not in sig:
                blockers.append(f"signature_field_{f}_missing")
            elif require_signed and not _is_filled(sig.get(f)):
                blockers.append(f"signature_field_{f}_unsigned_or_null")
        # numeric caps must be positive when present
        for f in ["cost_latency_cap_token_budget", "cost_latency_cap_wall_clock_s",
                  "regression_cap_error_class_delta_max_cases",
                  "cost_amplification_cap_factor", "provider_504_rate_cap_pct"]:
            v = sig.get(f)
            if v is not None and not isinstance(v, bool) and isinstance(v, (int, float)):
                if v <= 0:
                    blockers.append(f"signature_field_{f}_not_positive")

    # Require: if signed, approval_status must be 'approved'
    if require_signed and status != "approved":
        blockers.append("approval_status_not_approved_in_strict_mode")

    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, strict: bool = False) -> Dict[str, Any]:
    if not packet_path.exists():
        return {
            "report_scope": "abhe_v0_per_case_scorer_slicer_approval_packet_check",
            "packet_path": str(packet_path),
            "packet_present": False,
            "approval_packet_passed": False,
            "blockers": ["approval_packet_missing"],
            "performance_evidence": False,
            "authorized": False,
        }
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "report_scope": "abhe_v0_per_case_scorer_slicer_approval_packet_check",
            "packet_path": str(packet_path),
            "packet_present": True,
            "approval_packet_passed": False,
            "blockers": [f"load_failed:{exc.__class__.__name__}"],
            "performance_evidence": False,
            "authorized": False,
        }
    blockers = validate_packet(packet, require_signed=strict)
    return {
        "report_scope": "abhe_v0_per_case_scorer_slicer_approval_packet_check",
        "packet_path": str(packet_path),
        "packet_present": True,
        "approval_status": packet.get("approval_status"),
        "approval_scope": packet.get("approval_scope"),
        "authorized": packet.get("authorized"),
        "provider_calls_authorized": packet.get("provider_calls_authorized"),
        "bfcl_generate_authorized": packet.get("bfcl_generate_authorized"),
        "bfcl_evaluate_authorized": packet.get("bfcl_evaluate_authorized"),
        "scorer_authorized": packet.get("scorer_authorized"),
        "per_case_scorer_invocation_authorized": packet.get("per_case_scorer_invocation_authorized"),
        "performance_evidence": packet.get("performance_evidence"),
        "huawei_acceptance_ready": packet.get("huawei_acceptance_ready"),
        "sota_3pp_claim_ready": packet.get("sota_3pp_claim_ready"),
        "approved_selected_case_ids_hash": packet.get("approved_selected_case_ids_hash"),
        "approved_target_unique_scorer_unit_count_post_slicing": packet.get("approved_target_unique_scorer_unit_count_post_slicing"),
        "current_target_unique_scorer_unit_count_pre_slicing": packet.get("current_target_unique_scorer_unit_count_pre_slicing"),
        "signature_block": packet.get("signature_block"),
        "approval_packet_passed": not blockers,
        "blockers": blockers,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    summary = check(args.packet, strict=args.strict)
    if args.compact:
        # smaller compact output omits big blocks
        compact = {k: v for k, v in summary.items() if k != "signature_block"}
        print(json.dumps(compact, sort_keys=True))
    else:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if args.strict and not summary.get("approval_packet_passed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
