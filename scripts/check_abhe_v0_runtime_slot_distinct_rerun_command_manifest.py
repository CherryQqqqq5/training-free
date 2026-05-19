#!/usr/bin/env python3
"""Check the active command manifest for the ABHE runtime-slot distinct rerun."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT = ROOT / "abhe_v0_runtime_slot_controller_distinct_rerun_command_manifest.json"
EXPECTED_HASH = "sha256:9b26ba3d24c54562f6a5058877a24f15d2e4ef71ee9ea781bcae168307f7d14c"
EXPECTED_ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]
EXPECTED_SCOPE = "scorer_unit_distinct_bounded_residual_dev_smoke_only"
EXPECTED_MANIFEST = "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json"
EXPECTED_APPROVAL = "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_distinct_rerun_approval_packet.json"


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_distinct_rerun_command_manifest":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_distinct_rerun_command_manifest_v0":
        blockers.append("schema_version_invalid")
    if data.get("approval_scope") != EXPECTED_SCOPE:
        blockers.append("approval_scope_invalid")
    if data.get("approved_selected_case_ids_hash") != EXPECTED_HASH:
        blockers.append("selected_case_ids_hash_invalid")
    if data.get("approved_selected_case_count") != 48:
        blockers.append("selected_case_count_invalid")
    if data.get("approved_manifest_path") != EXPECTED_MANIFEST:
        blockers.append("manifest_path_invalid")
    if data.get("approved_approval_packet_path") != EXPECTED_APPROVAL:
        blockers.append("approval_packet_path_invalid")
    if data.get("approved_arms") != EXPECTED_ARMS:
        blockers.append("approved_arms_invalid")
    for key in ["tmux_required", "single_run_per_arm", "compact_only", "raw_material_absent"]:
        if data.get(key) is not True:
            blockers.append("%s_not_true" % key)
    for key in ["raw_provider_payload_committed", "raw_bfcl_result_tree_committed", "gold_expected_committed", "scorer_diff_committed", "holdout_touched", "full_suite_touched", "archive_update_authorized", "performance_claim_authorized", "performance_evidence"]:
        if data.get(key) is not False:
            blockers.append("%s_not_false" % key)
    commands = data.get("commands") if isinstance(data.get("commands"), list) else []
    if [row.get("arm") for row in commands if isinstance(row, dict)] != EXPECTED_ARMS:
        blockers.append("command_arms_invalid")
    for row in commands:
        if not isinstance(row, dict):
            blockers.append("command_row_invalid")
            continue
        cmd = str(row.get("command") or "")
        arm = row.get("arm")
        required_parts = ["--execute-approved", "--approval-packet %s" % EXPECTED_APPROVAL, "--manifest %s" % EXPECTED_MANIFEST, "--compact-only", "--arm %s" % arm]
        for part in required_parts:
            if part not in cmd:
                blockers.append("command_missing:%s:%s" % (arm, part))
        if "--dry-run" in cmd:
            blockers.append("execute_command_contains_dry_run:%s" % arm)
        expected_out = "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_distinct_rerun_%s_arm_compact.json" % arm
        if row.get("compact_output_path") != expected_out:
            blockers.append("compact_output_path_invalid:%s" % arm)
    blockers.extend(scan_value(data, label="abhe_v0_runtime_slot_controller_distinct_rerun_command_manifest"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    if not path.exists():
        return {"report_scope": "abhe_v0_runtime_slot_controller_distinct_rerun_command_manifest_check", "command_manifest_present": False, "command_manifest_passed": False, "blockers": ["command_manifest_missing"], "performance_evidence": False}
    data = _load(path)
    blockers = validate(data)
    return {"report_scope": "abhe_v0_runtime_slot_controller_distinct_rerun_command_manifest_check", "command_manifest_path": str(path), "command_manifest_present": True, "command_manifest_passed": not blockers, "approved_selected_case_ids_hash": data.get("approved_selected_case_ids_hash"), "approved_arms": data.get("approved_arms"), "performance_evidence": data.get("performance_evidence", False), "blockers": blockers}


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = check(args.path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {"report_scope": "abhe_v0_runtime_slot_controller_distinct_rerun_command_manifest_check", "command_manifest_passed": False, "blockers": ["load_failed:%s" % exc.__class__.__name__], "performance_evidence": False}
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report.get("command_manifest_passed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
