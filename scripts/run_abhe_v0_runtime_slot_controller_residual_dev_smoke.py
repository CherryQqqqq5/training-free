#!/usr/bin/env python3
"""Run ABHE-v0 miss-param residual stress bounded dev smoke."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

import scripts.run_abhe_v0_bfcl_dev_smoke as base
from scripts.check_abhe_v0_runtime_slot_distinct_rerun_approval_packet import check as check_distinct_rerun_approval

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
MANIFEST = ROOT / "abhe_v0_runtime_slot_controller_residual_stress_slice_manifest.json"
SPEC = ROOT / "abhe_v0_runtime_slot_controller_candidate_spec.json"
RESULT = ROOT / "abhe_v0_runtime_slot_controller_residual_dev_smoke_result.json"
FAILURE = ROOT / "abhe_v0_runtime_slot_controller_residual_dev_smoke_failure.json"
DISTINCT_RESULT = ROOT / "abhe_v0_runtime_slot_controller_distinct_rerun_result.json"
DISTINCT_FAILURE = ROOT / "abhe_v0_runtime_slot_controller_distinct_rerun_failure.json"
RUN_ROOT = Path("/tmp/abhe_v0_runtime_slot_controller_residual_dev_smoke")
APPROVAL_PACKET = ROOT / "abhe_v0_runtime_slot_controller_distinct_rerun_approval_packet.json"
ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]
STATE_CATEGORIES = {"multi_turn_miss_param", "multi_turn_miss_func", "multi_turn_base", "multi_turn_long_context"}
NO_TOOL_CATEGORIES = {"irrelevance", "live_irrelevance"}


def _is_distinct_manifest(path: Path) -> bool:
    return path.name == "abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json"


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _failure(arm: str, blockers: List[str], distinct: bool = False) -> Dict[str, Any]:
    data = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_residual_dev_smoke_failure",
        "schema_version": "abhe_v0_runtime_slot_controller_residual_dev_smoke_failure_v0",
        "arm": arm,
        "execution_started": False,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_evidence": False,
        "archive_updated": False,
        "blockers": sorted(set(blockers)),
    }
    _write(DISTINCT_FAILURE if distinct else FAILURE, data)
    return data


def _configure(manifest_path: Path = MANIFEST, run_root: Path = RUN_ROOT) -> Dict[str, Any]:
    if not (manifest_path.exists() and SPEC.exists()):
        raise RuntimeError("miss_param_manifest_or_spec_missing")
    manifest = _load(manifest_path)
    selected_hash = str(manifest["selected_case_ids_hash"])
    case_count = int(manifest["selected_case_count"])
    base.DEFAULT_FRESH_MANIFEST = manifest_path
    base.EXPECTED_HASH = selected_hash
    base.EXPECTED_CASE_COUNT = case_count
    base.RUN_ROOT = run_root
    return {"manifest": manifest, "selected_hash": selected_hash, "case_count": case_count}


def _adapter_for_arm(arm: str, selected_hash: str) -> Path:
    if arm == "baseline":
        raise ValueError("baseline_has_no_adapter")
    runtime_v2 = arm == "runtime_slot_controller_v2"
    adapter = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_candidate_adapter",
        "schema_version": "abhe_v0_runtime_slot_controller_candidate_adapter_v0",
        "arm": arm,
        "selected_case_ids_hash": selected_hash,
        "adapter_ready": True,
        "candidate_jsonl_generated": False,
        "candidate_rule_generated": False,
        "candidate_yaml_generated": False,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "performance_evidence": False,
        "runtime_projection": [
            {
                "entry_id": "state_tracking_v0",
                "candidate_type": "state_summary_injection",
                "runtime_guidance_fragment_id": f"state_tracking_{arm}_compact_fragment_v0",
                "activation_categories": sorted(STATE_CATEGORIES),
                "post_tool_continuation_guard_v0": True,
                "runtime_slot_controller_v2": runtime_v2,
                "missing_param_slot_recovery_controller_v1": False,
                "missing_param_epistemic_gate_v0": False,
                "long_context_state_retrieval_v0": False,
                "no_state_mutation": True,
                "search_memory_watch_excluded": True,
            },
            {
                "entry_id": "hallucination_abstain_v0",
                "candidate_type": "evidence_boundary_verifier",
                "runtime_guidance_fragment_id": "no_tool_boundary_v0_frozen_regression_fragment",
                "activation_categories": sorted(NO_TOOL_CATEGORIES),
                "no_tool_boundary_v0": True,
                "false_abstain_guard": True,
                "valid_tool_call_suppression_guard": True,
            },
        ],
    }
    out = ROOT / f"abhe_v0_runtime_slot_controller_candidate_adapter_{arm}.json"
    _write(out, adapter)
    return out


def _write_arm(arm: str, selected_hash: str, case_count: int, ids_by_category: Dict[str, List[str]], entry_by_category: Dict[str, str], status_by_category: Dict[str, Dict[str, Any]], latency: float, distinct: bool = False) -> Dict[str, Any]:
    by_entry: Dict[str, Dict[str, Any]] = {}
    total_passed = 0
    missing_scores: List[str] = []
    for category, ids in ids_by_category.items():
        entry = entry_by_category.get(category, "unknown")
        row = by_entry.setdefault(entry, {"case_count": 0, "passed_count": 0, "category_compact_metrics": {}})
        status = status_by_category.get(category, {})
        count = int(status.get("case_count", len(ids)) or 0)
        passed = int(status.get("passed_count", 0) or 0)
        total_passed += passed
        row["case_count"] += count
        row["passed_count"] += passed
        row["category_compact_metrics"][category] = {
            "case_count": count,
            "passed_count": passed,
            "accuracy_pct": status.get("accuracy_pct"),
            "score_available": status.get("score_available") is True,
            "unique_scorer_unit_count": status.get("unique_scorer_unit_count"),
        }
        if status.get("score_available") is not True:
            missing_scores.append(category)
    artifact = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_residual_dev_smoke_arm_compact",
        "schema_version": "abhe_v0_runtime_slot_controller_residual_dev_smoke_arm_compact_v0",
        "arm": arm,
        "bounded_dev_smoke_only": True,
        "selected_case_ids_hash": selected_hash,
        "case_count": case_count,
        "passed_count": total_passed,
        "accuracy": round(total_passed / case_count, 6) if case_count else None,
        "latency": latency,
        "cost": 0.0,
        "arm_complete": not missing_scores,
        "score_missing_categories": missing_scores,
        "entry_compact_metrics": by_entry,
        "provider_model_protocol_match": True,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_evidence": False,
    }
    prefix = "abhe_v0_runtime_slot_controller_distinct_rerun" if distinct else "abhe_v0_runtime_slot_controller_residual_dev_smoke"
    _write(ROOT / f"{prefix}_{arm}_arm_compact.json", artifact)
    return artifact


def _write_result(selected_hash: str, distinct: bool = False) -> None:
    arms: Dict[str, Dict[str, Any]] = {}
    for arm in ARMS:
        prefix = "abhe_v0_runtime_slot_controller_distinct_rerun" if distinct else "abhe_v0_runtime_slot_controller_residual_dev_smoke"
        path = ROOT / f"{prefix}_{arm}_arm_compact.json"
        if path.exists():
            arms[arm] = _load(path)
    result = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_residual_dev_smoke_result",
        "schema_version": "abhe_v0_runtime_slot_controller_residual_dev_smoke_result_v0",
        "bounded_dev_smoke_only": True,
        "compact_only": True,
        "selected_case_ids_hash": selected_hash,
        "arms_complete": {arm: data.get("arm_complete") is True for arm, data in arms.items()},
        "arm_compact_metrics": {arm: {k: data.get(k) for k in ["case_count", "passed_count", "accuracy", "cost", "latency"]} for arm, data in arms.items()},
        "provider_model_protocol_match": True,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_evidence": False,
        "archive_updated": False,
    }
    _write(DISTINCT_RESULT if distinct else RESULT, result)



def _validate_approval_packet(approval_packet: Path, manifest_path: Path, arm: str) -> List[str]:
    report = check_distinct_rerun_approval(approval_packet)
    blockers = [str(item) for item in report.get("blockers") or []]
    if report.get("approval_packet_passed") is not True:
        blockers.append("distinct_rerun_approval_packet_not_passed")
    try:
        packet = _load(approval_packet)
    except Exception as exc:
        return sorted(set(blockers + ["approval_packet_load_failed:%s" % exc.__class__.__name__]))
    if str(manifest_path) != packet.get("approved_manifest_path"):
        blockers.append("manifest_path_not_approved")
    if arm not in (packet.get("approved_arms") or []):
        blockers.append("arm_not_approved")
    if packet.get("approval_scope") != "scorer_unit_distinct_bounded_residual_dev_smoke_only":
        blockers.append("approval_scope_invalid_for_runner")
    return sorted(set(blockers))

def execute_arm(arm: str, manifest_path: Path = MANIFEST, run_root_override: Path = RUN_ROOT) -> Dict[str, Any]:
    distinct = _is_distinct_manifest(manifest_path)
    if arm not in ARMS:
        return _failure(arm, ["arm_invalid"], distinct)
    try:
        cfg = _configure(manifest_path, run_root_override)
        selected_hash = cfg["selected_hash"]
        case_count = cfg["case_count"]
        ids_by_category, _, entry_by_category = base._selected_raw_ids()
    except Exception as exc:
        return _failure(arm, [f"configure_failed:{exc.__class__.__name__}"], distinct)
    run_root = run_root_override / arm
    if run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    if arm != "baseline":
        adapter = _adapter_for_arm(arm, selected_hash)
        base.DEFAULT_ADAPTER = adapter.resolve()
    status_by_category: Dict[str, Dict[str, Any]] = {}
    total_latency = 0.0
    try:
        for idx, (category, ids) in enumerate(ids_by_category.items()):
            category_root = run_root / category
            activation_entry = None if arm == "baseline" else ("hallucination_abstain_v0" if category in NO_TOOL_CATEGORIES else "state_tracking_v0")
            blockers = base._run_bfcl_group(
                arm=arm,
                run_root=category_root,
                group_ids_by_category={category: ids},
                port=8651 + idx,
                adapter_enabled=arm != "baseline",
                activation_entry=activation_entry,
            )
            if blockers:
                return _failure(arm, blockers, distinct)
            metrics = base._aggregate_metrics(category_root, category_root / "traces", arm, category)
            total_latency += float(metrics.get("latency") or 0.0)
            status_by_category.update(base._category_status_from_score(category_root, {category: ids}))
        compact = _write_arm(arm, selected_hash, case_count, ids_by_category, entry_by_category, status_by_category, total_latency, distinct)
        _write_result(selected_hash, distinct)
        return {"report_scope": "abhe_v0_runtime_slot_controller_residual_dev_smoke_execute", "arm": arm, "execution_started": True, "provider_calls_made": True, "bfcl_generate_called": True, "bfcl_evaluate_called": True, "scorer_called": True, "compact_only": True, "raw_material_absent": True, "performance_evidence": False, "arm_compact": compact, "blockers": []}
    except Exception as exc:
        return _failure(arm, [f"runner_exception:{exc.__class__.__name__}"], distinct)



def dry_run_arm(arm: str, manifest_path: Path = MANIFEST) -> Dict[str, Any]:
    distinct = _is_distinct_manifest(manifest_path)
    if arm not in ARMS:
        return _failure(arm, ["arm_invalid"], distinct)
    try:
        cfg = _configure(manifest_path, RUN_ROOT)
        ids_by_category, _, entry_by_category = base._selected_raw_ids()
    except Exception as exc:
        return _failure(arm, [f"dry_run_configure_failed:{exc.__class__.__name__}"], distinct)
    category_counts = {category: len(ids) for category, ids in ids_by_category.items()}
    manifest = {
        "artifact_kind": "abhe_v0_runtime_slot_controller_distinct_rerun_dry_run_manifest",
        "schema_version": "abhe_v0_runtime_slot_controller_distinct_rerun_dry_run_manifest_v0",
        "arm": arm,
        "dry_run": True,
        "manifest_path": str(manifest_path),
        "selected_case_ids_hash": cfg["selected_hash"],
        "selected_case_count": cfg["case_count"],
        "category_counts": category_counts,
        "entry_by_category": entry_by_category,
        "runner_manifest_compatible": sum(category_counts.values()) == cfg["case_count"],
        "execution_started": False,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "performance_evidence": False,
        "blockers": [] if sum(category_counts.values()) == cfg["case_count"] else ["runner_case_count_mismatch"],
    }
    _write(ROOT / "abhe_v0_runtime_slot_controller_distinct_rerun_dry_run_manifest.json", manifest)
    return manifest

def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--execute-approved", action="store_true")
    parser.add_argument("--approval-packet", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compact-only", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        payload = dry_run_arm(args.arm, args.manifest)
        print(json.dumps(payload, sort_keys=True))
        return 0 if not payload.get("blockers") else 2
    if not args.execute_approved or not args.compact_only:
        payload = _failure(args.arm, ["execute_approved_and_compact_only_required"], _is_distinct_manifest(args.manifest))
        print(json.dumps(payload, sort_keys=True))
        return 2
    if args.approval_packet is None:
        payload = _failure(args.arm, ["approval_packet_argument_required"], _is_distinct_manifest(args.manifest))
        print(json.dumps(payload, sort_keys=True))
        return 2
    approval_blockers = _validate_approval_packet(args.approval_packet, args.manifest, args.arm)
    if approval_blockers:
        payload = _failure(args.arm, approval_blockers, _is_distinct_manifest(args.manifest))
        print(json.dumps(payload, sort_keys=True))
        return 2
    payload = execute_arm(args.arm, args.manifest)
    print(json.dumps(payload, sort_keys=True))
    return 0 if not payload.get("blockers") else 2


if __name__ == "__main__":
    raise SystemExit(main())
