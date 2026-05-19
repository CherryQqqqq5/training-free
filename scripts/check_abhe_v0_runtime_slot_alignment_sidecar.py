#!/usr/bin/env python3
"""Check compact selected-id alignment sidecar for ABHE runtime-slot reruns."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_alignment_sidecar.json")
EXPECTED_ACTION = "request_bounded_rerun_with_compact_alignment_sidecar_enabled"
FORBIDDEN_TRUE = [
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
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_controller_alignment_sidecar":
        blockers.append("artifact_kind_invalid")
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    arm_summaries = data.get("arm_summaries") if isinstance(data.get("arm_summaries"), dict) else {}
    if summary.get("alignment_sidecar_ready") is not True:
        blockers.append("alignment_sidecar_not_ready")
    if summary.get("next_rerun_must_emit_this_sidecar") is not True:
        blockers.append("next_rerun_sidecar_requirement_missing")
    if summary.get("more_bfcl_without_sidecar_recommended") is not False:
        blockers.append("more_bfcl_without_sidecar_not_false")
    if data.get("next_required_action") != EXPECTED_ACTION:
        blockers.append(f"next_required_action_invalid:{data.get('next_required_action')!r}")
    selected_count = int(summary.get("selected_count") or 0)
    arm_count = int(summary.get("arm_count") or 0)
    if selected_count <= 0 or arm_count <= 0:
        blockers.append("selected_or_arm_count_missing")
    if len(rows) != selected_count * arm_count:
        blockers.append(f"row_count_mismatch:{len(rows)}")
    required = {"arm", "selected_index", "selected_case_identifier_hash", "scorer_unit_hash", "bfcl_category", "score_record_seen_for_selected_id", "result_record_seen_for_selected_id", "per_selected_valid_label_available", "per_turn_valid_labels_available", "raw_material_absent"}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            blockers.append(f"row_not_object:{index}")
            continue
        missing = required - set(row)
        if missing:
            blockers.append(f"row_missing_required:{index}:{','.join(sorted(missing))}")
        if row.get("raw_material_absent") is not True:
            blockers.append(f"row_raw_material_absent_not_true:{index}")
        if row.get("per_selected_valid_label_available") is not False:
            blockers.append(f"row_per_selected_label_unexpected:{index}")
        if row.get("per_turn_valid_labels_available") is not False:
            blockers.append(f"row_per_turn_label_unexpected:{index}")
    for arm, summary_row in arm_summaries.items():
        if not isinstance(summary_row, dict):
            blockers.append(f"arm_summary_not_object:{arm}")
            continue
        if summary_row.get("selected_count") != selected_count:
            blockers.append(f"arm_selected_count_mismatch:{arm}")
    for field in FORBIDDEN_TRUE:
        if data.get(field) is not False:
            blockers.append(f"{field}_not_false")
    blockers.extend(scan_value(data, label="abhe_v0_runtime_slot_controller_alignment_sidecar"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_PATH) -> Dict[str, Any]:
    blockers: List[str] = []
    try:
        data = _load(path)
        blockers.extend(validate(data))
    except Exception as exc:
        data = {}
        blockers.append(f"load_failed:{exc.__class__.__name__}")
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return {
        "report_scope": "abhe_v0_runtime_slot_controller_alignment_sidecar_check",
        "artifact_path": str(path),
        "alignment_sidecar_check_passed": not blockers,
        "alignment_sidecar_ready": summary.get("alignment_sidecar_ready") is True,
        "selected_count": summary.get("selected_count"),
        "row_count": summary.get("row_count"),
        "per_selected_valid_labels_available": summary.get("per_selected_valid_labels_available"),
        "per_turn_valid_labels_available": summary.get("per_turn_valid_labels_available"),
        "next_required_action": data.get("next_required_action"),
        "performance_evidence": data.get("performance_evidence"),
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = check(args.path)
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["alignment_sidecar_check_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
