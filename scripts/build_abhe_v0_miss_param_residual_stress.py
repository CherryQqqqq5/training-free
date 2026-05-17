#!/usr/bin/env python3
"""Build ABHE-v0 miss-param residual stress artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

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
PLAN = ROOT / "abhe_v0_miss_param_residual_stress_plan.json"
MANIFEST = ROOT / "abhe_v0_miss_param_residual_stress_slice_manifest.json"
PROOF = ROOT / "abhe_v0_miss_param_source_exclusion_proof.json"
SPEC = ROOT / "abhe_v0_missing_param_slot_recovery_candidate_spec.json"
PREVIOUS_MANIFESTS = [
    ROOT / "abhe_v0_bfcl_fresh_dev_slice_manifest.json",
    ROOT / "abhe_v0_expanded_bfcl_fresh_dev_slice_manifest.json",
    ROOT / "abhe_v0_next_fresh_slice_manifest.json",
]
STRESS_COUNTS = {
    "multi_turn_miss_param": 36,
    "multi_turn_miss_func": 8,
    "multi_turn_base": 6,
    "multi_turn_long_context": 6,
    "irrelevance": 6,
    "live_irrelevance": 6,
}
ENTRY_BY_CATEGORY = {
    "multi_turn_miss_param": "missing_param_slot_recovery_controller_v1",
    "multi_turn_miss_func": "post_tool_continuation_guard_v0",
    "multi_turn_base": "post_tool_continuation_guard_v0",
    "multi_turn_long_context": "long_context_regression_guard",
    "irrelevance": "no_tool_boundary_regression_suite",
    "live_irrelevance": "no_tool_boundary_regression_suite",
}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _case_hash_set(rows: Iterable[Dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for row in rows:
        for key in ["case_stable_hash", "case_row_index_hash", "case_identifier_hash"]:
            value = row.get(key)
            if isinstance(value, str):
                out.add(value)
    return out


def _prior_hashes() -> Tuple[set[str], Dict[str, int]]:
    hashes: set[str] = set()
    counts: Dict[str, int] = {}
    for path in PREVIOUS_MANIFESTS:
        if not path.exists():
            counts[str(path)] = 0
            continue
        data = _load(path)
        rows: List[Dict[str, Any]] = []
        for key in ["selected_compact_case_identifiers", "stress_compact_case_identifiers"]:
            value = data.get(key)
            if isinstance(value, list):
                rows.extend(item for item in value if isinstance(item, dict))
        counts[str(path)] = len(rows)
        hashes.update(_case_hash_set(rows))
    return hashes, counts


def _select(dataset_path: Path, prior_hashes: set[str]) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    selected: List[Dict[str, str]] = []
    used = set(prior_hashes)
    summary: Dict[str, Any] = {}
    for category, target_count in STRESS_COUNTS.items():
        source_path = _category_file(dataset_path, category)
        if not source_path.exists():
            raise FileNotFoundError(f"bfcl_category_file_missing:{source_path}")
        rows = _iter_json_rows(source_path)
        source_hash = _source_file_hash(source_path)
        picked: List[Dict[str, str]] = []
        for row_index, raw in rows:
            compact = _compact_case(ENTRY_BY_CATEGORY[category], category, source_hash, row_index, raw)
            compact["slice_id"] = "miss_param_residual_stress_v0"
            compact_hashes = _case_hash_set([compact])
            if compact_hashes.intersection(used):
                continue
            picked.append(compact)
            used.update(compact_hashes)
            if len(picked) == target_count:
                break
        if len(picked) != target_count:
            raise RuntimeError(f"insufficient_residual_cases:{category}:{len(picked)}<{target_count}")
        selected.extend(picked)
        summary[category] = {"target_count": target_count, "selected_count": len(picked), "total_rows": len(rows), "source_file_hash": source_hash}
    return selected, summary


def _spec(selected_hash: str) -> Dict[str, Any]:
    return {
        "artifact_kind": "abhe_v0_missing_param_slot_recovery_candidate_spec",
        "schema_version": "abhe_v0_missing_param_slot_recovery_candidate_spec_v0",
        "mechanism_id": "missing_param_slot_recovery_controller_v1",
        "supersedes": "missing_param_epistemic_gate_v0",
        "candidate_type": "runtime_slot_recovery_controller_guidance",
        "selected_case_ids_hash": selected_hash,
        "training_free": True,
        "candidate_jsonl_generated": False,
        "candidate_rule_generated": False,
        "candidate_yaml_generated": False,
        "target_substratum": "multi_turn_miss_param",
        "activation_boundary": {"tool_call_state_cases": True, "required_slot_missing_or_uncertain": True, "bfcl_category_specific_trigger_rule": False, "case_identifier_allowlist": False},
        "controller_contract": [
            "build_required_slot_ledger_for_intended_tool_action",
            "bind_slot_from_current_user_turn_when_present",
            "bind_slot_from_prior_confirmed_selection_when_present",
            "bind_slot_from_prior_tool_observation_when_present",
            "call_prerequisite_lookup_tool_when_slot_is_tool_recoverable",
            "ask_or_insufficient_only_when_slot_absent_not_inferable_not_tool_recoverable",
            "do_not_block_valid_tool_call_when_required_slots_are_available",
            "do_not_hallucinate_required_argument_values",
        ],
        "negative_controls": [
            "slot_already_exists_in_prior_turn_must_not_ask_again",
            "slot_exists_in_prior_tool_observation_must_bind_not_ask",
            "slot_tool_recoverable_must_explore_not_immediate_ask",
            "slot_unrecoverable_must_ask_or_insufficient_not_hallucinate",
            "valid_tool_call_has_all_required_args_must_not_be_blocked",
        ],
        "primary_metrics": ["multi_turn_miss_param_delta_vs_frozen_v2", "target_bucket_reduction"],
        "safety_metrics": ["false_ask_count", "hallucinated_param_count", "valid_tool_call_suppression_count", "non_target_regression_count"],
        "performance_evidence": False,
        "archive_update_authorized": False,
    }


def build(dataset_path: Path = DEFAULT_DATASET) -> Dict[str, Any]:
    blockers: List[str] = []
    prior, prior_counts = _prior_hashes()
    discovery_hashes, discovery_count, discovery_by_file = _discovery_hashes()
    exclusion_hashes = set(prior).union(discovery_hashes)
    if not dataset_path.exists():
        blockers.append("bfcl_dataset_path_missing")
        selected: List[Dict[str, str]] = []
        category_summary: Dict[str, Any] = {}
    else:
        selected, category_summary = _select(dataset_path, exclusion_hashes)
    selected_hash = selected_case_ids_hash(selected) if selected else "pending"
    candidate_hashes = _case_hash_set(selected)
    discovery_overlap = sorted(candidate_hashes.intersection(discovery_hashes))
    prior_overlap = sorted(candidate_hashes.intersection(prior))
    if discovery_overlap:
        blockers.append("archive_source_overlap_detected")
    if prior_overlap:
        blockers.append("prior_slice_overlap_detected")
    case_count_by_category = {cat: sum(1 for row in selected if row.get("bfcl_category") == cat) for cat in STRESS_COUNTS}
    manifest = {
        "artifact_kind": "abhe_v0_miss_param_residual_stress_slice_manifest",
        "schema_version": "abhe_v0_miss_param_residual_stress_slice_manifest_v0",
        "bounded_dev_smoke_only": True,
        "slice_id": "miss_param_residual_stress_v0",
        "selected_dataset_path": str(dataset_path),
        "selected_case_ids_hash": selected_hash,
        "selected_case_count": len(selected),
        "case_count_by_category": case_count_by_category,
        "selected_compact_case_identifiers": selected,
        "source_160_compact_cases_reused_for_validation": False,
        "archive_source_overlap_count": len(discovery_overlap),
        "prior_slice_overlap_count": len(prior_overlap),
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
        "artifact_kind": "abhe_v0_miss_param_source_exclusion_proof",
        "schema_version": "abhe_v0_miss_param_source_exclusion_proof_v0",
        "overlap_check_status": "complete" if not blockers else "blocked",
        "candidate_case_hash_count": len(selected),
        "discovery_source_hash_count": discovery_count,
        "prior_slice_source_hash_count": len(prior),
        "prior_slice_source_counts": prior_counts,
        "archive_source_overlap_count": len(discovery_overlap),
        "prior_slice_overlap_count": len(prior_overlap),
        "overlap_count": len(discovery_overlap) + len(prior_overlap),
        "overlap_hashes": discovery_overlap + prior_overlap,
        "source_160_compact_cases_reused_for_validation": False,
        "archive_seed_source_excluded": not discovery_overlap,
        "old_dev_slices_excluded": not prior_overlap,
        "hash_rule_description": "sha256 compact hashes only; values omitted.",
        "discovery_source_file_counts": discovery_by_file,
        "raw_material_absent": True,
        "performance_evidence": False,
        "blockers": blockers,
    }
    plan = {
        "artifact_kind": "abhe_v0_miss_param_residual_stress_plan",
        "schema_version": "abhe_v0_miss_param_residual_stress_plan_v0",
        "purpose": "targeted_multi_turn_miss_param_residual_mechanism_validation_not_full_bfcl",
        "bounded_dev_smoke_only": True,
        "dataset_path": str(dataset_path),
        "selected_case_ids_hash": selected_hash,
        "selected_case_count": len(selected),
        "case_count_by_category": case_count_by_category,
        "category_selection_summary": category_summary,
        "arms": ["baseline", "frozen_v2", "slot_recovery_v1"],
        "frozen_mechanisms": ["post_tool_continuation_guard_v0", "no_tool_boundary_v0"],
        "new_mechanism": "missing_param_slot_recovery_controller_v1",
        "demoted_mechanisms": ["missing_param_epistemic_gate_v0"],
        "narrowed_mechanisms": ["long_context_state_retrieval_v0"],
        "no_full_bfcl": True,
        "no_holdout": True,
        "archive_update_authorized": False,
        "performance_evidence": False,
        "manifest_path": str(MANIFEST),
        "source_exclusion_proof_path": str(PROOF),
        "candidate_spec_path": str(SPEC),
        "next_required_action": "run_targeted_residual_dev_smoke_and_sanitized_taxonomy",
        "blockers": blockers,
    }
    spec = _spec(selected_hash)
    all_blockers: List[str] = list(blockers)
    for label, data in [("plan", plan), ("manifest", manifest), ("proof", proof), ("spec", spec)]:
        all_blockers.extend(scan_value(data, label=f"abhe_v0_miss_param_{label}"))
    for data in [plan, manifest, proof, spec]:
        data["blockers"] = sorted(set(all_blockers))
    return {"plan": plan, "manifest": manifest, "proof": proof, "spec": spec}


def write_all(payload: Dict[str, Any]) -> None:
    for path, key in [(PLAN, "plan"), (MANIFEST, "manifest"), (PROOF, "proof"), (SPEC, "spec")]:
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
        report = {"artifact_kind": "abhe_v0_miss_param_residual_stress_plan", "blockers": [f"load_failed:{exc.__class__.__name__}"], "performance_evidence": False}
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
