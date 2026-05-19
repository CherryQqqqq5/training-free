#!/usr/bin/env python3
"""Check ABHE runtime-slot selected-row to raw run-id mapping audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_run_id_mapping_audit.json")
EXPECTED_COUNTS = {
    "multi_turn_miss_param": 24,
    "multi_turn_miss_func": 6,
    "multi_turn_base": 6,
    "multi_turn_long_context": 4,
    "irrelevance": 4,
    "live_irrelevance": 4,
}
EXPECTED_TOTAL = 48
EXPECTED_NEXT_ACTION = "request_bounded_rerun_after_run_id_mapping_fix"
FALSE_FIELDS = [
    "provider_calls_made",
    "bfcl_generate_called",
    "bfcl_evaluate_called",
    "scorer_called",
    "prompt_literal_committed",
    "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed",
    "gold_expected_committed",
    "scorer_diff_committed",
    "model_output_text_committed",
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
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_run_id_mapping_audit":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_controller_run_id_mapping_audit_v0":
        blockers.append("schema_version_invalid")
    if data.get("run_scope") != "offline_run_id_mapping_audit_only_no_provider_no_bfcl_no_scorer":
        blockers.append("run_scope_invalid")
    if data.get("selected_case_count") != EXPECTED_TOTAL:
        blockers.append("selected_case_count_invalid")
    if data.get("mapped_run_id_count") != EXPECTED_TOTAL:
        blockers.append("mapped_run_id_count_invalid")
    if data.get("unique_run_id_hash_count") != EXPECTED_TOTAL:
        blockers.append("unique_run_id_hash_count_invalid")
    if data.get("run_id_mapping_ready") is not True:
        blockers.append("run_id_mapping_not_ready")
    if data.get("next_required_action") != EXPECTED_NEXT_ACTION:
        blockers.append("next_required_action_invalid")
    if data.get("raw_material_absent") is not True:
        blockers.append("raw_material_absent_not_true")
    if data.get("raw_ids_persisted") is not False or data.get("raw_id_hashes_persisted") is not False:
        blockers.append("raw_id_material_persisted")
    for field in FALSE_FIELDS:
        if data.get(field) is not False:
            blockers.append(f"{field}_not_false")
    summaries = data.get("category_summaries") if isinstance(data.get("category_summaries"), dict) else {}
    for category, expected in EXPECTED_COUNTS.items():
        summary = summaries.get(category) if isinstance(summaries.get(category), dict) else {}
        if summary.get("selected_compact_count") != expected:
            blockers.append(f"selected_count_invalid:{category}")
        if summary.get("mapped_run_id_count") != expected:
            blockers.append(f"mapped_count_invalid:{category}")
        if summary.get("unique_run_id_hash_count") != expected:
            blockers.append(f"unique_count_invalid:{category}")
        if summary.get("duplicate_run_id_count") != 0:
            blockers.append(f"duplicate_run_ids:{category}")
        if summary.get("mapping_is_one_to_one") is not True:
            blockers.append(f"mapping_not_one_to_one:{category}")
        if summary.get("raw_ids_persisted") is not False or summary.get("raw_id_hashes_persisted") is not False:
            blockers.append(f"category_raw_id_material_persisted:{category}")
    blockers.extend(str(item) for item in (data.get("blockers") or []))
    blockers.extend(scan_value(data, label="abhe_v0_runtime_slot_controller_run_id_mapping_audit"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    try:
        data = _load(path)
        blockers = validate(data)
    except Exception as exc:
        data = {}
        blockers = [f"load_failed:{exc.__class__.__name__}"]
    return {
        "report_scope": "abhe_v0_runtime_slot_controller_run_id_mapping_audit_check",
        "artifact_path": str(path),
        "run_id_mapping_audit_passed": not blockers,
        "run_id_mapping_ready": data.get("run_id_mapping_ready") is True,
        "selected_case_ids_hash": data.get("selected_case_ids_hash"),
        "selected_case_count": data.get("selected_case_count"),
        "mapped_run_id_count": data.get("mapped_run_id_count"),
        "unique_run_id_hash_count": data.get("unique_run_id_hash_count"),
        "next_required_action": data.get("next_required_action"),
        "performance_evidence": data.get("performance_evidence"),
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
    return 1 if args.strict and not report["run_id_mapping_audit_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
