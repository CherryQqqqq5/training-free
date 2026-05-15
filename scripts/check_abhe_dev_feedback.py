#!/usr/bin/env python3
"""Validate ABHE post-dev feedback records while keeping the planner fail-closed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_SCHEMA = Path("abhe_archive/dev_feedback.schema.json")
DEFAULT_FEEDBACK_ROOT = Path("abhe_archive/dev_feedback")
REQUIRED_FIELDS = {
    "entry_id",
    "dev_run_id_hash",
    "fresh_dev_slice_hash",
    "target_bucket_reduction",
    "fixed_count",
    "regressed_count",
    "net_fixed",
    "non_target_regression_count",
    "activation_precision",
    "activation_recall",
    "cost_delta_pct",
    "latency_delta_pct",
    "leakage_count",
    "boundary_violation_count",
    "provider_model_protocol_match",
    "raw_material_absent",
    "candidate_pool_created",
    "holdout_touched",
    "full_suite_touched",
}
ALLOWED_ENTRY_IDS = {"state_tracking_v0", "hallucination_abstain_v0"}
NONNEGATIVE_INT_FIELDS = {
    "fixed_count",
    "regressed_count",
    "non_target_regression_count",
    "leakage_count",
    "boundary_violation_count",
}
RATIO_FIELDS = {"activation_precision", "activation_recall"}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _feedback_paths(root: Path) -> List[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        return []
    return sorted(path for path in root.glob("*.json") if path.name != "dev_feedback.schema.json")


def validate_schema(schema: Dict[str, Any]) -> List[str]:
    blockers = []
    required = schema.get("required")
    properties = schema.get("properties")
    if schema.get("type") != "object":
        blockers.append("schema_type_must_be_object")
    if schema.get("additionalProperties") is not False:
        blockers.append("schema_additional_properties_must_be_false")
    if set(required or []) != REQUIRED_FIELDS:
        blockers.append("schema_required_fields_mismatch")
    if not isinstance(properties, dict):
        blockers.append("schema_properties_missing")
        return blockers
    missing_props = sorted(REQUIRED_FIELDS - set(properties))
    if missing_props:
        blockers.append("schema_properties_missing_fields:%s" % ",".join(missing_props))
    const_expectations = {
        "provider_model_protocol_match": True,
        "raw_material_absent": True,
        "candidate_pool_created": False,
        "holdout_touched": False,
        "full_suite_touched": False,
    }
    for key, expected in const_expectations.items():
        if not isinstance(properties.get(key), dict) or properties[key].get("const") is not expected:
            blockers.append("schema_%s_const_invalid:%r" % (key, properties.get(key)))
    blockers.extend(scan_value(schema, label="dev_feedback_schema"))
    return sorted(set(blockers))


def validate_feedback(row: Dict[str, Any], label: str) -> List[str]:
    blockers = []
    missing = sorted(REQUIRED_FIELDS - set(row))
    if missing:
        blockers.append("%s_missing_fields:%s" % (label, ",".join(missing)))
        return blockers
    extra = sorted(set(row) - REQUIRED_FIELDS)
    if extra:
        blockers.append("%s_extra_fields:%s" % (label, ",".join(extra)))
    if row.get("entry_id") not in ALLOWED_ENTRY_IDS:
        blockers.append("%s_entry_id_invalid:%r" % (label, row.get("entry_id")))
    for key in NONNEGATIVE_INT_FIELDS:
        value = row.get(key)
        if not isinstance(value, int) or value < 0:
            blockers.append("%s_%s_nonnegative_int_required:%r" % (label, key, value))
    if row.get("net_fixed") != row.get("fixed_count") - row.get("regressed_count"):
        blockers.append("%s_net_fixed_mismatch" % label)
    for key in RATIO_FIELDS:
        value = row.get(key)
        if not isinstance(value, (int, float)) or value < 0 or value > 1:
            blockers.append("%s_%s_ratio_invalid:%r" % (label, key, value))
    for key in ("target_bucket_reduction", "cost_delta_pct", "latency_delta_pct"):
        if not isinstance(row.get(key), (int, float)):
            blockers.append("%s_%s_number_required:%r" % (label, key, row.get(key)))
    expected_booleans = {
        "provider_model_protocol_match": True,
        "raw_material_absent": True,
        "candidate_pool_created": False,
        "holdout_touched": False,
        "full_suite_touched": False,
    }
    for key, expected in expected_booleans.items():
        if row.get(key) is not expected:
            blockers.append("%s_%s_must_be_%s:%r" % (label, key, str(expected).lower(), row.get(key)))
    blockers.extend(scan_value(row, label=label))
    return sorted(set(blockers))


def check(schema_path: Path = DEFAULT_SCHEMA, feedback_root: Path = DEFAULT_FEEDBACK_ROOT) -> Dict[str, Any]:
    blockers = []
    schema = _load(schema_path)
    blockers.extend(validate_schema(schema))
    checked_files = []
    for path in _feedback_paths(feedback_root):
        checked_files.append(str(path))
        row = _load(path)
        blockers.extend(validate_feedback(row, "feedback_%s" % path.name))
    return {
        "report_scope": "abhe_dev_feedback_check",
        "schema_path": str(schema_path),
        "feedback_root": str(feedback_root),
        "feedback_file_count": len(checked_files),
        "checked_feedback_files": checked_files,
        "post_dev_planner_enabled": False,
        "next_required_action": "keep_plan_abhe_next_evolution_fail_closed_until_post_dev_planner_is_implemented",
        "abhe_dev_feedback_check_passed": not blockers,
        "blockers": sorted(set(blockers)),
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--feedback-root", type=Path, default=DEFAULT_FEEDBACK_ROOT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.schema, args.feedback_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "abhe_dev_feedback_check",
            "abhe_dev_feedback_check_passed": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["abhe_dev_feedback_check_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
