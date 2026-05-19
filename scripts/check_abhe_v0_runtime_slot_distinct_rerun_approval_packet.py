#!/usr/bin/env python3
"""Check the approved ABHE runtime-slot scorer-unit-distinct bounded rerun packet."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value
from scripts.check_abhe_v0_runtime_slot_distinct_rerun_request import check as check_request
from scripts.check_abhe_v0_runtime_slot_scorer_unit_distinct_slice import check as check_distinct_slice
from scripts.check_abhe_v0_runtime_slot_distinct_rerun_command_manifest import check as check_command_manifest

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_PACKET = ROOT / "abhe_v0_runtime_slot_controller_distinct_rerun_approval_packet.json"
EXPECTED_HASH = "sha256:9b26ba3d24c54562f6a5058877a24f15d2e4ef71ee9ea781bcae168307f7d14c"
EXPECTED_SCOPE = "scorer_unit_distinct_bounded_residual_dev_smoke_only"
EXPECTED_PROVIDER = "ToolCallingFunction/OpenAICompatible"
EXPECTED_PROFILE = "toolcallingfunction"
EXPECTED_MODEL = "gpt-4.1"
EXPECTED_ROUTE_POLICY = "toolcallingfunction_openai_compatible_only_openrouter_disabled"
EXPECTED_PROTOCOL = "bfcl_v4_abhe_v0_scorer_unit_distinct_bounded_residual_dev_smoke_toolcallingfunction"
EXPECTED_ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]
REQUIRED_TRUE = ["authorized", "provider_calls_authorized", "bfcl_generate_authorized", "bfcl_evaluate_authorized", "scorer_authorized"]
FORCED_FALSE = ["holdout_authorized", "full_suite_authorized", "archive_update_authorized", "performance_claim_authorized", "performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready"]
BOUNDARY_FALSE = ["raw_outputs_committed", "raw_provider_payload_committed", "raw_bfcl_result_tree_committed", "gold_expected_committed", "scorer_diff_committed"]
REQUIRED_STOP_LOSS = {"raw_leakage", "provider_model_protocol_mismatch", "case_list_hash_mismatch", "scorer_unit_alignment_mismatch", "runner_manifest_incompatible", "runtime_config_missing_or_mismatch", "cost_latency_cap_exceeded", "regression_cap_exceeded", "scorer_artifact_schema_failure"}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _load_if_exists(path_value: Any, blockers: List[str], missing_blocker: str) -> Dict[str, Any]:
    if not path_value:
        blockers.append(missing_blocker)
        return {}
    path = Path(str(path_value))
    if not path.exists():
        blockers.append(missing_blocker)
        return {}
    return _load(path)


def validate_packet(packet: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if packet.get("artifact_kind") != "abhe_v0_runtime_slot_controller_distinct_rerun_approval_packet":
        blockers.append("artifact_kind_invalid")
    if packet.get("schema_version") != "abhe_v0_runtime_slot_controller_distinct_rerun_approval_packet_v0":
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
    if packet.get("approved_selected_case_ids_hash") != EXPECTED_HASH:
        blockers.append("approved_selected_case_ids_hash_invalid")
    if packet.get("approved_selected_case_count") != 48:
        blockers.append("approved_selected_case_count_invalid")
    if packet.get("approved_target_category") != "multi_turn_miss_param":
        blockers.append("approved_target_category_invalid")
    if packet.get("approved_target_selected_compact_case_count") != 24:
        blockers.append("approved_target_selected_compact_case_count_invalid")
    if packet.get("approved_target_unique_scorer_unit_count") != 24:
        blockers.append("approved_target_unique_scorer_unit_count_invalid")
    if packet.get("approved_target_compact_to_scorer_unit_factor") != 1.0:
        blockers.append("approved_target_compact_to_scorer_unit_factor_invalid")
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
    if packet.get("scorer_authorization_scope") != EXPECTED_SCOPE:
        blockers.append("scorer_authorization_scope_invalid")
    runtime_config = Path(str(packet.get("approved_runtime_config_path") or ""))
    if not packet.get("approved_runtime_config_path"):
        blockers.append("runtime_config_not_selected")
    elif not runtime_config.exists():
        blockers.append("runtime_config_path_missing")
    boundary = packet.get("artifact_boundary")
    if not isinstance(boundary, dict):
        blockers.append("artifact_boundary_missing")
    else:
        if boundary.get("compact_only") is not True:
            blockers.append("artifact_boundary_compact_only_not_true")
        for key in BOUNDARY_FALSE:
            if boundary.get(key) is not False:
                blockers.append("artifact_boundary_%s_not_false" % key)
    if not REQUIRED_STOP_LOSS.issubset(set(packet.get("stop_loss") or [])):
        blockers.append("stop_loss_incomplete")

    distinct = check_distinct_slice(Path(str(packet.get("approved_manifest_path") or "")))
    if distinct.get("scorer_unit_distinct_slice_check_passed") is not True:
        blockers.append("distinct_slice_check_not_passed")
    if distinct.get("selected_case_ids_hash") != packet.get("approved_selected_case_ids_hash"):
        blockers.append("distinct_slice_hash_mismatch")
    if distinct.get("selected_case_count") != packet.get("approved_selected_case_count"):
        blockers.append("distinct_slice_case_count_mismatch")
    if distinct.get("target_unique_scorer_unit_count") != packet.get("approved_target_unique_scorer_unit_count"):
        blockers.append("distinct_slice_target_unit_count_mismatch")
    if distinct.get("target_compact_to_scorer_unit_factor") != 1.0:
        blockers.append("distinct_slice_target_not_one_to_one")

    request = check_request(Path(str(packet.get("approved_request_path") or "")))
    if request.get("distinct_rerun_request_passed") is not True:
        blockers.append("distinct_rerun_request_not_passed")
    if request.get("authorized") is not False:
        blockers.append("request_not_pending_unapproved")
    if request.get("runner_manifest_compatible") is not True:
        blockers.append("request_runner_manifest_not_compatible")
    if request.get("selected_case_ids_hash") != packet.get("approved_selected_case_ids_hash"):
        blockers.append("request_selected_hash_mismatch")

    command = check_command_manifest(Path(str(packet.get("approved_command_manifest_path") or "")))
    if command.get("command_manifest_passed") is not True:
        blockers.append("command_manifest_not_passed")
    if command.get("approved_selected_case_ids_hash") != packet.get("approved_selected_case_ids_hash"):
        blockers.append("command_manifest_selected_hash_mismatch")
    if command.get("approved_arms") != packet.get("approved_arms"):
        blockers.append("command_manifest_arms_mismatch")

    dry_run = _load_if_exists(packet.get("approved_dry_run_manifest_path"), blockers, "dry_run_manifest_missing")
    if dry_run:
        if dry_run.get("artifact_kind") != "abhe_v0_runtime_slot_controller_distinct_rerun_dry_run_manifest":
            blockers.append("dry_run_artifact_kind_invalid")
        if dry_run.get("runner_manifest_compatible") is not True:
            blockers.append("dry_run_runner_manifest_not_compatible")
        if dry_run.get("selected_case_ids_hash") != packet.get("approved_selected_case_ids_hash"):
            blockers.append("dry_run_selected_hash_mismatch")
        for key in ["execution_started", "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called", "scorer_called", "holdout_touched", "full_suite_touched", "archive_updated", "performance_evidence"]:
            if dry_run.get(key) is not False:
                blockers.append("dry_run_%s_not_false" % key)
    blockers.extend(scan_value(packet, label="abhe_v0_runtime_slot_controller_distinct_rerun_approval_packet"))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET) -> Dict[str, Any]:
    if not packet_path.exists():
        return {"report_scope": "abhe_v0_runtime_slot_controller_distinct_rerun_approval_packet_check", "packet_path": str(packet_path), "packet_present": False, "approval_packet_passed": False, "blockers": ["distinct_rerun_approval_packet_missing"], "performance_evidence": False}
    packet = _load(packet_path)
    blockers = validate_packet(packet)
    return {
        "report_scope": "abhe_v0_runtime_slot_controller_distinct_rerun_approval_packet_check",
        "packet_path": str(packet_path),
        "packet_present": True,
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "approval_scope": packet.get("approval_scope"),
        "approved_provider": packet.get("approved_provider"),
        "approved_profile": packet.get("approved_profile"),
        "approved_model": packet.get("approved_model"),
        "approved_protocol": packet.get("approved_protocol"),
        "approved_selected_case_ids_hash": packet.get("approved_selected_case_ids_hash"),
        "approved_selected_case_count": packet.get("approved_selected_case_count"),
        "approved_target_unique_scorer_unit_count": packet.get("approved_target_unique_scorer_unit_count"),
        "approved_target_compact_to_scorer_unit_factor": packet.get("approved_target_compact_to_scorer_unit_factor"),
        "scorer_authorized": packet.get("scorer_authorized") is True,
        "scorer_authorization_scope": packet.get("scorer_authorization_scope"),
        "holdout_authorized": packet.get("holdout_authorized"),
        "full_suite_authorized": packet.get("full_suite_authorized"),
        "archive_update_authorized": packet.get("archive_update_authorized"),
        "performance_claim_authorized": packet.get("performance_claim_authorized"),
        "performance_evidence": packet.get("performance_evidence", False),
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
        summary = {"report_scope": "abhe_v0_runtime_slot_controller_distinct_rerun_approval_packet_check", "approval_packet_passed": False, "blockers": ["load_failed:%s" % exc.__class__.__name__], "performance_evidence": False}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 1 if args.strict and not summary.get("approval_packet_passed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
