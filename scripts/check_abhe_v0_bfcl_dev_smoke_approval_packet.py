#!/usr/bin/env python3
"""Check the approved ABHE-v0 bounded BFCL dev smoke packet.

This checker validates approval packet structure and static artifact boundaries.
Provider environment/preflight and runner executability are reported by
check_abhe_v0_bfcl_execution_readiness.py so a structurally valid approval can
still fail closed before execution.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_packet.json")
DEFAULT_FRESH_MANIFEST = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_manifest.json")
DEFAULT_CANDIDATES = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_materialized_candidates.json")
EXPECTED_HASH = "sha256:8e28826895c76afd14fb2ec07550b871ea50df25c0666881dad39be86450991f"
EXPECTED_ENTRIES = ["state_tracking_v0", "hallucination_abstain_v0"]
EXPECTED_PROVIDER = "ToolCallingFunction/OpenAICompatible"
EXPECTED_PROFILE = "toolcallingfunction"
EXPECTED_MODEL = "gpt-4.1"
EXPECTED_ROUTE_POLICY = "toolcallingfunction_openai_compatible_only_openrouter_disabled"
EXPECTED_PROTOCOL = "bfcl_v4_abhe_v0_bounded_paired_dev_smoke_toolcallingfunction"
EXPECTED_SCOPE = "bounded_dev_smoke_only"
REQUIRED_STOP_LOSS = {
    "provider_preflight_failed",
    "provider_model_protocol_mismatch",
    "case_list_hash_mismatch",
    "candidate_artifact_hash_mismatch",
    "runtime_config_missing_or_mismatch",
    "raw_leakage",
    "cost_latency_cap_exceeded",
    "regression_cap_exceeded",
    "scorer_artifact_schema_failure",
}
FORCED_FALSE = [
    "holdout_authorized",
    "full_suite_authorized",
    "archive_update_authorized",
    "performance_claim_authorized",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
]
REQUIRED_TRUE = [
    "authorized",
    "baseline_arm_authorized",
    "candidate_arm_authorized",
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
]
BOUNDARY_FALSE = [
    "raw_outputs_committed",
    "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed",
    "gold_expected_committed",
    "scorer_diff_committed",
]


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _validate_manifest(packet: Dict[str, Any], manifest_path: Path) -> List[str]:
    blockers: List[str] = []
    if not manifest_path.exists():
        return ["fresh_slice_manifest_missing"]
    manifest = _load(manifest_path)
    if manifest.get("fresh_dev_slice_materialized") is not True:
        blockers.append("fresh_slice_not_materialized")
    if manifest.get("selected_case_ids_hash") != packet.get("approved_fresh_dev_slice_hash"):
        blockers.append("fresh_slice_hash_mismatch")
    if manifest.get("selected_case_count") != packet.get("approved_case_count"):
        blockers.append("fresh_slice_case_count_mismatch")
    if manifest.get("selected_case_count") != 20:
        blockers.append("fresh_slice_case_count_not_20")
    for key in ["raw_cases_persisted", "gold_expected_persisted", "scorer_diff_persisted", "performance_evidence"]:
        if manifest.get(key) is not False:
            blockers.append("fresh_slice_%s_not_false" % key)
    return blockers


def _validate_candidates(packet: Dict[str, Any], candidates_path: Path) -> List[str]:
    blockers: List[str] = []
    if not candidates_path.exists():
        return ["materialized_candidates_missing"]
    candidates = _load(candidates_path)
    if candidates.get("candidate_materialized") is not True:
        blockers.append("candidate_not_materialized")
    if candidates.get("selected_case_ids_hash") != packet.get("approved_fresh_dev_slice_hash"):
        blockers.append("candidate_selected_hash_mismatch")
    if set(row.get("entry_id") for row in candidates.get("candidates", []) if isinstance(row, dict)) != set(EXPECTED_ENTRIES):
        blockers.append("candidate_entry_ids_invalid")
    for key in ["candidate_rule_generated", "candidate_yaml_generated", "candidate_jsonl_generated", "candidate_pool_ready", "performance_evidence"]:
        if candidates.get(key) is not False:
            blockers.append("candidate_%s_not_false" % key)
    if str(candidates_path) != packet.get("approved_candidate_artifact"):
        blockers.append("approved_candidate_artifact_path_mismatch")
    return blockers


def validate_packet(packet: Dict[str, Any], *, packet_path: Path = DEFAULT_PACKET) -> List[str]:
    blockers: List[str] = []
    if packet.get("artifact_kind") != "abhe_v0_bfcl_dev_smoke_approval_packet":
        blockers.append("artifact_kind_invalid")
    if packet.get("schema_version") != "abhe_v0_bfcl_dev_smoke_approval_packet_v0":
        blockers.append("schema_version_invalid")
    if packet.get("approval_status") != "approved":
        blockers.append("approval_status_not_approved")
    if packet.get("approval_scope") != EXPECTED_SCOPE:
        blockers.append("approval_scope_invalid")
    for key in REQUIRED_TRUE:
        if packet.get(key) is not True:
            blockers.append("%s_not_true" % key)
    for key in FORCED_FALSE:
        if packet.get(key) is not False:
            blockers.append("%s_not_false" % key)
    if packet.get("approved_entry_ids") != EXPECTED_ENTRIES:
        blockers.append("approved_entry_ids_invalid")
    if packet.get("approved_case_count") != 20:
        blockers.append("approved_case_count_not_20")
    if packet.get("approved_fresh_dev_slice_hash") != EXPECTED_HASH:
        blockers.append("approved_fresh_dev_slice_hash_invalid")
    if packet.get("approved_dataset_path") != ".venv/lib/python3.10/site-packages/bfcl_eval/data":
        blockers.append("approved_dataset_path_invalid")
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
    runtime_config = Path(str(packet.get("approved_runtime_config_path") or ""))
    if not packet.get("approved_runtime_config_path"):
        blockers.append("runtime_config_not_selected")
    elif not runtime_config.exists():
        blockers.append("runtime_config_path_missing")
    if packet.get("scorer_authorization_scope") != EXPECTED_SCOPE:
        blockers.append("scorer_authorization_scope_invalid")
    boundary = packet.get("artifact_boundary")
    if not isinstance(boundary, dict):
        blockers.append("artifact_boundary_missing")
    else:
        if boundary.get("compact_only") is not True:
            blockers.append("artifact_boundary_compact_only_not_true")
        for key in BOUNDARY_FALSE:
            if boundary.get(key) is not False:
                blockers.append("artifact_boundary_%s_not_false" % key)
    stop_loss = set(packet.get("stop_loss") or [])
    if not REQUIRED_STOP_LOSS.issubset(stop_loss):
        blockers.append("stop_loss_incomplete")
    blockers.extend(_validate_manifest(packet, Path(str(packet.get("approved_fresh_slice_manifest") or DEFAULT_FRESH_MANIFEST))))
    blockers.extend(_validate_candidates(packet, Path(str(packet.get("approved_candidate_artifact") or DEFAULT_CANDIDATES))))
    blockers.extend(scan_value(packet, label="abhe_v0_bfcl_dev_smoke_approval_packet"))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET) -> Dict[str, Any]:
    if not packet_path.exists():
        return {
            "report_scope": "abhe_v0_bfcl_dev_smoke_approval_packet_check",
            "packet_path": str(packet_path),
            "packet_present": False,
            "approval_packet_passed": False,
            "blockers": ["dev_smoke_approval_packet_missing"],
        }
    packet = _load(packet_path)
    blockers = validate_packet(packet, packet_path=packet_path)
    return {
        "report_scope": "abhe_v0_bfcl_dev_smoke_approval_packet_check",
        "packet_path": str(packet_path),
        "packet_present": True,
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "approval_scope": packet.get("approval_scope"),
        "approved_provider": packet.get("approved_provider"),
        "approved_profile": packet.get("approved_profile"),
        "approved_model": packet.get("approved_model"),
        "approved_protocol": packet.get("approved_protocol"),
        "approved_runtime_config_path": packet.get("approved_runtime_config_path"),
        "scorer_authorized": packet.get("scorer_authorized") is True,
        "scorer_authorization_scope": packet.get("scorer_authorization_scope"),
        "holdout_authorized": packet.get("holdout_authorized"),
        "full_suite_authorized": packet.get("full_suite_authorized"),
        "archive_update_authorized": packet.get("archive_update_authorized"),
        "performance_claim_authorized": packet.get("performance_claim_authorized"),
        "approval_packet_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "abhe_v0_bfcl_dev_smoke_approval_packet_check",
            "approval_packet_passed": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 1 if args.strict and not summary.get("approval_packet_passed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
