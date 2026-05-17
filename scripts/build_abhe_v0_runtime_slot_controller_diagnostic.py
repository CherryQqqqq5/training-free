#!/usr/bin/env python3
"""Summarize ABHE runtime slot-controller diagnostic gates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
MICRO = ROOT / "abhe_v0_runtime_slot_micro_harness.json"
AUDIT = ROOT / "abhe_v0_missing_param_counterfactual_slot_audit_v0.json"
OUT = ROOT / "abhe_v0_runtime_slot_controller_diagnostic.json"
RESIDUAL_FAILURE = ROOT / "abhe_v0_runtime_slot_controller_residual_failure_analysis.json"
RESIDUAL_AUDIT = ROOT / "abhe_v0_runtime_slot_controller_sanitized_trace_audit.json"


def _load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"artifact_missing": str(path)}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"artifact_invalid": str(path)}


def build() -> Dict[str, Any]:
    micro = _load(MICRO)
    audit = _load(AUDIT)
    residual_failure = _load(RESIDUAL_FAILURE)
    residual_audit = _load(RESIDUAL_AUDIT)
    blockers = []
    if micro.get("micro_harness_passed") is not True:
        blockers.append("micro_harness_not_passed")
    if audit.get("blockers"):
        blockers.extend("counterfactual_audit:" + str(item) for item in audit.get("blockers", []))
    summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    bindable = int(summary.get("counterfactual_bindable_count") or 0)
    lookup = int(summary.get("counterfactual_lookup_needed_count") or 0)
    residual_summary = residual_failure.get("summary") if isinstance(residual_failure.get("summary"), dict) else {}
    residual_audit_summary = residual_audit.get("summary") if isinstance(residual_audit.get("summary"), dict) else {}
    runtime_audit = residual_audit_summary.get("runtime_slot_controller_v2") if isinstance(residual_audit_summary.get("runtime_slot_controller_v2"), dict) else {}
    phase_c_completed = residual_failure.get("artifact_kind") == "abhe_v0_runtime_slot_controller_residual_failure_analysis"
    slot_bind_repair_count = int(residual_summary.get("slot_bind_repair_count") or runtime_audit.get("slot_bind_repair_count") or 0)
    phase_c_blockers = [] if phase_c_completed else ["runtime_slot_controller_v2_not_integrated_into_proxy_request_response_path"]
    return {
        "artifact_kind": "abhe_v0_runtime_slot_controller_diagnostic",
        "schema_version": "abhe_v0_runtime_slot_controller_diagnostic_v0",
        "phase_a_counterfactual_audit_ready": not audit.get("artifact_missing") and not audit.get("blockers"),
        "phase_b_micro_harness_ready": micro.get("micro_harness_passed") is True,
        "phase_c_bfcl_rerun_completed": phase_c_completed,
        "phase_c_bfcl_rerun_ready": phase_c_completed,
        "phase_c_mechanism_confirmed_by_bind_repairs": slot_bind_repair_count > 0,
        "phase_c_blockers": phase_c_blockers,
        "residual_target_delta_vs_conditional_frozen_v2": residual_summary.get("multi_turn_miss_param_delta_vs_conditional_frozen_v2"),
        "residual_slot_bind_repair_count": slot_bind_repair_count,
        "counterfactual_bindable_count": bindable,
        "counterfactual_lookup_needed_count": lookup,
        "runtime_controller_direction": "promising_for_runtime_integration" if bindable + lookup > 0 else "insufficient_counterfactual_signal",
        "next_required_action": "confirm_mechanism_with_actual_bind_repairs_before_promotion" if phase_c_completed and slot_bind_repair_count == 0 else ("review_runtime_slot_controller_v2_for_promotion" if phase_c_completed else "integrate_runtime_slot_controller_v2_into_proxy_before_bounded_bfcl_rerun"),
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "raw_material_absent": True,
        "trace_content_committed": False,
        "prompt_literal_committed": False,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_evidence": False,
        "archive_updated": False,
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = build()
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
