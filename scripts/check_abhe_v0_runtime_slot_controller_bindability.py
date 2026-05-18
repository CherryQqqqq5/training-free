#!/usr/bin/env python3
"""Check ABHE runtime slot-controller bindability audit artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_bindability_audit_v1.json")
FALSE_FIELDS = [
    "prompt_literal_committed",
    "argument_values_committed",
    "provider_payload_committed",
    "bfcl_result_tree_committed",
    "gold_expected_committed",
    "scorer_diff_committed",
    "provider_calls_made",
    "bfcl_generate_called",
    "bfcl_evaluate_called",
    "scorer_called",
    "holdout_touched",
    "full_suite_touched",
    "performance_evidence",
    "archive_updated",
]


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_bindability_audit_v1":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_bindability_audit_v1":
        blockers.append("schema_version_invalid")
    if data.get("safe_fields_only") is not True or data.get("raw_material_absent") is not True:
        blockers.append("safe_boundary_not_true")
    for key in FALSE_FIELDS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false")
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    if int(summary.get("target_trace_row_count") or 0) <= 0:
        blockers.append("target_trace_row_count_missing")
    if int(summary.get("runtime_marker_present_count") or 0) <= 0:
        blockers.append("runtime_marker_present_count_missing")
    if int(summary.get("slot_bind_repair_count") or 0) != 0:
        blockers.append("unexpected_slot_bind_repair_count_nonzero")
    interp = data.get("interpretation") if isinstance(data.get("interpretation"), dict) else {}
    if interp.get("direct_slot_binding_causality_supported") is not False:
        blockers.append("direct_slot_binding_causality_overclaimed")
    if interp.get("mechanism_promotion_allowed") is not False:
        blockers.append("mechanism_promotion_not_fail_closed")
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            blockers.append(f"row_invalid:{idx}")
            continue
        if row.get("raw_material_absent") is not True or row.get("argument_values_committed") is not False:
            blockers.append(f"row_boundary_invalid:{idx}")
        if row.get("bfcl_category") != "multi_turn_miss_param":
            blockers.append(f"row_target_category_invalid:{idx}")
    for item in data.get("blockers") or []:
        blockers.append(str(item))
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    try:
        data = _load(path)
        blockers = validate(data)
    except Exception as exc:
        data = {}
        blockers = [f"load_failed:{exc.__class__.__name__}"]
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    interpretation = data.get("interpretation") if isinstance(data.get("interpretation"), dict) else {}
    return {
        "report_scope": "abhe_v0_runtime_slot_controller_bindability_audit_v1_check",
        "artifact_path": str(path),
        "bindability_audit_check_passed": not blockers,
        "blockers": blockers,
        "target_trace_row_count": summary.get("target_trace_row_count"),
        "slot_bind_repair_count": summary.get("slot_bind_repair_count"),
        "bindable_missing_required_arg_row_count": summary.get("bindable_missing_required_arg_row_count"),
        "mechanism_promotion_allowed": interpretation.get("mechanism_promotion_allowed"),
        "performance_evidence": data.get("performance_evidence", False),
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = check(args.path)
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["bindability_audit_check_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
