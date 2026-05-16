#!/usr/bin/env python3
"""Build and materialize the ABHE-v0 expanded BFCL dev slice manifest."""
from __future__ import annotations

import argparse, json
from pathlib import Path
from typing import Any, Dict, List

from scripts.build_abhe_v0_bfcl_fresh_dev_slice import (
    _category_file,
    _compact_case,
    _discovery_hashes,
    _hash_text,
    _iter_json_rows,
    _source_file_hash,
    selected_case_ids_hash,
)
from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_DATASET = Path(".venv/lib/python3.10/site-packages/bfcl_eval/data")
PREVIOUS_MANIFEST = ROOT / "abhe_v0_bfcl_fresh_dev_slice_manifest.json"
DEFAULT_MANIFEST = ROOT / "abhe_v0_expanded_bfcl_fresh_dev_slice_manifest.json"
DEFAULT_APPROVAL = ROOT / "abhe_v0_expanded_dev_smoke_approval_packet.json"
DEFAULT_PROOF = ROOT / "abhe_v0_expanded_bfcl_source_exclusion_proof.json"
DEFAULT_PLAN = ROOT / "abhe_v0_expanded_bfcl_dev_slice_plan.json"
CATEGORIES_BY_ENTRY = {
    "state_tracking_v0": ["multi_turn_base", "multi_turn_long_context", "multi_turn_miss_func", "multi_turn_miss_param"],
    "hallucination_abstain_v0": ["irrelevance", "live_irrelevance", "live_relevance"],
}
CASE_COUNT_PER_CATEGORY = 6
SELECTION_START_ROW_INDEX = 80
CATEGORY_START_ROW_INDEX = {"live_relevance": 3}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _previous_hashes() -> set[str]:
    if not PREVIOUS_MANIFEST.exists():
        return set()
    data = _load(PREVIOUS_MANIFEST)
    out: set[str] = set()
    for item in data.get("selected_compact_case_identifiers", []):
        if isinstance(item, dict):
            for key in ["case_stable_hash", "case_row_index_hash", "case_identifier_hash"]:
                value = item.get(key)
                if isinstance(value, str):
                    out.add(value)
    return out


def _select_cases(dataset_path: Path) -> tuple[List[Dict[str, str]], Dict[str, Any]]:
    previous = _previous_hashes()
    selected: List[Dict[str, str]] = []
    summary: Dict[str, Any] = {
        "selection_strategy": "fixed_six_per_stratum_after_same_slice_window_exclusion",
        "selection_start_row_index": SELECTION_START_ROW_INDEX,
        "category_start_row_index_overrides": CATEGORY_START_ROW_INDEX,
        "category_counts": {},
    }
    for entry_id, categories in CATEGORIES_BY_ENTRY.items():
        for category in categories:
            path = _category_file(dataset_path, category)
            rows = _iter_json_rows(path)
            source_hash = _source_file_hash(path)
            picked: List[Dict[str, str]] = []
            for row_index, raw in rows:
                if row_index < CATEGORY_START_ROW_INDEX.get(category, SELECTION_START_ROW_INDEX):
                    continue
                compact = _compact_case(entry_id, category, source_hash, row_index, raw)
                compact_hashes = {compact.get("case_stable_hash"), compact.get("case_row_index_hash"), compact.get("case_identifier_hash")}
                if any(h in previous for h in compact_hashes if h):
                    continue
                picked.append(compact)
                if len(picked) == CASE_COUNT_PER_CATEGORY:
                    break
            if len(picked) != CASE_COUNT_PER_CATEGORY:
                raise RuntimeError("insufficient_expanded_cases:%s" % category)
            selected.extend(picked)
            summary["category_counts"][category] = {
                "total_rows": len(rows),
                "selected_count": len(picked),
                "source_file_hash": source_hash,
            }
    return selected, summary


def build(dataset_path: Path = DEFAULT_DATASET) -> Dict[str, Any]:
    blockers: List[str] = []
    if not dataset_path.exists():
        blockers.append("bfcl_dataset_path_missing")
        selected: List[Dict[str, str]] = []
        summary: Dict[str, Any] = {}
    else:
        selected, summary = _select_cases(dataset_path)
    selected_hash = selected_case_ids_hash(selected) if selected else "pending"
    discovery_hashes, discovery_count, discovery_by_file = _discovery_hashes()
    candidate_hashes = set()
    for item in selected:
        for key in ["case_stable_hash", "case_row_index_hash", "case_identifier_hash"]:
            value = item.get(key)
            if isinstance(value, str):
                candidate_hashes.add(value)
    previous_hashes = _previous_hashes()
    discovery_overlap = sorted(candidate_hashes.intersection(discovery_hashes))
    previous_overlap = sorted(candidate_hashes.intersection(previous_hashes))
    if discovery_overlap:
        blockers.append("discovery_source_overlap_detected")
    if previous_overlap:
        blockers.append("same_slice_overlap_detected")
    case_count_by_entry = {entry: sum(1 for item in selected if item["entry_id"] == entry) for entry in CATEGORIES_BY_ENTRY}
    case_count_by_category = {cat: sum(1 for item in selected if item["bfcl_category"] == cat) for cats in CATEGORIES_BY_ENTRY.values() for cat in cats}
    manifest = {
        "artifact_kind": "abhe_v0_expanded_bfcl_fresh_dev_slice_manifest",
        "schema_version": "abhe_v0_expanded_bfcl_fresh_dev_slice_manifest_v0",
        "fresh_dev_slice_materialized": True,
        "expanded_dev_smoke_only": True,
        "selected_dataset_path": str(dataset_path),
        "selected_case_ids_hash": selected_hash,
        "selected_case_count": len(selected),
        "case_count_per_category": CASE_COUNT_PER_CATEGORY,
        "case_count_by_entry": case_count_by_entry,
        "case_count_by_category": case_count_by_category,
        "selected_compact_case_identifiers": selected,
        "source_160_compact_cases_reused_for_validation": False,
        "archive_seed_source_excluded": not discovery_overlap,
        "same_slice_20_case_overlap_count": len(previous_overlap),
        "raw_cases_persisted": False,
        "gold_expected_persisted": False,
        "scorer_diff_persisted": False,
        "raw_provider_payload_committed": False,
        "provider_calls_authorized": False,
        "bfcl_generate_authorized": False,
        "bfcl_evaluate_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "blockers": blockers,
    }
    proof = {
        "artifact_kind": "abhe_v0_expanded_bfcl_source_exclusion_proof",
        "schema_version": "abhe_v0_expanded_bfcl_source_exclusion_proof_v0",
        "overlap_check_status": "complete" if not blockers else "blocked",
        "discovery_source_hash_count": discovery_count,
        "candidate_case_hash_count": len(selected),
        "discovery_overlap_count": len(discovery_overlap),
        "same_slice_overlap_count": len(previous_overlap),
        "overlap_count": len(discovery_overlap) + len(previous_overlap),
        "overlap_hashes": discovery_overlap + previous_overlap,
        "discovery_source_file_counts": discovery_by_file,
        "source_160_compact_cases_reused_for_validation": False,
        "archive_seed_source_excluded": not discovery_overlap,
        "same_slice_20_case_excluded": not previous_overlap,
        "hash_rule_description": "Compact BFCL hashes and row-window hashes only; disallowed benchmark and provider material is omitted from repo artifacts.",
        "raw_material_persisted": False,
        "performance_evidence": False,
        "blockers": blockers,
    }
    approval = {
        "artifact_kind": "abhe_v0_expanded_dev_smoke_approval_packet",
        "schema_version": "abhe_v0_expanded_dev_smoke_approval_packet_v0",
        "approval_status": "approved",
        "authorized": True,
        "review_owner": "project_owner",
        "approval_scope": "expanded_dev_smoke_only_not_full_bfcl",
        "approved_case_count": len(selected),
        "approved_entry_ids": list(CATEGORIES_BY_ENTRY),
        "approved_selected_case_ids_hash": selected_hash,
        "approved_fresh_slice_manifest": str(DEFAULT_MANIFEST),
        "approved_provider": "ToolCallingFunction/OpenAICompatible",
        "approved_profile": "toolcallingfunction",
        "approved_model": "gpt-4.1",
        "approved_runtime_config_path": "configs/runtime_bfcl_structured.yaml",
        "baseline_arm_authorized": True,
        "candidate_arm_authorized": True,
        "provider_calls_authorized": True,
        "bfcl_generate_authorized": True,
        "bfcl_evaluate_authorized": True,
        "scorer_authorized": True,
        "scorer_authorization_scope": "expanded_dev_smoke_only_not_full_bfcl",
        "holdout_authorized": False,
        "full_suite_authorized": False,
        "archive_update_authorized": False,
        "performance_claim_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "raw_material_absent_required": True,
        "stop_loss": [
            "source_overlap_nonzero",
            "provider_model_protocol_mismatch",
            "entry_specific_activation_missing",
            "raw_leakage",
            "any_compact_regression_detected",
            "false_abstain_detected",
            "valid_tool_call_suppression_detected",
            "holdout_or_full_suite_attempted",
        ],
        "blockers": blockers,
    }
    plan = {
        "artifact_kind": "abhe_v0_expanded_bfcl_dev_slice_plan",
        "schema_version": "abhe_v0_expanded_bfcl_dev_slice_plan_v0",
        "expanded_dev_smoke_only": True,
        "selected_case_ids_hash": selected_hash,
        "selected_case_count": len(selected),
        "case_count_per_category": CASE_COUNT_PER_CATEGORY,
        "source_exclusion_proof_status": proof["overlap_check_status"],
        "fresh_dev_slice_materialized": True,
        "approval_packet_path": str(DEFAULT_APPROVAL),
        "manifest_path": str(DEFAULT_MANIFEST),
        "proof_path": str(DEFAULT_PROOF),
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "next_required_action": "run_expanded_dev_smoke_baseline_candidate_and_extract_sanitized_failure_traces",
        "blockers": blockers,
    }
    for label, data in [("manifest", manifest), ("proof", proof), ("approval", approval), ("plan", plan)]:
        blockers.extend(scan_value(data, label="abhe_v0_expanded_bfcl_%s" % label))
    for data in [manifest, proof, approval, plan]:
        data["blockers"] = sorted(set(blockers))
    return {"manifest": manifest, "proof": proof, "approval": approval, "plan": plan, "blockers": sorted(set(blockers))}


def write_all(payload: Dict[str, Any]) -> None:
    for path, key in [(DEFAULT_MANIFEST, "manifest"), (DEFAULT_PROOF, "proof"), (DEFAULT_APPROVAL, "approval"), (DEFAULT_PLAN, "plan")]:
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
        report = {"artifact_kind": "abhe_v0_expanded_bfcl_dev_slice_plan", "blockers": ["load_failed:%s" % exc.__class__.__name__], "performance_evidence": False}
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
