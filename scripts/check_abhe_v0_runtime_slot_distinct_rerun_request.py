#!/usr/bin/env python3
"""Build/check pending request for ABHE runtime slot scorer-unit-distinct bounded rerun.

This request does not approve execution. It verifies that the new distinct slice
is compact, scorer-unit aligned, and runner-dry-run compatible before any future
bounded BFCL rerun approval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value
from scripts.check_abhe_v0_runtime_slot_scorer_unit_distinct_slice import check as check_distinct_slice

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_REQUEST = ROOT / "abhe_v0_runtime_slot_controller_distinct_rerun_request.json"
DISTINCT_PLAN = ROOT / "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json"
DRY_RUN_MANIFEST = ROOT / "abhe_v0_runtime_slot_controller_distinct_rerun_dry_run_manifest.json"
FORCED_FALSE = [
    "authorized",
    "execution_started",
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "archive_update_authorized",
    "holdout_authorized",
    "full_suite_authorized",
    "performance_claim_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
]
REQUIRED_STOP_LOSS = {
    "raw_leakage",
    "provider_model_protocol_mismatch",
    "case_list_hash_mismatch",
    "scorer_unit_alignment_mismatch",
    "runner_manifest_incompatible",
    "candidate_rule_unapproved",
    "cost_latency_cap_exceeded",
    "regression_cap_exceeded",
    "scorer_artifact_schema_failure",
}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _dry_run_summary() -> Dict[str, Any]:
    if not DRY_RUN_MANIFEST.exists():
        return {"dry_run_manifest_present": False, "runner_manifest_compatible": False, "blockers": ["distinct_rerun_dry_run_manifest_missing"]}
    data = _load(DRY_RUN_MANIFEST)
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_distinct_rerun_dry_run_manifest":
        blockers.append("dry_run_artifact_kind_invalid")
    if data.get("runner_manifest_compatible") is not True:
        blockers.append("runner_manifest_not_compatible")
    for key in ["execution_started", "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called", "scorer_called", "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated"]:
        if data.get(key) is not False:
            blockers.append(f"dry_run_{key}_not_false")
    if data.get("raw_material_absent") is not True:
        blockers.append("dry_run_raw_material_absent_not_true")
    return {
        "dry_run_manifest_present": True,
        "runner_manifest_compatible": data.get("runner_manifest_compatible") is True,
        "dry_run_manifest_path": str(DRY_RUN_MANIFEST),
        "dry_run_checked_arm": data.get("arm"),
        "selected_case_ids_hash": data.get("selected_case_ids_hash"),
        "selected_case_count": data.get("selected_case_count"),
        "category_counts": data.get("category_counts"),
        "blockers": blockers + [str(item) for item in data.get("blockers") or []],
    }


def build_request() -> Dict[str, Any]:
    distinct = check_distinct_slice(DISTINCT_PLAN)
    dry_run = _dry_run_summary()
    selected_hash = distinct.get("selected_case_ids_hash")
    request: Dict[str, Any] = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_distinct_rerun_request",
        "schema_version": "abhe_v0_runtime_slot_controller_distinct_rerun_request_v0",
        "approval_status": "pending",
        "authorized": False,
        "approval_required": True,
        "scope": "scorer_unit_distinct_bounded_residual_dev_smoke_review_only",
        "bounded_dev_smoke_only": True,
        "execution_started": False,
        "selected_case_ids_hash": selected_hash,
        "selected_case_count": distinct.get("selected_case_count"),
        "target_category": "multi_turn_miss_param",
        "target_selected_compact_case_count": distinct.get("target_selected_compact_case_count"),
        "target_unique_scorer_unit_count": distinct.get("target_unique_scorer_unit_count"),
        "target_compact_to_scorer_unit_factor": distinct.get("target_compact_to_scorer_unit_factor"),
        "distinct_slice_plan_path": str(DISTINCT_PLAN),
        "runner_dry_run_manifest_path": str(DRY_RUN_MANIFEST),
        "runner_manifest_compatible": dry_run.get("runner_manifest_compatible") is True,
        "requested_arms": ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"],
        "dry_run_command_template": "PYTHONPATH=.:src .venv/bin/python scripts/run_abhe_v0_runtime_slot_controller_residual_dev_smoke.py --dry-run --arm baseline --manifest outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json --compact-only",
        "future_execute_command_templates": [
            "PYTHONPATH=.:src .venv/bin/python scripts/run_abhe_v0_runtime_slot_controller_residual_dev_smoke.py --execute-approved --arm baseline --manifest outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json --compact-only",
            "PYTHONPATH=.:src .venv/bin/python scripts/run_abhe_v0_runtime_slot_controller_residual_dev_smoke.py --execute-approved --arm conditional_frozen_v2 --manifest outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json --compact-only",
            "PYTHONPATH=.:src .venv/bin/python scripts/run_abhe_v0_runtime_slot_controller_residual_dev_smoke.py --execute-approved --arm runtime_slot_controller_v2 --manifest outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json --compact-only",
        ],
        "provider_calls_authorized": False,
        "bfcl_generate_authorized": False,
        "bfcl_evaluate_authorized": False,
        "scorer_authorized": False,
        "archive_update_authorized": False,
        "holdout_authorized": False,
        "full_suite_authorized": False,
        "performance_claim_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "artifact_boundary": "compact_only",
        "stop_loss": sorted(REQUIRED_STOP_LOSS),
        "component_summaries": {
            "distinct_slice": distinct,
            "runner_dry_run": dry_run,
        },
        "next_required_action": "request_explicit_distinct_residual_bounded_rerun_approval",
    }
    request["blockers"] = validate_request(request)
    request["distinct_rerun_request_passed"] = not request["blockers"]
    return request


def validate_request(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_distinct_rerun_request":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_distinct_rerun_request_v0":
        blockers.append("schema_version_invalid")
    if data.get("approval_status") != "pending":
        blockers.append("approval_status_not_pending")
    if data.get("scope") != "scorer_unit_distinct_bounded_residual_dev_smoke_review_only":
        blockers.append("scope_invalid")
    for key in FORCED_FALSE:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false")
    if data.get("artifact_boundary") != "compact_only":
        blockers.append("artifact_boundary_not_compact_only")
    if data.get("target_compact_to_scorer_unit_factor") != 1.0:
        blockers.append("target_not_scorer_unit_distinct")
    if data.get("runner_manifest_compatible") is not True:
        blockers.append("runner_manifest_not_compatible")
    if not REQUIRED_STOP_LOSS.issubset(set(data.get("stop_loss") or [])):
        blockers.append("stop_loss_incomplete")
    summaries = data.get("component_summaries") if isinstance(data.get("component_summaries"), dict) else {}
    distinct = summaries.get("distinct_slice") if isinstance(summaries.get("distinct_slice"), dict) else {}
    if distinct.get("scorer_unit_distinct_slice_check_passed") is not True:
        blockers.append("distinct_slice_check_not_passed")
    dry_run = summaries.get("runner_dry_run") if isinstance(summaries.get("runner_dry_run"), dict) else {}
    blockers.extend(str(item) for item in dry_run.get("blockers") or [])
    blockers.extend(scan_value(data, label="abhe_v0_runtime_slot_controller_distinct_rerun_request"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_REQUEST) -> Dict[str, Any]:
    if not path.exists():
        return {
            "report_scope": "abhe_v0_runtime_slot_controller_distinct_rerun_request_check",
            "request_path": str(path),
            "request_present": False,
            "distinct_rerun_request_passed": False,
            "blockers": ["distinct_rerun_request_missing"],
            "performance_evidence": False,
        }
    try:
        data = _load(path)
        blockers = validate_request(data)
    except Exception as exc:
        data = {}
        blockers = [f"load_failed:{exc.__class__.__name__}"]
    return {
        "report_scope": "abhe_v0_runtime_slot_controller_distinct_rerun_request_check",
        "request_path": str(path),
        "request_present": True,
        "approval_status": data.get("approval_status"),
        "authorized": data.get("authorized"),
        "runner_manifest_compatible": data.get("runner_manifest_compatible"),
        "selected_case_ids_hash": data.get("selected_case_ids_hash"),
        "target_compact_to_scorer_unit_factor": data.get("target_compact_to_scorer_unit_factor"),
        "distinct_rerun_request_passed": not blockers,
        "blockers": blockers,
        "performance_evidence": data.get("performance_evidence", False),
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.write:
            request = build_request()
            _write(args.request, request)
        report = check(args.request)
    except Exception as exc:
        report = {
            "report_scope": "abhe_v0_runtime_slot_controller_distinct_rerun_request_check",
            "distinct_rerun_request_passed": False,
            "blockers": [f"load_failed:{exc.__class__.__name__}"],
            "performance_evidence": False,
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report.get("distinct_rerun_request_passed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
