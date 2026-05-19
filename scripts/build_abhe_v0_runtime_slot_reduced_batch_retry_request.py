#!/usr/bin/env python3
"""Build pending reduced-batch retry request after runtime-slot provider 504 failure."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.build_abhe_v0_bfcl_fresh_dev_slice import selected_case_ids_hash
from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
FULL_PLAN = ROOT / "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json"
STABILIZATION_PLAN = ROOT / "abhe_v0_runtime_slot_controller_retry_stabilization_plan.json"
OUTPUT = ROOT / "abhe_v0_runtime_slot_controller_reduced_batch_retry_request.json"
PARENT_HASH = "sha256:9b26ba3d24c54562f6a5058877a24f15d2e4ef71ee9ea781bcae168307f7d14c"
TARGET_CATEGORY = "multi_turn_miss_param"
MAX_CASES = 6
NEXT_ACTION = "request_reduced_batch_retry_approval_packet_with_fresh_run_root"


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _target_rows(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = plan.get("selected_compact_case_identifiers") if isinstance(plan.get("selected_compact_case_identifiers"), list) else []
    selected = [row for row in rows if isinstance(row, dict) and row.get("bfcl_category") == TARGET_CATEGORY][:MAX_CASES]
    return selected


def build() -> Dict[str, Any]:
    full = _load(FULL_PLAN)
    stabilization = _load(STABILIZATION_PLAN)
    selected = _target_rows(full)
    reduced_hash = selected_case_ids_hash(selected) if selected else "pending"
    request: Dict[str, Any] = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_reduced_batch_retry_request",
        "schema_version": "abhe_v0_runtime_slot_controller_reduced_batch_retry_request_v0",
        "approval_status": "pending",
        "authorized": False,
        "approval_required": True,
        "scope": "mapping_fixed_reduced_batch_provider_stability_retry_review_only",
        "bounded_dev_smoke_only": True,
        "based_on_failure_artifact": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_distinct_rerun_failure.json",
        "based_on_stabilization_plan": str(STABILIZATION_PLAN),
        "parent_selected_case_ids_hash": PARENT_HASH,
        "reduced_batch_case_ids_hash": reduced_hash,
        "target_category": TARGET_CATEGORY,
        "selected_case_count": len(selected),
        "max_selected_case_count": MAX_CASES,
        "selected_compact_case_identifiers": selected,
        "must_use_exact_selected_compact_identifiers_from_existing_distinct_slice": True,
        "must_not_expand_case_list": True,
        "fresh_run_root_required": True,
        "provider_stability_preflight_required": True,
        "one_attempt_only": True,
        "requested_arms": ["baseline"],
        "evaluate_after_generate_authorized": False,
        "scorer_after_generate_authorized": False,
        "future_execute_scope_requires_new_approval_packet": True,
        "provider_calls_authorized": False,
        "bfcl_generate_authorized": False,
        "bfcl_evaluate_authorized": False,
        "scorer_authorized": False,
        "archive_update_authorized": False,
        "holdout_authorized": False,
        "full_suite_authorized": False,
        "performance_claim_authorized": False,
        "performance_evidence": False,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "component_summaries": {
            "full_distinct_slice_hash": full.get("selected_case_ids_hash"),
            "full_distinct_slice_count": full.get("selected_case_count"),
            "retry_stabilization_next_required_action": stabilization.get("next_required_action"),
        },
        "stop_loss": [
            "provider_stability_preflight_failed",
            "fresh_run_root_not_empty",
            "reduced_batch_case_count_exceeded",
            "case_list_hash_mismatch",
            "raw_leakage",
            "bfcl_generate_timeout_or_504",
            "unexpected_evaluate_or_scorer_call",
        ],
        "next_required_action": NEXT_ACTION,
    }
    request["blockers"] = scan_value(request, label="abhe_v0_runtime_slot_controller_reduced_batch_retry_request")
    return request


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build()
        if args.write:
            _write(OUTPUT, report)
    except Exception as exc:
        report = {"artifact_kind": "abhe_v0_runtime_slot_controller_reduced_batch_retry_request", "blockers": [f"load_failed:{exc.__class__.__name__}"], "performance_evidence": False}
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
