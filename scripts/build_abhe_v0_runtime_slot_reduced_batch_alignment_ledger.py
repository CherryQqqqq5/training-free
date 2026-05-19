#!/usr/bin/env python3
"""Build a compact reduced-batch dataset alignment ledger for runtime-slot retry.

This audit reads the installed BFCL dataset and the reduced-batch compact
manifest, then persists only compact row hashes and dataset-match counts. Raw
BFCL ids and raw-id hashes are used only in memory to prove uniqueness and are
not written to the artifact.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from scripts.build_abhe_v0_bfcl_fresh_dev_slice import _category_file, _compact_case, _iter_json_rows, _source_file_hash, selected_case_ids_hash
from scripts.build_abhe_v0_runtime_slot_controller_residual_stress import DEFAULT_DATASET
from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_MANIFEST = ROOT / "abhe_v0_runtime_slot_controller_reduced_batch_slice_manifest.json"
OUTPUT = ROOT / "abhe_v0_runtime_slot_controller_reduced_batch_alignment_ledger.json"
PARENT_HASH = "sha256:9b26ba3d24c54562f6a5058877a24f15d2e4ef71ee9ea781bcae168307f7d14c"
REDUCED_HASH = "sha256:aa341bfc1d78a406f9f3a25967a03d88849dc42fc64e49625eae1993f33ddece"
TARGET_CATEGORY = "multi_turn_miss_param"
NEXT_ACTION = "review_reduced_batch_alignment_ledger_then_request_retry_approval_if_provider_stable"


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _dataset_rows_by_category(dataset_path: Path, category: str) -> List[Tuple[int, Any, Dict[str, str]]]:
    path = _category_file(dataset_path, category)
    source_hash = _source_file_hash(path)
    rows = []
    for row_index, raw in _iter_json_rows(path):
        rows.append((row_index, raw, _compact_case("state_tracking_v0", category, source_hash, row_index, raw)))
    return rows


def _compact_match(candidate: Dict[str, Any], selected: Dict[str, Any]) -> bool:
    return (
        candidate.get("source_file_hash") == selected.get("source_file_hash")
        and candidate.get("case_stable_hash") == selected.get("case_stable_hash")
        and candidate.get("case_row_index_hash") == selected.get("case_row_index_hash")
        and candidate.get("bfcl_category") == selected.get("bfcl_category")
    )


def _raw_id(raw: Any) -> str | None:
    if not isinstance(raw, dict):
        return None
    value = raw.get("id")
    return value if isinstance(value, str) and value else None


def build(dataset_path: Path = DEFAULT_DATASET, manifest_path: Path = DEFAULT_MANIFEST) -> Dict[str, Any]:
    blockers: List[str] = []
    manifest = _load(manifest_path)
    selected_rows = manifest.get("selected_compact_case_identifiers") if isinstance(manifest.get("selected_compact_case_identifiers"), list) else []
    if manifest.get("selected_case_ids_hash") != REDUCED_HASH:
        blockers.append("reduced_manifest_hash_mismatch")
    if manifest.get("parent_selected_case_ids_hash") != PARENT_HASH:
        blockers.append("parent_hash_mismatch")
    if manifest.get("selected_case_count") != 6:
        blockers.append("selected_case_count_not_six")
    if not dataset_path.exists():
        blockers.append("bfcl_dataset_path_missing")
        dataset_rows: List[Tuple[int, Any, Dict[str, str]]] = []
    else:
        dataset_rows = _dataset_rows_by_category(dataset_path, TARGET_CATEGORY)
    ledger_rows: List[Dict[str, Any]] = []
    raw_ids_for_uniqueness: List[str] = []
    for index, selected in enumerate(selected_rows):
        if not isinstance(selected, dict):
            blockers.append(f"selected_row_not_object:{index}")
            continue
        if selected.get("bfcl_category") != TARGET_CATEGORY:
            blockers.append(f"selected_row_target_category_invalid:{index}")
        matches = [(row_index, raw, compact) for row_index, raw, compact in dataset_rows if _compact_match(compact, selected)]
        raw_id_values = [raw_id for _, raw, _ in matches for raw_id in [_raw_id(raw)] if raw_id]
        raw_ids_for_uniqueness.extend(raw_id_values)
        if len(matches) != 1:
            blockers.append(f"dataset_match_count_not_one:{index}:{len(matches)}")
        ledger_rows.append({
            "selected_index": index,
            "entry_id": selected.get("entry_id"),
            "bfcl_category": selected.get("bfcl_category"),
            "source_file_hash": selected.get("source_file_hash"),
            "case_stable_hash": selected.get("case_stable_hash"),
            "case_row_index_hash": selected.get("case_row_index_hash"),
            "dataset_match_count": len(matches),
            "scorer_unit_distinct_proxy": len(raw_id_values) == 1,
            "per_selected_valid_label_available": False,
            "per_turn_valid_labels_available": False,
            "raw_material_absent": True,
            "raw_ids_persisted": False,
            "raw_id_hashes_persisted": False,
        })
    recomputed_hash = selected_case_ids_hash(selected_rows) if selected_rows else "pending"
    if recomputed_hash != REDUCED_HASH:
        blockers.append("reduced_selected_case_ids_hash_recompute_mismatch")
    unique_raw_id_count = len(set(raw_ids_for_uniqueness))
    duplicate_raw_id_count = len(raw_ids_for_uniqueness) - unique_raw_id_count
    if len(raw_ids_for_uniqueness) != len(selected_rows):
        blockers.append("mapped_run_id_count_mismatch")
    if unique_raw_id_count != len(selected_rows):
        blockers.append("unique_run_id_count_mismatch")
    if duplicate_raw_id_count != 0:
        blockers.append("duplicate_run_id_count_nonzero")
    report: Dict[str, Any] = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_reduced_batch_alignment_ledger",
        "schema_version": "abhe_v0_runtime_slot_controller_reduced_batch_alignment_ledger_v0",
        "run_scope": "offline_dataset_side_scorer_unit_alignment_only_no_provider_no_bfcl_no_scorer",
        "approval_status": "pending",
        "authorized": False,
        "approved_packet_present": False,
        "alignment_ledger_ready": not blockers,
        "source_manifest_path": str(manifest_path),
        "selected_dataset_path": str(dataset_path),
        "parent_selected_case_ids_hash": manifest.get("parent_selected_case_ids_hash"),
        "selected_case_ids_hash": manifest.get("selected_case_ids_hash"),
        "recomputed_selected_case_ids_hash": recomputed_hash,
        "target_category": TARGET_CATEGORY,
        "selected_case_count": len(selected_rows),
        "mapped_run_id_count": len(raw_ids_for_uniqueness),
        "unique_run_id_count": unique_raw_id_count,
        "duplicate_run_id_count": duplicate_raw_id_count,
        "run_id_group_size_histogram": {"1": unique_raw_id_count} if duplicate_raw_id_count == 0 else {},
        "rows": ledger_rows,
        "per_selected_valid_labels_available": False,
        "per_turn_valid_labels_available": False,
        "true_per_selected_id_scoring_available_from_dataset_only": False,
        "true_per_turn_scoring_available_from_dataset_only": False,
        "scorer_output_contract_still_required": True,
        "next_required_action": NEXT_ACTION if not blockers else "fix_reduced_batch_alignment_ledger_before_any_retry_approval",
        "raw_material_absent": True,
        "raw_ids_persisted": False,
        "raw_id_hashes_persisted": False,
        "raw_run_ids_persisted": False,
        "raw_run_id_hashes_persisted": False,
        "prompt_literal_committed": False,
        "tool_schema_body_committed": False,
        "model_output_text_committed": False,
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
    leakage = scan_value(report, label="abhe_v0_runtime_slot_controller_reduced_batch_alignment_ledger")
    if leakage:
        report["blockers"] = sorted(set(report["blockers"] + leakage))
        report["alignment_ledger_ready"] = False
    return report


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build(args.dataset_path, args.manifest)
        if args.write:
            _write(OUTPUT, report)
    except Exception as exc:
        report = {
            "artifact_kind": "abhe_v0_runtime_slot_controller_reduced_batch_alignment_ledger",
            "alignment_ledger_ready": False,
            "blockers": [f"build_failed:{exc.__class__.__name__}"],
            "performance_evidence": False,
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
