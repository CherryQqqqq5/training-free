#!/usr/bin/env python3
"""Build compact scorer-unit matrix from existing ABHE runtime slot residual score JSONL files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
RUN_ROOT = Path("/tmp/abhe_v0_runtime_slot_controller_residual_dev_smoke")
MANIFEST = ROOT / "abhe_v0_runtime_slot_controller_residual_stress_slice_manifest.json"
OUTPUT = ROOT / "abhe_v0_runtime_slot_controller_scorer_unit_matrix.json"
MODEL_ALIAS = "gpt-4o-mini-2024-07-18-FC"
ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]
TARGET_CATEGORY = "multi_turn_miss_param"
NEXT_ACTION = "redesign_residual_slice_at_scorer_unit_level_or_enable_per_turn_scoring_before_more_bfcl"


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


def _score_path(arm: str, category: str) -> Path:
    family = "live" if category.startswith("live_") else ("multi_turn" if category.startswith("multi_turn") else "non_live")
    return RUN_ROOT / arm / category / "bfcl" / "score" / MODEL_ALIAS / family / f"BFCL_v4_{category}_score.json"


def _shape_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    if value is None:
        return 0
    return 1


def _record_shape(record: Dict[str, Any]) -> Dict[str, Any]:
    prompt = record.get("prompt") if isinstance(record.get("prompt"), dict) else {}
    error = record.get("error") if isinstance(record.get("error"), dict) else {}
    return {
        "valid": record.get("valid") is True,
        "scorer_unit_hash": _hash_text(str(record.get("id") or "missing-id")),
        "test_category": record.get("test_category"),
        "error_type_class": str(error.get("error_type") or "none"),
        "prompt_question_turn_count": _shape_count(prompt.get("question")),
        "prompt_initial_config_count": _shape_count(prompt.get("initial_config")),
        "model_result_decoded_count": _shape_count(record.get("model_result_decoded")),
        "model_result_shape_count": _shape_count(record.get("model_result_raw")),
        "inference_log_count": _shape_count(record.get("inference_log")),
        "raw_material_absent": True,
    }


def _parse_score(path: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    if not path.exists():
        return {"score_available": False}, []
    lines = [line for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    summary: Dict[str, Any] = {"score_available": False}
    records: List[Dict[str, Any]] = []
    for index, line in enumerate(lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if index == 0 and {"accuracy", "correct_count", "total_count"}.issubset(obj.keys()):
            summary = {
                "score_available": True,
                "accuracy": obj.get("accuracy"),
                "correct_count": obj.get("correct_count"),
                "total_count": obj.get("total_count"),
                "score_jsonl_line_count": len(lines),
            }
        else:
            records.append(_record_shape(obj))
    return summary, records


def build() -> Dict[str, Any]:
    manifest = _load(MANIFEST)
    categories = list((manifest.get("case_count_by_category") or {}).keys())
    rows: List[Dict[str, Any]] = []
    category_rows: List[Dict[str, Any]] = []
    for category in categories:
        selected_count = int((manifest.get("case_count_by_category") or {}).get(category) or 0)
        summaries: Dict[str, Any] = {}
        records_by_hash: Dict[str, Dict[str, Any]] = {}
        for arm in ARMS:
            summary, records = _parse_score(_score_path(arm, category))
            summaries[arm] = summary
            for record in records:
                h = record["scorer_unit_hash"]
                row = records_by_hash.setdefault(h, {"bfcl_category": category, "scorer_unit_hash": h, "arm_outcomes": {}})
                row["arm_outcomes"][arm] = record
        for row in records_by_hash.values():
            outcomes = row["arm_outcomes"]
            baseline_valid = (outcomes.get("baseline") or {}).get("valid") is True
            conditional_valid = (outcomes.get("conditional_frozen_v2") or {}).get("valid") is True
            runtime_valid = (outcomes.get("runtime_slot_controller_v2") or {}).get("valid") is True
            row["delta_conditional_vs_baseline"] = "fixed" if conditional_valid and not baseline_valid else ("regressed" if baseline_valid and not conditional_valid else "unchanged")
            row["delta_runtime_vs_conditional"] = "fixed" if runtime_valid and not conditional_valid else ("regressed" if conditional_valid and not runtime_valid else "unchanged")
            row["raw_material_absent"] = True
            rows.append(row)
        score_record_count = len(records_by_hash)
        category_rows.append({
            "bfcl_category": category,
            "selected_compact_case_count": selected_count,
            "score_record_count": score_record_count,
            "compact_to_score_record_factor": round(selected_count / max(1, score_record_count), 6) if selected_count else 0.0,
            "score_summary_by_arm": summaries,
            "strict_per_compact_case_pairing_available": selected_count == score_record_count and selected_count > 0,
            "raw_material_absent": True,
        })
    target = next((row for row in category_rows if row["bfcl_category"] == TARGET_CATEGORY), {})
    summary = {
        "selected_case_ids_hash": manifest.get("selected_case_ids_hash"),
        "selected_compact_case_count": manifest.get("selected_case_count"),
        "scorer_unit_row_count": len(rows),
        "target_category": TARGET_CATEGORY,
        "target_selected_compact_case_count": target.get("selected_compact_case_count"),
        "target_score_record_count": target.get("score_record_count"),
        "target_compact_to_score_record_factor": target.get("compact_to_score_record_factor"),
        "target_strict_per_compact_case_pairing_available": target.get("strict_per_compact_case_pairing_available"),
        "more_bfcl_before_alignment_recommended": False,
    }
    report: Dict[str, Any] = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_scorer_unit_matrix",
        "schema_version": "abhe_v0_runtime_slot_controller_scorer_unit_matrix_v0",
        "run_scope": "offline_score_jsonl_shape_parser_only_no_provider_no_bfcl_no_scorer",
        "bounded_dev_smoke_only": True,
        "summary": summary,
        "category_alignment_rows": category_rows,
        "scorer_unit_rows": rows,
        "next_required_action": NEXT_ACTION,
        "raw_material_absent": True,
        "prompt_literal_committed": False,
        "argument_values_committed": False,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "performance_evidence": False,
        "blockers": [],
    }
    if not rows:
        report["blockers"].append("scorer_unit_rows_missing")
    if not target or int(target.get("score_record_count") or 0) <= 0:
        report["blockers"].append("target_score_record_missing")
    if target and bool(target.get("strict_per_compact_case_pairing_available")):
        report["blockers"].append("target_unexpectedly_has_strict_compact_pairing")
    leakage_blockers = scan_value(report, label="abhe_v0_runtime_slot_controller_scorer_unit_matrix")
    if leakage_blockers:
        report["blockers"] = sorted(set(report["blockers"] + leakage_blockers))
    _write(OUTPUT, report)
    return report


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build()
    except Exception as exc:
        report = {"artifact_kind": "abhe_v0_runtime_slot_controller_scorer_unit_matrix", "blockers": [f"load_failed:{exc.__class__.__name__}"], "performance_evidence": False}
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
