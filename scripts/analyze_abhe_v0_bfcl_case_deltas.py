#!/usr/bin/env python3
"""Build compact ABHE-v0 BFCL paired delta diagnostics without raw persistence."""
from __future__ import annotations

import argparse
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List

from scripts.run_abhe_v0_bfcl_dev_smoke import EXPECTED_HASH, _selected_raw_ids
from scripts.check_abhe_no_leakage_boundary import scan_value

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_OUTPUT = ARTIFACT_ROOT / "abhe_v0_bfcl_case_delta_analysis.json"
DEFAULT_BASELINE_ROOT = Path("/tmp/abhe_v0_bfcl_dev_smoke/baseline")
DEFAULT_CANDIDATE_ROOT = Path("/tmp/abhe_v0_bfcl_dev_smoke/candidate")
DEFAULT_FRESH_MANIFEST = ARTIFACT_ROOT / "abhe_v0_bfcl_fresh_dev_slice_manifest.json"
MODEL_ALIAS = "gpt-4o-mini-2024-07-18-FC"
CATEGORY_RESULT_PATHS = {
    "multi_turn_base": "multi_turn/BFCL_v4_multi_turn_base_result.json",
    "multi_turn_long_context": "multi_turn/BFCL_v4_multi_turn_long_context_result.json",
    "multi_turn_miss_func": "multi_turn/BFCL_v4_multi_turn_miss_func_result.json",
    "multi_turn_miss_param": "multi_turn/BFCL_v4_multi_turn_miss_param_result.json",
    "irrelevance": "non_live/BFCL_v4_irrelevance_result.json",
    "live_irrelevance": "live/BFCL_v4_live_irrelevance_result.json",
    "live_relevance": "live/BFCL_v4_live_relevance_result.json",
}


def _hash_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _score_file(root: Path, category: str) -> Path:
    family = "live" if category.startswith("live_") else ("multi_turn" if category.startswith("multi_turn") else "non_live")
    return root / "bfcl/score" / MODEL_ALIAS / family / f"BFCL_v4_{category}_score.json"


def _parse_score(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"score_available": False, "blocker": "score_file_missing"}
    lines = [line for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    summary: Dict[str, Any] = {}
    records: List[Dict[str, Any]] = []
    try:
        parsed = json.loads("\n".join(lines))
        if isinstance(parsed, dict):
            summary = parsed
    except json.JSONDecodeError:
        for index, line in enumerate(lines):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and index == 0 and "accuracy" in obj:
                summary = obj
            elif isinstance(obj, dict):
                records.append(obj)
    accuracy = summary.get("accuracy")
    correct_count = summary.get("correct_count")
    total_count = summary.get("total_count")
    passed = bool(total_count and correct_count == total_count)
    failure_records = [r for r in records if r.get("valid") is False]
    reason_classes = sorted({str(r.get("error_type") or "score_failure") for r in failure_records})
    return {
        "score_available": bool(summary),
        "accuracy": accuracy,
        "correct_count": correct_count,
        "total_count": total_count,
        "pass": passed,
        "failure_record_count": len(failure_records),
        "compact_reason_classes": reason_classes,
    }


def _result_file(root: Path, category: str) -> Path:
    return root / "bfcl/result" / MODEL_ALIAS / CATEGORY_RESULT_PATHS[category]


def _count_function_calls(value: Any) -> int:
    if isinstance(value, dict):
        count = 0
        if isinstance(value.get("function"), str) or isinstance(value.get("name"), str):
            count += 1
        for item in value.values():
            count += _count_function_calls(item)
        return count
    if isinstance(value, list):
        return sum(_count_function_calls(item) for item in value)
    return 0


def _collect_function_names(value: Any, names: set[str]) -> None:
    if isinstance(value, dict):
        for key in ("function", "name"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                names.add(item.strip())
        for item in value.values():
            _collect_function_names(item, names)
    elif isinstance(value, list):
        for item in value:
            _collect_function_names(item, names)


def _result_shape(root: Path, category: str) -> Dict[str, Any]:
    path = _result_file(root, category)
    if not path.exists():
        return {"result_available": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"result_available": False, "result_parse_status": "json_parse_failed"}
    shape = data.get("grc_decoded_execution_output_shape") if isinstance(data, dict) else None
    names: set[str] = set()
    if isinstance(data, dict):
        _collect_function_names(data.get("result"), names)
    return {
        "result_available": True,
        "decoded_output_count": shape.get("decoded_output_count") if isinstance(shape, dict) else None,
        "function_call_shape_present": shape.get("function_call_shape_present") if isinstance(shape, dict) else None,
        "shape_label": shape.get("shape_label") if isinstance(shape, dict) else None,
        "tool_call_count_compact": _count_function_calls(data.get("result") if isinstance(data, dict) else None),
        "selected_tool_name_hashes": [_short_hash(name) for name in sorted(names)],
    }


def _trace_patch_counts(root: Path) -> Dict[str, int]:
    trace_root = root / "traces"
    counts: Dict[str, int] = {}
    if not trace_root.exists():
        return counts
    for path in trace_root.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        validation = data.get("validation") if isinstance(data, dict) else None
        patches = validation.get("request_patches") if isinstance(validation, dict) else []
        if not isinstance(patches, list):
            continue
        for patch in patches:
            text = str(patch)
            if text.startswith("abhe_v0_runtime_candidate_adapter_guidance"):
                counts[text] = counts.get(text, 0) + 1
    return counts


def _delta_label(base_pass: bool | None, cand_pass: bool | None) -> str:
    if base_pass is None or cand_pass is None:
        return "unknown_score_unavailable"
    if not base_pass and cand_pass:
        return "fixed"
    if base_pass and not cand_pass:
        return "regressed"
    if base_pass and cand_pass:
        return "unchanged_pass"
    return "unchanged_fail"


def _category_rows(ids_by_category: Dict[str, List[str]], entry_by_category: Dict[str, str], baseline_root: Path, candidate_root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for category, raw_ids in ids_by_category.items():
        unique_hashes = sorted({_hash_text(raw_id) for raw_id in raw_ids})
        baseline_score = _parse_score(_score_file(baseline_root, category))
        candidate_score = _parse_score(_score_file(candidate_root, category))
        baseline_pass = baseline_score.get("pass") if baseline_score.get("score_available") else None
        candidate_pass = candidate_score.get("pass") if candidate_score.get("score_available") else None
        rows.append({
            "entry_id": entry_by_category.get(category, "unknown"),
            "bfcl_category": category,
            "selected_compact_case_count": len(raw_ids),
            "unique_scorer_unit_count": len(unique_hashes),
            "scorer_unit_hashes": unique_hashes,
            "baseline_pass": baseline_pass,
            "candidate_pass": candidate_pass,
            "delta": _delta_label(baseline_pass, candidate_pass),
            "baseline_score_summary": {k: baseline_score.get(k) for k in ["score_available", "accuracy", "correct_count", "total_count", "failure_record_count", "compact_reason_classes"]},
            "candidate_score_summary": {k: candidate_score.get(k) for k in ["score_available", "accuracy", "correct_count", "total_count", "failure_record_count", "compact_reason_classes"]},
            "baseline_result_shape": _result_shape(baseline_root, category),
            "candidate_result_shape": _result_shape(candidate_root, category),
        })
    return rows


def _compact_rows(manifest: Dict[str, Any], ids_by_category: Dict[str, List[str]], category_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    category_by_name = {row["bfcl_category"]: row for row in category_rows}
    occurrences: Dict[str, int] = {}
    rows: List[Dict[str, Any]] = []
    for item in manifest.get("selected_compact_case_identifiers", []):
        if not isinstance(item, dict):
            continue
        category = str(item.get("bfcl_category"))
        occurrence = occurrences.get(category, 0)
        occurrences[category] = occurrence + 1
        raw_ids = ids_by_category.get(category, [])
        scorer_hash = _hash_text(raw_ids[min(occurrence, len(raw_ids) - 1)]) if raw_ids else None
        category_row = category_by_name.get(category, {})
        rows.append({
            "entry_id": item.get("entry_id"),
            "bfcl_category": category,
            "case_hash": item.get("case_stable_hash"),
            "case_row_index_hash": item.get("case_row_index_hash"),
            "case_identifier_hash": item.get("case_identifier_hash"),
            "scorer_unit_hash": scorer_hash,
            "pass_resolution": "category_scorer_unit_inherited_not_strict_per_compact_case",
            "baseline_pass": category_row.get("baseline_pass"),
            "candidate_pass": category_row.get("candidate_pass"),
            "delta": category_row.get("delta"),
        })
    return rows


def build_analysis(
    *,
    baseline_root: Path = DEFAULT_BASELINE_ROOT,
    candidate_root: Path = DEFAULT_CANDIDATE_ROOT,
    fresh_manifest_path: Path = DEFAULT_FRESH_MANIFEST,
) -> Dict[str, Any]:
    manifest = _load(fresh_manifest_path)
    ids_by_category, _entry_by_run_id, entry_by_category = _selected_raw_ids()
    category_rows = _category_rows(ids_by_category, entry_by_category, baseline_root, candidate_root)
    compact_rows = _compact_rows(manifest, ids_by_category, category_rows)
    strict_fixed = sum(1 for row in category_rows if row["delta"] == "fixed")
    strict_regressed = sum(1 for row in category_rows if row["delta"] == "regressed")
    scaled_fixed = sum(int(row["selected_compact_case_count"]) for row in category_rows if row["delta"] == "fixed")
    scaled_regressed = sum(int(row["selected_compact_case_count"]) for row in category_rows if row["delta"] == "regressed")
    unique_units = sorted({h for row in category_rows for h in row.get("scorer_unit_hashes", [])})
    selected_count = len(compact_rows)
    patch_counts = _trace_patch_counts(candidate_root)
    analysis = {
        "artifact_kind": "abhe_v0_bfcl_case_delta_analysis",
        "schema_version": "abhe_v0_bfcl_case_delta_analysis_v0",
        "bounded_dev_smoke_only": True,
        "selected_case_ids_hash": EXPECTED_HASH,
        "selected_compact_case_count": selected_count,
        "unique_bfcl_scorer_unit_count": len(unique_units),
        "strict_per_compact_case_paired_available": selected_count == len(unique_units),
        "case_delta_resolution": "category_scorer_unit" if selected_count != len(unique_units) else "compact_case",
        "aggregate_feedback_fixed_count_is_scaled_category_delta": selected_count != len(unique_units),
        "strict_scorer_unit_fixed_count": strict_fixed,
        "strict_scorer_unit_regressed_count": strict_regressed,
        "scaled_compact_fixed_count": scaled_fixed,
        "scaled_compact_regressed_count": scaled_regressed,
        "state_tracking_signal_summary": "weak_positive_from_multi_turn_miss_param_only" if any(row["bfcl_category"] == "multi_turn_miss_param" and row["delta"] == "fixed" for row in category_rows) else "no_state_tracking_fixed_scorer_unit",
        "hallucination_abstain_signal_summary": "no_mechanism_signal" if all(row["delta"] != "fixed" for row in category_rows if row["entry_id"] == "hallucination_abstain_v0") else "has_fixed_scorer_unit",
        "candidate_activation_telemetry": {
            "candidate_patch_counts": patch_counts,
            "global_guidance_detected": any(key == "abhe_v0_runtime_candidate_adapter_guidance" for key in patch_counts),
            "entry_specific_guidance_detected": any(key.startswith("abhe_v0_runtime_candidate_adapter_guidance:") for key in patch_counts),
        },
        "category_delta_rows": category_rows,
        "compact_case_delta_rows": compact_rows,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "performance_evidence": False,
        "next_required_action": "review_entry_specific_activation_rerun_before_any_archive_write",
        "blockers": [],
    }
    analysis["blockers"] = sorted(set(scan_value(analysis, label="abhe_v0_bfcl_case_delta_analysis")))
    analysis["abhe_v0_bfcl_case_delta_analysis_passed"] = not analysis["blockers"]
    return analysis


def write_analysis(path: Path, analysis: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, default=DEFAULT_BASELINE_ROOT)
    parser.add_argument("--candidate-root", type=Path, default=DEFAULT_CANDIDATE_ROOT)
    parser.add_argument("--fresh-manifest", type=Path, default=DEFAULT_FRESH_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        analysis = build_analysis(baseline_root=args.baseline_root, candidate_root=args.candidate_root, fresh_manifest_path=args.fresh_manifest)
        if args.write:
            write_analysis(args.output, analysis)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        analysis = {
            "report_scope": "abhe_v0_bfcl_case_delta_analysis",
            "abhe_v0_bfcl_case_delta_analysis_passed": False,
            "raw_material_absent": True,
            "performance_evidence": False,
            "blockers": [f"load_failed:{exc.__class__.__name__}"],
        }
    print(json.dumps(analysis, sort_keys=True) if args.compact else json.dumps(analysis, indent=2, sort_keys=True))
    return 1 if args.strict and not analysis.get("abhe_v0_bfcl_case_delta_analysis_passed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
