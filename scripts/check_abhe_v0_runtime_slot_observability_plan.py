#!/usr/bin/env python3
"""Validate the ABHE runtime-slot observability plan is fail-closed and compact-only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_observability_plan.json")
FALSE_FIELDS = [
    "authorized",
    "implementation_started",
    "provider_calls_authorized",
    "provider_calls_made",
    "bfcl_generate_authorized",
    "bfcl_generate_called",
    "bfcl_evaluate_authorized",
    "bfcl_evaluate_called",
    "scorer_authorized",
    "scorer_called",
    "holdout_touched",
    "full_suite_touched",
    "archive_updated",
    "performance_evidence",
    "candidate_jsonl_generated",
    "candidate_yaml_generated",
    "candidate_rule_generated",
    "bfcl_rerun_authorized_by_this_plan",
]
REQUIRED_LABEL_PREFIXES = ("pre_generation_", "post_decode_", "post_response_")
FORBIDDEN_TERMS = ["raw_prompt_literal", "raw_tool_argument_value", "raw_provider_payload", "gold_expected_reference_answer", "scorer_diff"]


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_observability_plan":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_observability_plan_v0":
        blockers.append("schema_version_invalid")
    if data.get("plan_status") != "review_plan_only":
        blockers.append("plan_status_not_review_only")
    if data.get("observability_plan_ready") is not True:
        blockers.append("observability_plan_not_ready")
    if data.get("raw_material_absent") is not True or data.get("safe_fields_only") is not True:
        blockers.append("safe_boundary_not_true")
    for key in FALSE_FIELDS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false")
    labels = data.get("safe_compact_labels") if isinstance(data.get("safe_compact_labels"), list) else []
    for prefix in REQUIRED_LABEL_PREFIXES:
        if not any(isinstance(label, str) and label.startswith(prefix) for label in labels):
            blockers.append(f"missing_label_prefix:{prefix}")
    forbidden = data.get("forbidden_surfaces") if isinstance(data.get("forbidden_surfaces"), list) else []
    for term in FORBIDDEN_TERMS:
        if term not in forbidden:
            blockers.append(f"forbidden_surface_missing:{term}")
    row_contract = data.get("future_trace_row_contract") if isinstance(data.get("future_trace_row_contract"), dict) else {}
    if row_contract.get("argument_values_committed") is not False:
        blockers.append("row_contract_argument_values_not_false")
    if row_contract.get("provider_payload_committed") is not False:
        blockers.append("row_contract_provider_payload_not_false")
    if row_contract.get("scorer_diff_committed") is not False:
        blockers.append("row_contract_scorer_diff_not_false")
    anchors = data.get("instrumentation_anchors") if isinstance(data.get("instrumentation_anchors"), list) else []
    required_surfaces = {"pre_generation_request_context", "post_decode_tool_call_structure", "runtime_slot_controller_attribution"}
    actual_surfaces = {item.get("surface") for item in anchors if isinstance(item, dict)}
    for surface in sorted(required_surfaces - actual_surfaces):
        blockers.append(f"instrumentation_surface_missing:{surface}")
    if "runtime_slot_bind_causality_not_confirmed" not in (data.get("promotion_blockers_until_implemented") or []):
        blockers.append("causality_blocker_missing")
    if data.get("next_required_action") != "implement_pre_generation_post_decode_observability_no_provider_fixture_before_bfcl_rerun":
        blockers.append("next_required_action_invalid")
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    try:
        data = _load(path)
        blockers = validate(data)
    except Exception as exc:
        data = {}
        blockers = [f"load_failed:{exc.__class__.__name__}"]
    return {
        "report_scope": "abhe_v0_runtime_slot_observability_plan_check",
        "artifact_path": str(path),
        "observability_plan_check_passed": not blockers,
        "blockers": blockers,
        "observability_plan_ready": data.get("observability_plan_ready"),
        "bfcl_rerun_authorized_by_this_plan": data.get("bfcl_rerun_authorized_by_this_plan", False),
        "performance_evidence": data.get("performance_evidence", False),
        "next_required_action": data.get("next_required_action"),
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = check(args.path)
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["observability_plan_check_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
