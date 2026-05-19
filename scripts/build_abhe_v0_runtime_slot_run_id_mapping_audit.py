#!/usr/bin/env python3
"""Audit compact selected rows to BFCL raw run-id mapping for runtime slot reruns.

No provider, BFCL generate/evaluate, or scorer is called. The artifact records
only counts and boundary flags, not raw ids, prompts, outputs, gold, or diffs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

import scripts.run_abhe_v0_bfcl_dev_smoke as base
from scripts.check_abhe_no_leakage_boundary import scan_value
from scripts.run_abhe_v0_runtime_slot_controller_residual_dev_smoke import _configure

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_MANIFEST = ROOT / "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json"
DEFAULT_OUTPUT = ROOT / "abhe_v0_runtime_slot_controller_run_id_mapping_audit.json"
NEXT_ACTION = "request_bounded_rerun_after_run_id_mapping_fix"
FALSE_FIELDS = [
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


def _write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _hash_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def build(manifest_path: Path = DEFAULT_MANIFEST, output_path: Path = DEFAULT_OUTPUT, write: bool = False) -> Dict[str, Any]:
    blockers: List[str] = []
    manifest = _load(manifest_path)
    _configure(manifest_path)
    ids_by_category, _, _ = base._selected_raw_ids()
    selected_rows = manifest.get("selected_compact_case_identifiers") if isinstance(manifest.get("selected_compact_case_identifiers"), list) else []
    selected_by_category: Dict[str, int] = {}
    for row in selected_rows:
        if isinstance(row, dict):
            category = str(row.get("bfcl_category"))
            selected_by_category[category] = selected_by_category.get(category, 0) + 1
    category_summaries: Dict[str, Dict[str, Any]] = {}
    for category, selected_count in sorted(selected_by_category.items()):
        raw_ids = ids_by_category.get(category, [])
        raw_id_hashes = [_hash_text(value) for value in raw_ids]
        unique_count = len(set(raw_id_hashes))
        category_summaries[category] = {
            "selected_compact_count": selected_count,
            "mapped_run_id_count": len(raw_ids),
            "unique_run_id_hash_count": unique_count,
            "duplicate_run_id_count": len(raw_ids) - unique_count,
            "mapping_is_one_to_one": len(raw_ids) == selected_count and unique_count == selected_count,
            "raw_ids_persisted": False,
            "raw_id_hashes_persisted": False,
        }
        if len(raw_ids) != selected_count:
            blockers.append(f"run_id_count_mismatch:{category}")
        if unique_count != selected_count:
            blockers.append(f"run_id_hash_not_distinct:{category}:{unique_count}<{selected_count}")
    expected_total = int(manifest.get("selected_case_count") or 0)
    mapped_total = sum(len(ids) for ids in ids_by_category.values())
    unique_total = sum(summary["unique_run_id_hash_count"] for summary in category_summaries.values())
    report: Dict[str, Any] = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_run_id_mapping_audit",
        "schema_version": "abhe_v0_runtime_slot_controller_run_id_mapping_audit_v0",
        "run_scope": "offline_run_id_mapping_audit_only_no_provider_no_bfcl_no_scorer",
        "manifest_path": str(manifest_path),
        "selected_case_ids_hash": manifest.get("selected_case_ids_hash"),
        "selected_case_count": expected_total,
        "mapped_run_id_count": mapped_total,
        "unique_run_id_hash_count": unique_total,
        "run_id_mapping_ready": not blockers,
        "category_summaries": category_summaries,
        "next_required_action": NEXT_ACTION if not blockers else "fix_selected_raw_id_mapping_before_more_bfcl",
        "raw_material_absent": True,
        "raw_ids_persisted": False,
        "raw_id_hashes_persisted": False,
        "prompt_literal_committed": False,
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
    for field in FALSE_FIELDS:
        if report.get(field) is not False:
            report["blockers"].append(f"{field}_not_false")
    leakage = scan_value(report, label="abhe_v0_runtime_slot_controller_run_id_mapping_audit")
    if leakage:
        report["blockers"] = sorted(set(report["blockers"] + leakage))
        report["run_id_mapping_ready"] = False
    if write:
        _write(output_path, report)
    return report


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build(args.manifest, args.output, write=args.write)
    except Exception as exc:
        report = {
            "artifact_kind": "abhe_v0_runtime_slot_controller_run_id_mapping_audit",
            "run_id_mapping_ready": False,
            "blockers": [f"build_failed:{exc.__class__.__name__}"],
            "performance_evidence": False,
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
