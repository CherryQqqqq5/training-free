#!/usr/bin/env python3
"""Check reduced-batch retry dry-run manifest is non-executing and compact-only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value
from scripts.check_abhe_v0_runtime_slot_reduced_batch_slice_manifest import check as check_slice_manifest

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_reduced_batch_retry_dry_run_manifest.json")
SLICE = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_reduced_batch_slice_manifest.json")
EXPECTED_HASH = "sha256:aa341bfc1d78a406f9f3a25967a03d88849dc42fc64e49625eae1993f33ddece"
TARGET_CATEGORY = "multi_turn_miss_param"
EXPECTED_COUNT = 6
FORCED_FALSE = [
    "execution_started", "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called", "scorer_called",
    "raw_provider_payload_committed", "raw_bfcl_result_tree_committed", "gold_expected_committed", "scorer_diff_committed",
    "holdout_touched", "full_suite_touched", "archive_updated", "performance_evidence",
]


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_reduced_batch_retry_dry_run_manifest":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_reduced_batch_retry_dry_run_manifest_v0":
        blockers.append("schema_version_invalid")
    if data.get("arm") != "baseline":
        blockers.append("arm_invalid")
    if data.get("dry_run") is not True:
        blockers.append("dry_run_not_true")
    if data.get("manifest_path") != str(SLICE):
        blockers.append("manifest_path_invalid")
    if data.get("selected_case_ids_hash") != EXPECTED_HASH:
        blockers.append("selected_case_ids_hash_invalid")
    if data.get("selected_case_count") != EXPECTED_COUNT:
        blockers.append("selected_case_count_invalid")
    if (data.get("category_counts") or {}).get(TARGET_CATEGORY) != EXPECTED_COUNT:
        blockers.append("category_counts_invalid")
    if data.get("runner_manifest_compatible") is not True:
        blockers.append("runner_manifest_compatible_not_true")
    if data.get("mapped_run_id_count") != EXPECTED_COUNT or data.get("unique_run_id_count") != EXPECTED_COUNT or data.get("duplicate_run_id_count") != 0:
        blockers.append("mapped_run_id_count_invalid")
    if data.get("raw_run_ids_persisted") is not False or data.get("raw_run_id_hashes_persisted") is not False:
        blockers.append("raw_run_ids_persisted_not_false")
    if data.get("fresh_run_root_required") is not True:
        blockers.append("fresh_run_root_required_not_true")
    if not isinstance(data.get("run_root_path"), str) or not data.get("run_root_path"):
        blockers.append("run_root_path_missing")
    if data.get("raw_material_absent") is not True:
        blockers.append("raw_material_absent_not_true")
    for key in FORCED_FALSE:
        if data.get(key) is not False:
            blockers.append("%s_not_false" % key)
    slice_report = check_slice_manifest()
    if slice_report.get("reduced_batch_slice_manifest_passed") is not True:
        blockers.append("reduced_batch_slice_manifest_not_passed")
    blockers.extend(str(item) for item in data.get("blockers") or [])
    blockers.extend(scan_value(data, label="abhe_v0_runtime_slot_controller_reduced_batch_retry_dry_run_manifest"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    try:
        data = _load(path)
        blockers = validate(data)
    except Exception as exc:
        data = {}
        blockers = ["load_failed:%s" % exc.__class__.__name__]
    return {
        "report_scope": "abhe_v0_runtime_slot_controller_reduced_batch_retry_dry_run_manifest_check",
        "artifact_path": str(path),
        "reduced_batch_dry_run_manifest_passed": not blockers,
        "selected_case_ids_hash": data.get("selected_case_ids_hash"),
        "selected_case_count": data.get("selected_case_count"),
        "provider_calls_made": data.get("provider_calls_made"),
        "bfcl_generate_called": data.get("bfcl_generate_called"),
        "scorer_called": data.get("scorer_called"),
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
    return 1 if args.strict and not report["reduced_batch_dry_run_manifest_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
