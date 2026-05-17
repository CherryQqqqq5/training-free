#!/usr/bin/env python3
"""Build ABHE-v0 next fresh-slice verification artifacts.

This materializes compact identifiers for a new balanced verification slice and
an additional residual stress slice. It never persists disallowed benchmark or
provider material.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from scripts.build_abhe_v0_bfcl_fresh_dev_slice import (
    _category_file,
    _compact_case,
    _discovery_hashes,
    _iter_json_rows,
    _source_file_hash,
    selected_case_ids_hash,
)
from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_DATASET = Path(".venv/lib/python3.10/site-packages/bfcl_eval/data")
PREVIOUS_20 = ROOT / "abhe_v0_bfcl_fresh_dev_slice_manifest.json"
PREVIOUS_EXPANDED = ROOT / "abhe_v0_expanded_bfcl_fresh_dev_slice_manifest.json"
PLAN = ROOT / "abhe_v0_next_fresh_slice_plan.json"
MANIFEST = ROOT / "abhe_v0_next_fresh_slice_manifest.json"
PROOF = ROOT / "abhe_v0_next_source_exclusion_proof.json"

BALANCED_COUNTS = {
    "multi_turn_base": 8,
    "multi_turn_long_context": 8,
    "multi_turn_miss_func": 8,
    "multi_turn_miss_param": 8,
    "irrelevance": 8,
    "live_irrelevance": 8,
    "live_relevance": 6,
}
STRESS_COUNTS = {
    "multi_turn_long_context": 10,
    "multi_turn_miss_param": 10,
    "multi_turn_base": 4,
    "multi_turn_miss_func": 4,
    "live_relevance": 1,
}
ENTRY_BY_CATEGORY = {
    "multi_turn_base": "post_tool_continuation_guard_v0",
    "multi_turn_long_context": "long_context_state_retrieval_v0",
    "multi_turn_miss_func": "post_tool_continuation_guard_v0",
    "multi_turn_miss_param": "missing_param_epistemic_gate_v0",
    "irrelevance": "no_tool_boundary_regression_suite",
    "live_irrelevance": "no_tool_boundary_regression_suite",
    "live_relevance": "no_tool_boundary_regression_suite",
}
BALANCED_START_ROW_INDEX = 20
STRESS_START_ROW_INDEX = 20
CATEGORY_START_ROW_OVERRIDES = {"live_relevance": 0}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _prior_hashes() -> tuple[set[str], Dict[str, int]]:
    out: set[str] = set()
    counts: Dict[str, int] = {}
    for path in [PREVIOUS_20, PREVIOUS_EXPANDED]:
        if not path.exists():
            counts[str(path)] = 0
            continue
        data = _load(path)
        rows = data.get("selected_compact_case_identifiers") or []
        counts[str(path)] = len(rows) if isinstance(rows, list) else 0
        for item in rows:
            if not isinstance(item, dict):
                continue
            for key in ["case_stable_hash", "case_row_index_hash", "case_identifier_hash"]:
                value = item.get(key)
                if isinstance(value, str):
                    out.add(value)
    return out, counts


def _case_hash_set(rows: Iterable[Dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for row in rows:
        for key in ["case_stable_hash", "case_row_index_hash", "case_identifier_hash"]:
            value = row.get(key)
            if isinstance(value, str):
                out.add(value)
    return out


def _select_slice(dataset_path: Path, counts: Dict[str, int], *, start_index: int, slice_id: str, exclude_hashes: set[str]) -> tuple[List[Dict[str, str]], Dict[str, Any]]:
    selected: List[Dict[str, str]] = []
    summary: Dict[str, Any] = {"slice_id": slice_id, "selection_strategy": "fixed_count_per_stratum_after_prior_slice_hash_exclusion", "selection_start_row_index": start_index, "category_counts": {}}
    used_hashes = set(exclude_hashes)
    for category, target_count in counts.items():
        path = _category_file(dataset_path, category)
        if not path.exists():
            raise FileNotFoundError(f"bfcl_category_file_missing:{path}")
        rows = _iter_json_rows(path)
        source_hash = _source_file_hash(path)
        picked: List[Dict[str, str]] = []
        category_start_index = CATEGORY_START_ROW_OVERRIDES.get(category, start_index)
        for row_index, raw in rows:
            if row_index < category_start_index:
                continue
            compact = _compact_case(ENTRY_BY_CATEGORY[category], category, source_hash, row_index, raw)
            compact["slice_id"] = slice_id
            compact_hashes = _case_hash_set([compact])
            if compact_hashes.intersection(used_hashes):
                continue
            picked.append(compact)
            used_hashes.update(compact_hashes)
            if len(picked) == target_count:
                break
        if len(picked) != target_count:
            raise RuntimeError(f"insufficient_next_slice_cases:{slice_id}:{category}:{len(picked)}<{target_count}")
        selected.extend(picked)
        summary["category_counts"][category] = {"source_file_hash": source_hash, "total_rows": len(rows), "selected_count": len(picked), "target_count": target_count}
    return selected, summary


def build(dataset_path: Path = DEFAULT_DATASET) -> Dict[str, Any]:
    blockers: List[str] = []
    prior_hashes, prior_counts = _prior_hashes()
    if not dataset_path.exists():
        blockers.append("bfcl_dataset_path_missing")
        balanced: List[Dict[str, str]] = []
        stress: List[Dict[str, str]] = []
        balanced_summary: Dict[str, Any] = {}
        stress_summary: Dict[str, Any] = {}
    else:
        balanced, balanced_summary = _select_slice(dataset_path, BALANCED_COUNTS, start_index=BALANCED_START_ROW_INDEX, slice_id="balanced_verification", exclude_hashes=prior_hashes)
        stress_exclude = set(prior_hashes).union(_case_hash_set(balanced))
        stress, stress_summary = _select_slice(dataset_path, STRESS_COUNTS, start_index=STRESS_START_ROW_INDEX, slice_id="residual_stress", exclude_hashes=stress_exclude)
    discovery_hashes, discovery_count, discovery_by_file = _discovery_hashes()
    balanced_hash = selected_case_ids_hash(balanced) if balanced else "pending"
    stress_hash = selected_case_ids_hash(stress) if stress else "pending"
    all_rows = list(balanced) + list(stress)
    all_hashes = _case_hash_set(all_rows)
    discovery_overlap = sorted(all_hashes.intersection(discovery_hashes))
    old_overlap = sorted(all_hashes.intersection(prior_hashes))
    cross_overlap = sorted(_case_hash_set(balanced).intersection(_case_hash_set(stress)))
    if discovery_overlap:
        blockers.append("archive_source_overlap_detected")
    if old_overlap:
        blockers.append("old_slice_overlap_detected")
    if cross_overlap:
        blockers.append("balanced_stress_overlap_detected")
    balanced_by_category = {cat: sum(1 for item in balanced if item["bfcl_category"] == cat) for cat in BALANCED_COUNTS}
    stress_by_category = {cat: sum(1 for item in stress if item["bfcl_category"] == cat) for cat in STRESS_COUNTS}
    manifest = {
        "artifact_kind": "abhe_v0_next_fresh_slice_manifest",
        "schema_version": "abhe_v0_next_fresh_slice_manifest_v0",
        "bounded_dev_smoke_only": True,
        "fresh_slice_materialized": True,
        "selected_dataset_path": str(dataset_path),
        "primary_slice_id": "balanced_verification",
        "selected_case_ids_hash": balanced_hash,
        "selected_case_count": len(balanced),
        "case_count_by_category": balanced_by_category,
        "selected_compact_case_identifiers": balanced,
        "stress_slice_id": "residual_stress",
        "stress_selected_case_ids_hash": stress_hash,
        "stress_selected_case_count": len(stress),
        "stress_case_count_by_category": stress_by_category,
        "stress_compact_case_identifiers": stress,
        "old_expanded_slice_overlap_count": len(old_overlap),
        "archive_source_overlap_count": len(discovery_overlap),
        "source_160_compact_cases_reused_for_validation": False,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_evidence": False,
        "blockers": blockers,
    }
    proof = {
        "artifact_kind": "abhe_v0_next_source_exclusion_proof",
        "schema_version": "abhe_v0_next_source_exclusion_proof_v0",
        "overlap_check_status": "complete" if not blockers else "blocked",
        "discovery_source_hash_count": discovery_count,
        "candidate_case_hash_count": len(all_rows),
        "balanced_candidate_case_hash_count": len(balanced),
        "stress_candidate_case_hash_count": len(stress),
        "old_slice_source_hash_count": len(prior_hashes),
        "old_slice_source_counts": prior_counts,
        "archive_source_overlap_count": len(discovery_overlap),
        "old_slice_overlap_count": len(old_overlap),
        "balanced_stress_overlap_count": len(cross_overlap),
        "overlap_count": len(discovery_overlap) + len(old_overlap) + len(cross_overlap),
        "overlap_hashes": discovery_overlap + old_overlap + cross_overlap,
        "source_160_compact_cases_reused_for_validation": False,
        "archive_seed_source_excluded": not discovery_overlap,
        "old_expanded_and_smoke_slices_excluded": not old_overlap,
        "hash_rule_description": "sha256 compact case hashes and category row-window hashes; only compact identifiers are persisted.",
        "discovery_source_file_counts": discovery_by_file,
        "raw_material_absent": True,
        "performance_evidence": False,
        "blockers": blockers,
    }
    plan = {
        "artifact_kind": "abhe_v0_next_fresh_slice_plan",
        "schema_version": "abhe_v0_next_fresh_slice_plan_v0",
        "bounded_dev_smoke_only": True,
        "purpose": "fresh_slice_generalization_and_residual_state_bottleneck_diagnosis",
        "dataset_path": str(dataset_path),
        "balanced_slice_case_count": len(balanced),
        "balanced_slice_hash": balanced_hash,
        "stress_slice_case_count": len(stress),
        "stress_slice_hash": stress_hash,
        "candidate_arms": ["baseline", "frozen_v2", "missing_param_gate", "long_context_retrieval", "both"],
        "frozen_mechanisms": ["post_tool_continuation_guard_v0", "no_tool_boundary_v0"],
        "new_child_mechanisms": ["missing_param_epistemic_gate_v0", "long_context_state_retrieval_v0"],
        "no_full_bfcl": True,
        "no_holdout": True,
        "archive_update_authorized": False,
        "performance_evidence": False,
        "source_exclusion_proof_path": str(PROOF),
        "manifest_path": str(MANIFEST),
        "next_required_action": "run_balanced_verification_then_residual_stress_only_if_needed",
        "blockers": blockers,
    }
    for label, data in [("plan", plan), ("manifest", manifest), ("proof", proof)]:
        blockers.extend(scan_value(data, label=f"abhe_v0_next_{label}"))
    for data in [plan, manifest, proof]:
        data["blockers"] = sorted(set(blockers))
    return {"plan": plan, "manifest": manifest, "proof": proof}


def write_all(payload: Dict[str, Any]) -> None:
    for path, key in [(PLAN, "plan"), (MANIFEST, "manifest"), (PROOF, "proof")]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload[key], indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = build(args.dataset_path)
        if args.write:
            write_all(payload)
        report = payload["plan"]
    except Exception as exc:
        report = {"artifact_kind": "abhe_v0_next_fresh_slice_plan", "blockers": [f"load_failed:{exc.__class__.__name__}"], "performance_evidence": False}
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
