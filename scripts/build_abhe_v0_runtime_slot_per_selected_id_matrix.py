#!/usr/bin/env python3
"""Build compact per-selected-id and per-turn shape matrix for ABHE runtime slot residual runs.

This parser reads existing raw-only BFCL residual run outputs under /tmp and
persists only hashes, counts, booleans, and enum-like labels. It deliberately
marks scorer pass/fail as scorer-unit inherited when BFCL collapses multiple
selected compact identifiers into one scorer record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from scripts.build_abhe_v0_bfcl_fresh_dev_slice import (
    _category_file,
    _compact_case,
    _iter_json_rows,
    _source_file_hash,
)
from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
RUN_ROOT = Path("/tmp/abhe_v0_runtime_slot_controller_residual_dev_smoke")
MANIFEST = ROOT / "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json"
OUTPUT = ROOT / "abhe_v0_runtime_slot_controller_per_selected_id_matrix.json"
MODEL_ALIAS = "gpt-4o-mini-2024-07-18-FC"
ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]
TARGET_CATEGORY = "multi_turn_miss_param"
NEXT_ACTION = "fix_score_output_contract_or_enable_true_per_selected_or_per_turn_scoring_before_more_bfcl"
FALSE_FIELDS = [
    "prompt_literal_committed",
    "argument_values_committed",
    "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed",
    "gold_expected_committed",
    "scorer_diff_committed",
    "provider_calls_made",
    "bfcl_generate_called",
    "bfcl_evaluate_called",
    "scorer_called",
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


def _score_path(arm: str, category: str) -> Path:
    family = "live" if category.startswith("live_") else ("multi_turn" if category.startswith("multi_turn") else "non_live")
    return RUN_ROOT / arm / category / "bfcl" / "score" / MODEL_ALIAS / family / f"BFCL_v4_{category}_score.json"


def _result_path(arm: str, category: str) -> Path:
    family = "live" if category.startswith("live_") else ("multi_turn" if category.startswith("multi_turn") else "non_live")
    return RUN_ROOT / arm / category / "bfcl" / "result" / MODEL_ALIAS / family / f"BFCL_v4_{category}_result.json"


def _trace_dir(arm: str, category: str) -> Path:
    return RUN_ROOT / arm / category / "traces"


def _shape_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    if value is None:
        return 0
    return 1


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


def _score_summary_and_records(path: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    summary: Dict[str, Any] = {"score_available": False}
    records: List[Dict[str, Any]] = []
    for index, obj in enumerate(_iter_jsonl(path)):
        if index == 0 and {"accuracy", "correct_count", "total_count"}.issubset(obj.keys()):
            summary = {
                "score_available": True,
                "accuracy": obj.get("accuracy"),
                "correct_count": obj.get("correct_count"),
                "total_count": obj.get("total_count"),
            }
            continue
        prompt = obj.get("prompt") if isinstance(obj.get("prompt"), dict) else {}
        error = obj.get("error") if isinstance(obj.get("error"), dict) else {}
        records.append({
            "scorer_unit_hash": _hash_text(str(obj.get("id") or "missing-id")),
            "valid": obj.get("valid") is True,
            "error_type_class": str(error.get("error_type") or "none"),
            "prompt_question_turn_count": _shape_count(prompt.get("question")),
            "prompt_initial_config_count": _shape_count(prompt.get("initial_config")),
            "model_result_decoded_turn_count": _shape_count(obj.get("model_result_decoded")),
            "model_result_raw_shape_count": _shape_count(obj.get("model_result_raw")),
            "inference_log_count": _shape_count(obj.get("inference_log")),
            "raw_material_absent": True,
        })
    return summary, records


def _load_result_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    records = obj if isinstance(obj, list) else [obj]
    out: List[Dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        out.append({
            "scorer_unit_hash": _hash_text(str(item.get("id") or "missing-id")),
            "result_turn_count": _shape_count(item.get("result")),
            "inference_log_count": _shape_count(item.get("inference_log")),
            "input_token_count_present": item.get("input_token_count") is not None,
            "output_token_count_present": item.get("output_token_count") is not None,
            "latency_present": item.get("latency") is not None,
            "grc_decoded_execution_output_shape_count": _shape_count(item.get("grc_decoded_execution_output_shape")),
            "raw_material_absent": True,
        })
    return out


def _trace_summary(arm: str, category: str) -> Dict[str, Any]:
    directory = _trace_dir(arm, category)
    files = sorted(directory.rglob("*.json")) if directory.exists() else []
    repair_kind_counts: Dict[str, int] = {}
    failure_label_counts: Dict[str, int] = {}
    request_patch_counts: Dict[str, int] = {}
    issue_count = 0
    policy_hit_count = 0
    latency_present_count = 0
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        validation = data.get("validation") if isinstance(data.get("validation"), dict) else {}
        for key in validation.get("repair_kinds") or []:
            if isinstance(key, str):
                repair_kind_counts[key] = repair_kind_counts.get(key, 0) + 1
        for key in validation.get("failure_labels") or []:
            if isinstance(key, str):
                failure_label_counts[key] = failure_label_counts.get(key, 0) + 1
        for key in validation.get("request_patches") or []:
            if isinstance(key, str):
                request_patch_counts[key] = request_patch_counts.get(key, 0) + 1
        issue_count += _shape_count(validation.get("issues"))
        policy_hit_count += _shape_count(validation.get("policy_hits"))
        if data.get("latency_ms") is not None:
            latency_present_count += 1
    return {
        "trace_file_count": len(files),
        "trace_file_hashes": [_hash_text(path.name) for path in files[:12]],
        "trace_hash_sample_truncated": len(files) > 12,
        "repair_kind_counts": repair_kind_counts,
        "failure_label_counts": failure_label_counts,
        "request_patch_counts": request_patch_counts,
        "issue_count": issue_count,
        "policy_hit_count": policy_hit_count,
        "latency_present_count": latency_present_count,
        "safe_trace_fields_only": True,
        "raw_material_absent": True,
    }


def _category_cache(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    dataset_path = Path(str(manifest.get("selected_dataset_path")))
    manifest_rows = [row for row in manifest.get("selected_compact_case_identifiers") or [] if isinstance(row, dict)]
    categories = sorted({str(row.get("bfcl_category")) for row in manifest_rows})
    entry_ids = sorted({str(row.get("entry_id")) for row in manifest_rows})
    cache: Dict[str, Dict[str, Any]] = {}
    for category in categories:
        source_path = _category_file(dataset_path, category)
        source_hash = _source_file_hash(source_path)
        compact_by_key: Dict[Tuple[str, str, str, str, str], Dict[str, Any]] = {}
        for row_index, raw in _iter_json_rows(source_path):
            raw_id = raw.get("id") if isinstance(raw, dict) else None
            if not isinstance(raw_id, str) or not raw_id:
                continue
            for entry_id in entry_ids:
                compact = _compact_case(entry_id, category, source_hash, row_index, raw)
                key = (compact["entry_id"], compact["bfcl_category"], compact["source_file_hash"], compact["case_stable_hash"], compact["case_row_index_hash"])
                compact_by_key[key] = {
                    "dataset_raw_id_hash": _hash_text(raw_id),
                    "source_row_index_hash": compact["case_row_index_hash"],
                    "case_stable_hash": compact["case_stable_hash"],
                }
        cache[category] = {"source_hash": source_hash, "compact_by_key": compact_by_key}
    return cache


def _selected_rows(manifest: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    cache = _category_cache(manifest)
    rows: List[Dict[str, Any]] = []
    blockers: List[str] = []
    counter_by_unit: Dict[str, int] = {}
    for index, row in enumerate(manifest.get("selected_compact_case_identifiers") or []):
        if not isinstance(row, dict):
            blockers.append("selected_row_not_object")
            continue
        category = str(row.get("bfcl_category"))
        key = (str(row.get("entry_id")), category, str(row.get("source_file_hash")), str(row.get("case_stable_hash")), str(row.get("case_row_index_hash")))
        found = (cache.get(category) or {}).get("compact_by_key", {}).get(key)
        if not found:
            blockers.append(f"selected_row_dataset_raw_id_not_found:{category}")
            dataset_raw_id_hash = "sha256:missing"
        else:
            dataset_raw_id_hash = found["dataset_raw_id_hash"]
        unit_key = f"{category}:{dataset_raw_id_hash}"
        counter_by_unit[unit_key] = counter_by_unit.get(unit_key, 0) + 1
        rows.append({
            "selected_index": index,
            "entry_id": row.get("entry_id"),
            "bfcl_category": category,
            "case_identifier_hash": row.get("case_identifier_hash"),
            "case_stable_hash": row.get("case_stable_hash"),
            "case_row_index_hash": row.get("case_row_index_hash"),
            "dataset_raw_id_hash": dataset_raw_id_hash,
            "scorer_unit_hash": "pending_score_record_alignment",
            "selected_index_within_dataset_raw_id": counter_by_unit[unit_key] - 1,
            "per_selected_pass_available": False,
            "pass_inherited_from_scorer_unit": True,
            "turn_index_mapping_available": False,
            "turn_index_mapping_blocker": "bfcl_score_record_collapses_multiple_selected_compact_identifiers",
            "raw_material_absent": True,
        })
    return rows, blockers


def build() -> Dict[str, Any]:
    manifest = _load(MANIFEST)
    selected_rows, blockers = _selected_rows(manifest)
    selected_by_category: Dict[str, List[Dict[str, Any]]] = {}
    for row in selected_rows:
        selected_by_category.setdefault(row["bfcl_category"], []).append(row)

    scorer_unit_rows: List[Dict[str, Any]] = []
    per_turn_shape_rows: List[Dict[str, Any]] = []
    trace_summaries: Dict[str, Any] = {}
    for category, category_selected_rows in selected_by_category.items():
        scorer_units_in_selected = sorted({row["scorer_unit_hash"] for row in category_selected_rows})
        for arm in ARMS:
            score_summary, score_records = _score_summary_and_records(_score_path(arm, category))
            result_records = _load_result_records(_result_path(arm, category))
            trace_summaries[f"{arm}:{category}"] = _trace_summary(arm, category)
            records_by_hash = {record["scorer_unit_hash"]: record for record in score_records}
            result_by_hash = {record["scorer_unit_hash"]: record for record in result_records}
            actual_score_units = sorted(set(records_by_hash) | set(result_by_hash))
            if arm == ARMS[0]:
                if len(actual_score_units) == 1:
                    for selected_row in category_selected_rows:
                        selected_row["scorer_unit_hash"] = actual_score_units[0]
                        selected_row["scorer_alignment_method"] = "single_score_record_category_level_inheritance"
                elif actual_score_units:
                    matched_units = set(actual_score_units)
                    for selected_row in category_selected_rows:
                        if selected_row.get("dataset_raw_id_hash") in matched_units:
                            selected_row["scorer_unit_hash"] = selected_row["dataset_raw_id_hash"]
                            selected_row["scorer_alignment_method"] = "dataset_raw_id_hash_match"
                        else:
                            selected_row["scorer_alignment_method"] = "score_record_alignment_unavailable"
                else:
                    for selected_row in category_selected_rows:
                        selected_row["scorer_alignment_method"] = "score_record_missing"
                scorer_units_in_selected = sorted({row["scorer_unit_hash"] for row in category_selected_rows})
            for scorer_unit_hash in sorted(set(scorer_units_in_selected) | set(records_by_hash) | set(result_by_hash)):
                selected_count = sum(1 for row in category_selected_rows if row["scorer_unit_hash"] == scorer_unit_hash)
                score_record = records_by_hash.get(scorer_unit_hash, {})
                result_record = result_by_hash.get(scorer_unit_hash, {})
                scorer_unit_rows.append({
                    "arm": arm,
                    "bfcl_category": category,
                    "scorer_unit_hash": scorer_unit_hash,
                    "selected_compact_case_count": selected_count,
                    "score_record_present": bool(score_record),
                    "result_record_present": bool(result_record),
                    "scorer_unit_valid": score_record.get("valid") if score_record else None,
                    "error_type_class": score_record.get("error_type_class", "missing_score_record"),
                    "prompt_question_turn_count": score_record.get("prompt_question_turn_count"),
                    "model_result_decoded_turn_count": score_record.get("model_result_decoded_turn_count"),
                    "result_turn_count": result_record.get("result_turn_count"),
                    "inference_log_count": max(int(score_record.get("inference_log_count") or 0), int(result_record.get("inference_log_count") or 0)),
                    "strict_per_selected_id_result_available": selected_count == 1,
                    "raw_material_absent": True,
                })
                max_turns = max(int(score_record.get("model_result_decoded_turn_count") or 0), int(result_record.get("result_turn_count") or 0))
                for turn_index in range(max_turns):
                    per_turn_shape_rows.append({
                        "arm": arm,
                        "bfcl_category": category,
                        "scorer_unit_hash": scorer_unit_hash,
                        "turn_index_proxy": turn_index,
                        "selected_id_mapping_available": False,
                        "selected_id_mapping_blocker": "bfcl_output_turns_do_not_expose_selected_compact_identifier",
                        "scorer_unit_valid": score_record.get("valid") if score_record else None,
                        "per_turn_pass_available": False,
                        "pass_inherited_from_scorer_unit": True,
                        "raw_material_absent": True,
                    })

    for row in selected_rows:
        arm_outcomes: Dict[str, Any] = {}
        for unit_row in scorer_unit_rows:
            if unit_row["bfcl_category"] == row["bfcl_category"] and unit_row["scorer_unit_hash"] == row["scorer_unit_hash"]:
                arm_outcomes[unit_row["arm"]] = {
                    "scorer_unit_valid": unit_row.get("scorer_unit_valid"),
                    "inherited_not_independent": True,
                    "error_type_class": unit_row.get("error_type_class"),
                }
        row["arm_outcomes"] = arm_outcomes

    target_selected = [row for row in selected_rows if row["bfcl_category"] == TARGET_CATEGORY]
    target_units = sorted({row["scorer_unit_hash"] for row in target_selected})
    selected_scorer_units_by_category = manifest.get("scorer_unit_count_by_category") if isinstance(manifest.get("scorer_unit_count_by_category"), dict) else {}
    category_summaries: List[Dict[str, Any]] = []
    for category, rows in sorted(selected_by_category.items()):
        observed_units = sorted({row["scorer_unit_hash"] for row in rows})
        selected_scorer_unit_count = int(selected_scorer_units_by_category.get(category) or len(rows))
        category_summaries.append({
            "bfcl_category": category,
            "selected_compact_case_count": len(rows),
            "selected_scorer_unit_count": selected_scorer_unit_count,
            "observed_score_record_count": len(observed_units),
            "unique_scorer_unit_count": len(observed_units),
            "compact_to_observed_score_record_factor": round(len(rows) / max(1, len(observed_units)), 6),
            "compact_to_scorer_unit_factor": round(len(rows) / max(1, len(observed_units)), 6),
            "strict_per_selected_id_pairing_available": len(rows) == len(observed_units),
            "raw_material_absent": True,
        })

    target_selected_scorer_unit_count = int(selected_scorer_units_by_category.get(TARGET_CATEGORY) or manifest.get("target_unique_scorer_unit_count") or len(target_selected))
    target_observed_score_record_count = len(target_units)
    summary = {
        "selected_case_ids_hash": manifest.get("selected_case_ids_hash"),
        "selected_compact_case_count": manifest.get("selected_case_count"),
        "selected_row_count": len(selected_rows),
        "observed_score_record_row_count": len(scorer_unit_rows),
        "scorer_unit_row_count": len(scorer_unit_rows),
        "per_turn_shape_row_count": len(per_turn_shape_rows),
        "target_category": TARGET_CATEGORY,
        "target_selected_compact_case_count": len(target_selected),
        "target_selected_scorer_unit_count": target_selected_scorer_unit_count,
        "target_observed_score_record_count": target_observed_score_record_count,
        "target_unique_scorer_unit_count": target_observed_score_record_count,
        "target_compact_to_observed_score_record_factor": round(len(target_selected) / max(1, target_observed_score_record_count), 6),
        "target_compact_to_scorer_unit_factor": round(len(target_selected) / max(1, target_observed_score_record_count), 6),
        "target_per_selected_id_pass_available": False,
        "target_pass_is_scorer_unit_inherited": True,
        "target_true_per_selected_or_per_turn_scoring_available": False,
        "strict_per_selected_id_pairing_available": all(row["strict_per_selected_id_pairing_available"] for row in category_summaries),
        "more_bfcl_before_alignment_recommended": False,
    }
    report: Dict[str, Any] = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_per_selected_id_matrix",
        "schema_version": "abhe_v0_runtime_slot_controller_per_selected_id_matrix_v0",
        "run_scope": "offline_raw_tmp_shape_parser_only_no_provider_no_bfcl_no_scorer",
        "bounded_dev_smoke_only": True,
        "summary": summary,
        "category_summaries": category_summaries,
        "selected_id_rows": selected_rows,
        "scorer_unit_rows": scorer_unit_rows,
        "per_turn_shape_rows": per_turn_shape_rows,
        "trace_shape_summaries": trace_summaries,
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
        "blockers": blockers,
    }
    if not selected_rows:
        report["blockers"].append("selected_id_rows_missing")
    if not scorer_unit_rows:
        report["blockers"].append("scorer_unit_rows_missing")
    if not per_turn_shape_rows:
        report["blockers"].append("per_turn_shape_rows_missing")
    if summary["target_unique_scorer_unit_count"] <= 0:
        report["blockers"].append("target_scorer_unit_missing")
    if summary["target_per_selected_id_pass_available"] is not False:
        report["blockers"].append("target_per_selected_id_pass_must_be_false_until_true_turn_scoring")
    leakage_blockers = scan_value(report, label="abhe_v0_runtime_slot_controller_per_selected_id_matrix")
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
        report = {
            "artifact_kind": "abhe_v0_runtime_slot_controller_per_selected_id_matrix",
            "blockers": [f"load_failed:{exc.__class__.__name__}"],
            "performance_evidence": False,
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
