#!/usr/bin/env python3
"""Build compact selected-id alignment sidecar for ABHE runtime-slot reruns.

This is an offline sidecar contract over manifest identifiers and existing
score/result record ids. It records only hashes, counts, and enum-like flags.
It does not call provider, BFCL generate/evaluate, or scorer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_MANIFEST = ROOT / "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json"
DEFAULT_OUTPUT = ROOT / "abhe_v0_runtime_slot_controller_alignment_sidecar.json"
DEFAULT_RUN_ROOT = Path("/tmp/abhe_v0_runtime_slot_controller_residual_dev_smoke")
MODEL_ALIAS = "gpt-4o-mini-2024-07-18-FC"
ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]
NEXT_ACTION = "request_bounded_rerun_with_compact_alignment_sidecar_enabled"
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


def _score_path(run_root: Path, arm: str, category: str) -> Path:
    family = _family(category)
    return run_root / arm / category / "bfcl" / "score" / MODEL_ALIAS / family / f"BFCL_v4_{category}_score.json"


def _result_path(run_root: Path, arm: str, category: str) -> Path:
    family = _family(category)
    return run_root / arm / category / "bfcl" / "result" / MODEL_ALIAS / family / f"BFCL_v4_{category}_result.json"


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


def _score_record_hashes(path: Path) -> set[str]:
    hashes: set[str] = set()
    for index, obj in enumerate(_iter_jsonl(path)):
        if index == 0 and {"accuracy", "correct_count", "total_count"}.issubset(obj.keys()):
            continue
        hashes.add(_hash_text(str(obj.get("id") or f"missing:{index}")))
    return hashes


def _result_record_hashes(path: Path) -> tuple[set[str], Dict[str, int]]:
    if not path.exists():
        return set(), {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return set(), {}
    records = data if isinstance(data, list) else [data]
    hashes: set[str] = set()
    turn_counts: Dict[str, int] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        record_hash = _hash_text(str(record.get("id") or f"missing:{index}"))
        hashes.add(record_hash)
        result = record.get("result")
        turn_counts[record_hash] = len(result) if isinstance(result, list) else 0
    return hashes, turn_counts


def _manifest_rows(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = manifest.get("selected_compact_case_identifiers")
    if not isinstance(rows, list):
        raise ValueError("manifest selected_compact_case_identifiers missing")
    return [row for row in rows if isinstance(row, dict)]


def build(
    manifest_path: Path = DEFAULT_MANIFEST,
    run_root: Path = DEFAULT_RUN_ROOT,
    output_path: Path = DEFAULT_OUTPUT,
    write: bool = False,
) -> Dict[str, Any]:
    manifest = _load(manifest_path)
    manifest_rows = _manifest_rows(manifest)
    selected_count = len(manifest_rows)
    rows: List[Dict[str, Any]] = []
    arm_summaries: Dict[str, Dict[str, Any]] = {}
    categories = sorted({str(row.get("bfcl_category")) for row in manifest_rows})
    for arm in ARMS:
        score_hashes_by_category = {category: _score_record_hashes(_score_path(run_root, arm, category)) for category in categories}
        result_data_by_category = {category: _result_record_hashes(_result_path(run_root, arm, category)) for category in categories}
        seen_score = 0
        seen_result = 0
        for selected_index, item in enumerate(manifest_rows):
            category = str(item.get("bfcl_category"))
            identifier_hash = str(item.get("case_identifier_hash") or item.get("case_stable_hash"))
            scorer_unit_hash = str(item.get("scorer_unit_hash") or identifier_hash)
            result_hashes, turn_counts = result_data_by_category[category]
            score_seen = identifier_hash in score_hashes_by_category[category]
            result_seen = identifier_hash in result_hashes
            seen_score += int(score_seen)
            seen_result += int(result_seen)
            rows.append({
                "arm": arm,
                "selected_index": selected_index,
                "selected_case_identifier_hash": identifier_hash,
                "case_stable_hash": item.get("case_stable_hash"),
                "scorer_unit_hash": scorer_unit_hash,
                "bfcl_category": category,
                "entry_id": item.get("entry_id"),
                "source_file_hash": item.get("source_file_hash"),
                "score_record_seen_for_selected_id": score_seen,
                "result_record_seen_for_selected_id": result_seen,
                "result_turn_count": turn_counts.get(identifier_hash),
                "per_selected_valid_label_available": False,
                "per_selected_valid_label": None,
                "per_turn_valid_labels_available": False,
                "per_turn_valid_labels": [],
                "explicit_aggregation_map_available": False,
                "raw_material_absent": True,
            })
        arm_summaries[arm] = {
            "selected_count": selected_count,
            "score_record_seen_count": seen_score,
            "result_record_seen_count": seen_result,
            "per_selected_valid_label_available": False,
            "per_turn_valid_labels_available": False,
        }

    summary = {
        "selected_case_ids_hash": manifest.get("selected_case_ids_hash"),
        "selected_count": selected_count,
        "row_count": len(rows),
        "arm_count": len(ARMS),
        "alignment_sidecar_ready": True,
        "per_selected_valid_labels_available": False,
        "per_turn_valid_labels_available": False,
        "explicit_aggregation_map_available": False,
        "more_bfcl_without_sidecar_recommended": False,
        "next_rerun_must_emit_this_sidecar": True,
    }
    report: Dict[str, Any] = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_alignment_sidecar",
        "schema_version": "abhe_v0_runtime_slot_controller_alignment_sidecar_v0",
        "run_scope": "offline_compact_alignment_sidecar_contract_only_no_provider_no_bfcl_no_scorer",
        "manifest_path": str(manifest_path),
        "run_root_checked": str(run_root),
        "bounded_dev_smoke_only": True,
        "compact_only": True,
        "summary": summary,
        "arm_summaries": arm_summaries,
        "rows": rows,
        "required_future_output_contract": {
            "selected_index": True,
            "selected_case_identifier_hash": True,
            "scorer_unit_hash": True,
            "arm": True,
            "bfcl_category": True,
            "score_record_seen_for_selected_id": True,
            "result_record_seen_for_selected_id": True,
            "per_selected_valid_label_or_explicit_aggregation_map": True,
            "per_turn_valid_labels_if_claiming_true_per_turn_scoring": True,
            "forbidden_material_absent_requirement": True,
        },
        "next_required_action": NEXT_ACTION,
        "raw_material_absent": True,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "prompt_literal_committed": False,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "model_output_text_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "performance_evidence": False,
        "blockers": [],
    }
    for field in FALSE_FIELDS:
        if report.get(field) is not False:
            report["blockers"].append(f"{field}_not_false")
    leakage = scan_value(report, label="abhe_v0_runtime_slot_controller_alignment_sidecar")
    if leakage:
        report["blockers"] = sorted(set(report["blockers"] + leakage))
    if write:
        _write(output_path, report)
    return report


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build(args.manifest, args.run_root, args.output, write=args.write)
    except Exception as exc:
        report = {
            "artifact_kind": "abhe_v0_runtime_slot_controller_alignment_sidecar",
            "blockers": [f"build_failed:{exc.__class__.__name__}"],
            "performance_evidence": False,
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
