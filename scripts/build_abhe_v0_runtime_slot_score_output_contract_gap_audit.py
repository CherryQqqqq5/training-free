#!/usr/bin/env python3
"""Build compact score-output contract gap audit for ABHE runtime-slot reruns.

This is an offline sanitizer over existing temporary BFCL outputs. It records
only counts, hashes, enum-like classes, and contract flags. It does not call a
provider, BFCL generation/evaluation, or scorer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
MANIFEST = ROOT / "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json"
OUTPUT = ROOT / "abhe_v0_runtime_slot_controller_score_output_contract_gap_audit.json"
RUN_ROOT = Path("/tmp/abhe_v0_runtime_slot_controller_residual_dev_smoke")
MODEL_ALIAS = "gpt-4o-mini-2024-07-18-FC"
ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]
TARGET_CATEGORY = "multi_turn_miss_param"
NEXT_ACTION = "instrument_runner_scorer_to_emit_compact_alignment_sidecar_before_more_bfcl"
MISSING_CONTRACT_FIELDS = [
    "selected_case_identifier_hash",
    "selected_index",
    "score_record_id_to_selected_identifier_hash_map",
    "turn_index_to_selected_identifier_hash_map",
    "per_selected_valid_label",
    "per_turn_valid_label",
    "error_type_class_per_selected_or_turn",
]
FALSE_FIELDS = [
    "provider_calls_made",
    "bfcl_generate_called",
    "bfcl_evaluate_called",
    "scorer_called",
    "score_rows_committed",
    "provider_payload_committed",
    "bfcl_result_tree_committed",
    "gold_expected_committed",
    "scorer_diff_committed",
    "holdout_touched",
    "full_suite_touched",
    "archive_updated",
    "performance_evidence",
]


def _hash_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _family(category: str) -> str:
    if category.startswith("live_"):
        return "live"
    if category.startswith("multi_turn"):
        return "multi_turn"
    return "non_live"


def _score_path(arm: str, category: str) -> Path:
    family = _family(category)
    return RUN_ROOT / arm / category / "bfcl" / "score" / MODEL_ALIAS / family / f"BFCL_v4_{category}_score.json"


def _result_path(arm: str, category: str) -> Path:
    family = _family(category)
    return RUN_ROOT / arm / category / "bfcl" / "result" / MODEL_ALIAS / family / f"BFCL_v4_{category}_result.json"


def _trace_dir(arm: str, category: str) -> Path:
    return RUN_ROOT / arm / category / "traces"


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _score_shape(path: Path) -> Dict[str, Any]:
    summary = {"score_file_present": path.exists(), "score_total_count": 0, "score_correct_count": 0, "score_accuracy": None}
    invalid_record_count = 0
    error_type_classes: Dict[str, int] = {}
    record_key_hashes: List[str] = []
    for index, obj in enumerate(_iter_jsonl(path)):
        if index == 0 and {"accuracy", "correct_count", "total_count"}.issubset(obj.keys()):
            summary.update({
                "score_total_count": int(obj.get("total_count") or 0),
                "score_correct_count": int(obj.get("correct_count") or 0),
                "score_accuracy": obj.get("accuracy"),
            })
            continue
        invalid_record_count += 1
        error = obj.get("error") if isinstance(obj.get("error"), dict) else {}
        error_type = str(error.get("error_type") or "none")
        error_type_classes[error_type] = error_type_classes.get(error_type, 0) + 1
        record_key_hashes.append(_hash_text(str(obj.get("id") or f"missing:{invalid_record_count}")))
    summary.update({
        "score_invalid_record_count": invalid_record_count,
        "score_record_key_hashes_sample": record_key_hashes[:8],
        "score_record_key_hash_sample_truncated": len(record_key_hashes) > 8,
        "error_type_class_counts": error_type_classes,
    })
    return summary


def _result_shape(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"result_file_present": False, "result_record_count": 0, "result_turn_count_min": 0, "result_turn_count_max": 0}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {"result_file_present": True, "result_record_count": 0, "result_decode_failed": True}
    records = data if isinstance(data, list) else [data]
    turn_counts: List[int] = []
    record_hashes: List[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        record_hashes.append(_hash_text(str(record.get("id") or f"missing:{len(record_hashes)}")))
        result = record.get("result")
        turn_counts.append(len(result) if isinstance(result, list) else 0)
    return {
        "result_file_present": True,
        "result_record_count": len(record_hashes),
        "result_record_key_hashes_sample": record_hashes[:8],
        "result_record_key_hash_sample_truncated": len(record_hashes) > 8,
        "result_turn_count_min": min(turn_counts) if turn_counts else 0,
        "result_turn_count_max": max(turn_counts) if turn_counts else 0,
    }


def _trace_shape(path: Path) -> Dict[str, Any]:
    files = sorted(path.rglob("*.json")) if path.exists() else []
    return {
        "trace_file_count": len(files),
        "trace_file_name_hashes_sample": [_hash_text(file.name) for file in files[:8]],
        "trace_file_hash_sample_truncated": len(files) > 8,
    }


def _category_counts(manifest: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in manifest.get("selected_compact_case_identifiers") or []:
        if not isinstance(row, dict):
            continue
        category = str(row.get("bfcl_category"))
        counts[category] = counts.get(category, 0) + 1
    return counts


def build(write: bool = False, output_path: Path = OUTPUT) -> Dict[str, Any]:
    manifest = _load(MANIFEST)
    selected_counts = _category_counts(manifest)
    selected_scorer_units = manifest.get("scorer_unit_count_by_category") if isinstance(manifest.get("scorer_unit_count_by_category"), dict) else {}
    rows: List[Dict[str, Any]] = []
    for arm in ARMS:
        for category in sorted(selected_counts):
            score = _score_shape(_score_path(arm, category))
            result = _result_shape(_result_path(arm, category))
            traces = _trace_shape(_trace_dir(arm, category))
            selected_count = int(selected_counts.get(category) or 0)
            planned_units = int(selected_scorer_units.get(category) or selected_count)
            score_total = int(score.get("score_total_count") or 0)
            result_count = int(result.get("result_record_count") or 0)
            trace_count = int(traces.get("trace_file_count") or 0)
            per_selected_recoverable = selected_count == score_total == result_count and selected_count > 0
            per_turn_recoverable = False
            row = {
                "arm": arm,
                "bfcl_category": category,
                "selected_compact_count": selected_count,
                "selected_scorer_unit_count": planned_units,
                "score_total_count": score_total,
                "score_correct_count": score.get("score_correct_count"),
                "score_invalid_record_count": score.get("score_invalid_record_count"),
                "score_accuracy": score.get("score_accuracy"),
                "result_record_count": result_count,
                "result_turn_count_min": result.get("result_turn_count_min"),
                "result_turn_count_max": result.get("result_turn_count_max"),
                "trace_file_count": trace_count,
                "selected_to_score_total_factor": round(selected_count / max(1, score_total), 6),
                "selected_to_result_record_factor": round(selected_count / max(1, result_count), 6),
                "score_total_matches_selected_count": score_total == selected_count,
                "result_records_match_selected_count": result_count == selected_count,
                "trace_files_match_selected_count": trace_count == selected_count,
                "per_selected_label_recoverable": per_selected_recoverable,
                "per_turn_label_recoverable": per_turn_recoverable,
                "error_type_class_counts": score.get("error_type_class_counts"),
                "score_record_key_hashes_sample": score.get("score_record_key_hashes_sample"),
                "result_record_key_hashes_sample": result.get("result_record_key_hashes_sample"),
                "trace_file_name_hashes_sample": traces.get("trace_file_name_hashes_sample"),
                "missing_contract_fields": MISSING_CONTRACT_FIELDS,
                "contract_gap_reasons": [],
                "raw_material_absent": True,
            }
            if not per_selected_recoverable:
                row["contract_gap_reasons"].append("selected_count_not_aligned_to_score_and_result_records")
            if not per_turn_recoverable:
                row["contract_gap_reasons"].append("bfcl_multi_turn_checker_returns_whole_entry_verdict_only")
            rows.append(row)

    target_rows = [row for row in rows if row["bfcl_category"] == TARGET_CATEGORY]
    target_selected = max([int(row["selected_compact_count"]) for row in target_rows] or [0])
    target_score_total = max([int(row["score_total_count"]) for row in target_rows] or [0])
    target_result_records = max([int(row["result_record_count"]) for row in target_rows] or [0])
    summary = {
        "selected_case_ids_hash": manifest.get("selected_case_ids_hash"),
        "selected_compact_case_count": manifest.get("selected_case_count"),
        "target_category": TARGET_CATEGORY,
        "target_selected_compact_count": target_selected,
        "target_score_total_count": target_score_total,
        "target_result_record_count": target_result_records,
        "target_selected_to_score_total_factor": round(target_selected / max(1, target_score_total), 6),
        "target_selected_to_result_record_factor": round(target_selected / max(1, target_result_records), 6),
        "per_selected_labels_recoverable": False,
        "per_turn_labels_recoverable": False,
        "contract_gap_confirmed": True,
        "more_bfcl_before_contract_fix_recommended": False,
    }
    report: Dict[str, Any] = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_score_output_contract_gap_audit",
        "schema_version": "abhe_v0_runtime_slot_controller_score_output_contract_gap_audit_v0",
        "run_scope": "offline_compact_score_output_contract_gap_audit_only_no_provider_no_bfcl_no_scorer",
        "bounded_dev_smoke_only": True,
        "summary": summary,
        "contract_requirements_for_next_rerun": {
            "score_output_must_emit_selected_identifier_hash": True,
            "score_output_must_emit_selected_index": True,
            "score_output_must_emit_scorer_unit_hash": True,
            "score_output_must_emit_arm_and_category": True,
            "score_output_must_emit_valid_label_per_selected_or_explicit_aggregation_map": True,
            "multi_turn_output_must_emit_turn_index_and_verdict_for_true_per_turn_claim": True,
            "sidecar_must_be_compact_only": True,
            "sidecar_must_not_include_prompt_or_answer_material": True,
        },
        "arm_category_rows": rows,
        "interpretation": {
            "current_tmp_outputs_support_category_or_observed_record_diagnostics_only": True,
            "do_not_interpret_distinct_rerun_as_true_per_selected_evidence": True,
            "do_not_interpret_distinct_rerun_as_true_per_turn_evidence": True,
            "safe_next_step": NEXT_ACTION,
        },
        "next_required_action": NEXT_ACTION,
        "raw_material_absent": True,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "score_rows_committed": False,
        "provider_payload_committed": False,
        "bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "performance_evidence": False,
        "blockers": [],
    }
    for key in FALSE_FIELDS:
        if report.get(key) is not False:
            report["blockers"].append(f"{key}_not_false")
    leakage = scan_value(report, label="abhe_v0_runtime_slot_controller_score_output_contract_gap_audit")
    if leakage:
        report["blockers"] = sorted(set(report["blockers"] + leakage))
    if write:
        _write(output_path, report)
    return report


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build(write=args.write)
    except Exception as exc:
        report = {
            "artifact_kind": "abhe_v0_runtime_slot_controller_score_output_contract_gap_audit",
            "blockers": [f"load_failed:{exc.__class__.__name__}"],
            "performance_evidence": False,
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
