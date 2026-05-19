#!/usr/bin/env python3
"""Check compact failure report for the ABHE runtime-slot distinct rerun."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_distinct_rerun_failure.json")
EXPECTED_HASH = "sha256:9b26ba3d24c54562f6a5058877a24f15d2e4ef71ee9ea781bcae168307f7d14c"
EXPECTED_NEXT_ACTION = "stabilize_provider_or_reduce_target_category_batch_before_mapping_fixed_bounded_rerun"
EXPECTED_BLOCKERS = {
    "bfcl_generate_failed:multi_turn_miss_param",
    "provider_504_observed_in_tmp_proxy_log",
    "bounded_rerun_stopped_before_evaluate_or_scorer",
}
FALSE_FIELDS = [
    "bfcl_evaluate_called",
    "scorer_called",
    "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed",
    "gold_expected_committed",
    "scorer_diff_committed",
    "holdout_touched",
    "full_suite_touched",
    "archive_updated",
    "performance_evidence",
]


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_distinct_rerun_failure":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_distinct_rerun_failure_v0":
        blockers.append("schema_version_invalid")
    if data.get("run_scope") != "scorer_unit_distinct_bounded_residual_dev_smoke_only":
        blockers.append("run_scope_invalid")
    if data.get("arm") != "baseline":
        blockers.append("arm_invalid")
    if data.get("failed_category") != "multi_turn_miss_param":
        blockers.append("failed_category_invalid")
    if data.get("selected_case_ids_hash") != EXPECTED_HASH:
        blockers.append("selected_case_ids_hash_invalid")
    if data.get("selected_case_count") != 48:
        blockers.append("selected_case_count_invalid")
    if data.get("execution_started") is not True:
        blockers.append("execution_started_not_true")
    if data.get("provider_calls_made") is not True:
        blockers.append("provider_calls_made_not_true")
    if data.get("bfcl_generate_called") is not True:
        blockers.append("bfcl_generate_called_not_true")
    if data.get("failure_kind") != "bfcl_generate_failed_or_timed_out_after_provider_504s":
        blockers.append("failure_kind_invalid")
    if data.get("raw_material_absent") is not True:
        blockers.append("raw_material_absent_not_true")
    for field in FALSE_FIELDS:
        if data.get(field) is not False:
            blockers.append(f"{field}_not_false")
    if data.get("next_required_action") != EXPECTED_NEXT_ACTION:
        blockers.append("next_required_action_invalid")
    seen_blockers = set(str(item) for item in data.get("blockers") or [])
    missing = EXPECTED_BLOCKERS - seen_blockers
    if missing:
        blockers.append("blockers_missing:" + ",".join(sorted(missing)))
    partial_count = data.get("partial_trace_file_count_tmp_only")
    if not isinstance(partial_count, int) or partial_count <= 0:
        blockers.append("partial_trace_file_count_tmp_only_invalid")
    blockers.extend(scan_value(data, label="abhe_v0_runtime_slot_controller_distinct_rerun_failure"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    try:
        data = _load(path)
        blockers = validate(data)
    except Exception as exc:
        data = {}
        blockers = [f"load_failed:{exc.__class__.__name__}"]
    return {
        "report_scope": "abhe_v0_runtime_slot_controller_distinct_rerun_failure_check",
        "artifact_path": str(path),
        "distinct_rerun_failure_check_passed": not blockers,
        "failure_present": bool(data),
        "execution_started": data.get("execution_started") is True,
        "provider_calls_made": data.get("provider_calls_made") is True,
        "bfcl_generate_called": data.get("bfcl_generate_called") is True,
        "bfcl_evaluate_called": data.get("bfcl_evaluate_called") is True,
        "scorer_called": data.get("scorer_called") is True,
        "selected_case_ids_hash": data.get("selected_case_ids_hash"),
        "selected_case_count": data.get("selected_case_count"),
        "failed_category": data.get("failed_category"),
        "performance_evidence": data.get("performance_evidence"),
        "next_required_action": data.get("next_required_action"),
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = check(args.path)
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["distinct_rerun_failure_check_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
