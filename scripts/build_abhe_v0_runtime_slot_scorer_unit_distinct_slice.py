#!/usr/bin/env python3
"""Build a compact scorer-unit-distinct residual slice proposal for ABHE runtime slot work.

This is a no-execution gate. It rebuilds the residual stress slice with one
compact selected identifier per BFCL raw scorer unit and records only hashes,
counts, and boundary flags. It does not call provider, BFCL, or scorer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from scripts.build_abhe_v0_bfcl_fresh_dev_slice import (
    _category_file,
    _compact_case,
    _discovery_hashes,
    _iter_json_rows,
    _source_file_hash,
    selected_case_ids_hash,
)
from scripts.build_abhe_v0_runtime_slot_controller_residual_stress import (
    DEFAULT_DATASET,
    ENTRY_BY_CATEGORY,
    STRESS_COUNTS,
    _case_hash_set,
    _prior_hashes,
)
from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
OUTPUT = ROOT / "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json"
TARGET_CATEGORY = "multi_turn_miss_param"
NEXT_ACTION = "approve_bounded_rerun_only_after_true_per_selected_or_distinct_scorer_unit_output_gate"


def _hash_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _raw_id(raw: Any) -> Optional[str]:
    if not isinstance(raw, dict):
        return None
    value = raw.get("id")
    return value if isinstance(value, str) and value else None


def _select_distinct(dataset_path: Path, exclusion_hashes: set[str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[str]]:
    selected: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {}
    blockers: List[str] = []
    used_case_hashes = set(exclusion_hashes)
    used_raw_id_hashes_by_category: Dict[str, set[str]] = {}
    for category, target_count in STRESS_COUNTS.items():
        source_path = _category_file(dataset_path, category)
        if not source_path.exists():
            blockers.append(f"bfcl_category_file_missing:{category}")
            summary[category] = {"target_count": target_count, "selected_count": 0, "available_distinct_scorer_units": 0}
            continue
        source_hash = _source_file_hash(source_path)
        available_distinct: Dict[str, Dict[str, Any]] = {}
        skipped_prior_overlap = 0
        skipped_duplicate_raw_id = 0
        seen_raw_ids: set[str] = set()
        for row_index, raw in _iter_json_rows(source_path):
            raw_id = _raw_id(raw)
            if raw_id is None:
                continue
            raw_id_hash = _hash_text(raw_id)
            if raw_id_hash in seen_raw_ids:
                skipped_duplicate_raw_id += 1
                continue
            seen_raw_ids.add(raw_id_hash)
            compact = _compact_case(ENTRY_BY_CATEGORY[category], category, source_hash, row_index, raw)
            compact["slice_id"] = "runtime_slot_controller_scorer_unit_distinct_residual_v0"
            compact_hashes = _case_hash_set([compact])
            if compact_hashes.intersection(used_case_hashes):
                skipped_prior_overlap += 1
                continue
            compact["scorer_unit_hash"] = raw_id_hash
            compact["scorer_unit_distinct"] = True
            compact["raw_material_absent"] = True
            available_distinct[raw_id_hash] = compact
        picked = list(available_distinct.values())[:target_count]
        for compact in picked:
            selected.append(compact)
            used_case_hashes.update(_case_hash_set([compact]))
            used_raw_id_hashes_by_category.setdefault(category, set()).add(compact["scorer_unit_hash"])
        if len(picked) < target_count:
            blockers.append(f"insufficient_distinct_scorer_units:{category}:{len(picked)}<{target_count}")
        summary[category] = {
            "target_count": target_count,
            "selected_count": len(picked),
            "available_distinct_scorer_units": len(available_distinct),
            "selected_distinct_scorer_units": len(used_raw_id_hashes_by_category.get(category, set())),
            "skipped_prior_or_discovery_overlap": skipped_prior_overlap,
            "skipped_duplicate_raw_id": skipped_duplicate_raw_id,
            "source_file_hash": source_hash,
            "scorer_unit_distinct_selection_feasible": len(picked) == target_count,
        }
    return selected, summary, blockers


def build(dataset_path: Path = DEFAULT_DATASET) -> Dict[str, Any]:
    blockers: List[str] = []
    prior_hashes, prior_counts = _prior_hashes()
    discovery_hashes, discovery_count, discovery_by_file = _discovery_hashes()
    exclusion_hashes = set(prior_hashes).union(discovery_hashes)
    if not dataset_path.exists():
        selected: List[Dict[str, Any]] = []
        category_summary: Dict[str, Any] = {}
        blockers.append("bfcl_dataset_path_missing")
    else:
        selected, category_summary, select_blockers = _select_distinct(dataset_path, exclusion_hashes)
        blockers.extend(select_blockers)
    selected_hash = selected_case_ids_hash(selected) if selected else "pending"
    selected_hashes = _case_hash_set(selected)
    discovery_overlap = sorted(selected_hashes.intersection(discovery_hashes))
    prior_overlap = sorted(selected_hashes.intersection(prior_hashes))
    if discovery_overlap:
        blockers.append("archive_source_overlap_detected")
    if prior_overlap:
        blockers.append("prior_slice_overlap_detected")
    case_count_by_category = {category: sum(1 for row in selected if row.get("bfcl_category") == category) for category in STRESS_COUNTS}
    scorer_units_by_category = {
        category: len({str(row.get("scorer_unit_hash")) for row in selected if row.get("bfcl_category") == category})
        for category in STRESS_COUNTS
    }
    target_selected = case_count_by_category.get(TARGET_CATEGORY, 0)
    target_units = scorer_units_by_category.get(TARGET_CATEGORY, 0)
    distinct_ready = not blockers and all(case_count_by_category.get(cat, 0) == count for cat, count in STRESS_COUNTS.items()) and all(scorer_units_by_category.get(cat, 0) == case_count_by_category.get(cat, 0) for cat in STRESS_COUNTS)
    report: Dict[str, Any] = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan",
        "schema_version": "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan_v0",
        "run_scope": "offline_dataset_hash_selection_only_no_provider_no_bfcl_no_scorer",
        "bounded_dev_smoke_only": True,
        "selected_dataset_path": str(dataset_path),
        "slice_id": "runtime_slot_controller_scorer_unit_distinct_residual_v0",
        "scorer_unit_distinct_slice_ready": distinct_ready,
        "selected_case_ids_hash": selected_hash,
        "selected_case_count": len(selected),
        "case_count_by_category": case_count_by_category,
        "scorer_unit_count_by_category": scorer_units_by_category,
        "category_selection_summary": category_summary,
        "target_category": TARGET_CATEGORY,
        "target_selected_compact_case_count": target_selected,
        "target_unique_scorer_unit_count": target_units,
        "target_compact_to_scorer_unit_factor": round(target_selected / max(1, target_units), 6),
        "selected_compact_case_identifiers": selected,
        "overlap_check_status": "complete" if not discovery_overlap and not prior_overlap else "blocked",
        "discovery_source_hash_count": discovery_count,
        "prior_slice_source_hash_count": len(prior_hashes),
        "prior_slice_source_counts": prior_counts,
        "archive_source_overlap_count": len(discovery_overlap),
        "prior_slice_overlap_count": len(prior_overlap),
        "overlap_hashes": discovery_overlap + prior_overlap,
        "source_160_compact_cases_reused_for_validation": False,
        "archive_seed_source_excluded": not discovery_overlap,
        "old_dev_slices_excluded": not prior_overlap,
        "true_per_selected_id_scoring_enabled": False,
        "bfcl_scorer_output_contract_required": "score_jsonl_must_emit_one_record_per_selected_scorer_unit_or_turn_before_more_bfcl",
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
    leakage_blockers = scan_value(report, label="abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan")
    if leakage_blockers:
        report["blockers"] = sorted(set(report["blockers"] + leakage_blockers))
        report["scorer_unit_distinct_slice_ready"] = False
    return report


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build(args.dataset_path)
        if args.write:
            _write(OUTPUT, report)
    except Exception as exc:
        report = {
            "artifact_kind": "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan",
            "blockers": [f"load_failed:{exc.__class__.__name__}"],
            "performance_evidence": False,
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
