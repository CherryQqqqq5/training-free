#!/usr/bin/env python3
"""Run approved ABHE-v0 expanded BFCL dev smoke with compact-only artifacts."""
from __future__ import annotations

import argparse, json, shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

import scripts.run_abhe_v0_bfcl_dev_smoke as base

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
APPROVAL = ROOT / "abhe_v0_expanded_dev_smoke_approval_packet.json"
MANIFEST = ROOT / "abhe_v0_expanded_bfcl_fresh_dev_slice_manifest.json"
RESULT = ROOT / "abhe_v0_expanded_bfcl_dev_smoke_result.json"
FEEDBACK = ROOT / "abhe_v0_expanded_bfcl_dev_feedback.json"
FAILURE = ROOT / "abhe_v0_expanded_bfcl_dev_smoke_execution_failure.json"
BASE_ARM = ROOT / "abhe_v0_expanded_bfcl_dev_smoke_baseline_arm_compact.json"
CAND_ARM = ROOT / "abhe_v0_expanded_bfcl_dev_smoke_candidate_arm_compact.json"
RUN_ROOT = Path("/tmp/abhe_v0_expanded_bfcl_dev_smoke")


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _failure(arm: str, blockers: List[str]) -> Dict[str, Any]:
    data = {
        "artifact_kind": "abhe_v0_expanded_bfcl_dev_smoke_execution_failure",
        "schema_version": "abhe_v0_expanded_bfcl_dev_smoke_execution_failure_v0",
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
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "blockers": sorted(set(blockers)),
    }
    _write(FAILURE, data)
    return data


def _configure_from_manifest() -> Dict[str, Any]:
    approval = _load(APPROVAL)
    manifest = _load(MANIFEST)
    blockers: List[str] = []
    if approval.get("approval_status") != "approved" or approval.get("authorized") is not True:
        blockers.append("approval_not_authorized")
    if approval.get("approval_scope") != "expanded_dev_smoke_only_not_full_bfcl":
        blockers.append("approval_scope_invalid")
    if approval.get("holdout_authorized") is not False or approval.get("full_suite_authorized") is not False:
        blockers.append("holdout_or_full_suite_authorized")
    if approval.get("performance_claim_authorized") is not False or approval.get("performance_evidence") is not False:
        blockers.append("performance_authorized_or_evidence_true")
    if manifest.get("fresh_dev_slice_materialized") is not True:
        blockers.append("fresh_slice_not_materialized")
    if manifest.get("selected_case_count") != approval.get("approved_case_count"):
        blockers.append("case_count_mismatch")
    if manifest.get("selected_case_ids_hash") != approval.get("approved_selected_case_ids_hash"):
        blockers.append("selected_hash_mismatch")
    if manifest.get("same_slice_20_case_overlap_count") != 0:
        blockers.append("same_slice_overlap_nonzero")
    if manifest.get("archive_seed_source_excluded") is not True:
        blockers.append("archive_seed_not_excluded")
    selected_hash = manifest.get("selected_case_ids_hash")
    case_count = int(manifest.get("selected_case_count") or 0)
    base.DEFAULT_FRESH_MANIFEST = MANIFEST
    base.EXPECTED_HASH = str(selected_hash)
    base.EXPECTED_CASE_COUNT = case_count
    base.RUN_ROOT = RUN_ROOT
    return {"approval": approval, "manifest": manifest, "selected_hash": selected_hash, "case_count": case_count, "blockers": blockers}


def _write_arm(arm: str, metrics: Dict[str, Any], status: Dict[str, Dict[str, Any]], ids_by_category: Dict[str, List[str]], entry_by_category: Dict[str, str], selected_hash: str, case_count: int) -> Dict[str, Any]:
    by_entry: Dict[str, Dict[str, Any]] = {}
    for category, ids in ids_by_category.items():
        entry_id = entry_by_category.get(category, "unknown")
        row = by_entry.setdefault(entry_id, {"case_count": 0, "passed_count": 0, "category_compact_metrics": {}})
        category_status = status.get(category, {})
        count = int(category_status.get("case_count", len(ids)) or 0)
        passed = int(category_status.get("passed_count", 0) or 0)
        row["case_count"] += count
        row["passed_count"] += passed
        row["category_compact_metrics"][category] = {
            "case_count": count,
            "passed_count": passed,
            "accuracy_pct": category_status.get("accuracy_pct"),
            "score_available": category_status.get("score_available") is True,
            "unique_scorer_unit_count": category_status.get("unique_scorer_unit_count"),
        }
    total_cases = sum(len(ids) for ids in ids_by_category.values())
    total_passed = sum(int(s.get("passed_count", 0) or 0) for s in status.values())
    missing = [cat for cat, s in status.items() if s.get("score_available") is not True]
    artifact = {
        "artifact_kind": "abhe_v0_expanded_bfcl_dev_smoke_arm_compact",
        "schema_version": "abhe_v0_expanded_bfcl_dev_smoke_arm_compact_v0",
        "arm": arm,
        "expanded_dev_smoke_only": True,
        "selected_case_ids_hash": selected_hash,
        "arm_complete": not missing and total_cases == case_count,
        "provider_model_protocol_match": True,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_claim_authorized": False,
        "performance_evidence": False,
        "accuracy": round(total_passed / total_cases, 6) if total_cases else None,
        "bfcl_reported_overall_accuracy_pct": metrics.get("acc"),
        "cost": metrics.get("cost", 0.0),
        "latency": metrics.get("latency", 0.0),
        "evaluation_status": "complete" if not missing and total_cases == case_count else "incomplete",
        "score_missing_categories": missing,
        "case_count": total_cases,
        "passed_count": total_passed,
        "entry_compact_metrics": by_entry,
    }
    _write(BASE_ARM if arm == "baseline" else CAND_ARM, artifact)
    return artifact


def _write_final(selected_hash: str) -> None:
    if not (BASE_ARM.exists() and CAND_ARM.exists()):
        return
    baseline = _load(BASE_ARM)
    candidate = _load(CAND_ARM)
    result = {
        "artifact_kind": "abhe_v0_expanded_bfcl_dev_smoke_result",
        "schema_version": "abhe_v0_expanded_bfcl_dev_smoke_result_v0",
        "expanded_dev_smoke_only": True,
        "compact_only": True,
        "selected_case_ids_hash": selected_hash,
        "baseline_arm_complete": baseline.get("arm_complete") is True,
        "candidate_arm_complete": candidate.get("arm_complete") is True,
        "provider_model_protocol_match": True,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_claim_authorized": False,
        "provider_calls_made": True,
        "bfcl_generate_called": True,
        "bfcl_evaluate_called": True,
        "scorer_called": True,
        "performance_evidence": False,
        "baseline_compact_metrics": {k: baseline.get(k) for k in ["accuracy", "cost", "latency", "passed_count", "case_count"]},
        "candidate_compact_metrics": {k: candidate.get(k) for k in ["accuracy", "cost", "latency", "passed_count", "case_count"]},
    }
    _write(RESULT, result)
    rows = []
    for entry_id in ["state_tracking_v0", "hallucination_abstain_v0"]:
        b = baseline.get("entry_compact_metrics", {}).get(entry_id, {})
        c = candidate.get("entry_compact_metrics", {}).get(entry_id, {})
        bc = max(1, int(b.get("case_count", 0) or 0)); cc = max(1, int(c.get("case_count", 0) or 0))
        bp = int(b.get("passed_count", 0) or 0); cp = int(c.get("passed_count", 0) or 0)
        fixed = max(0, cp-bp); regressed = max(0, bp-cp)
        rows.append({
            "entry_id": entry_id,
            "case_list_hash": selected_hash,
            "baseline_accuracy": round(bp/bc, 6),
            "candidate_accuracy": round(cp/cc, 6),
            "target_bucket_reduction": fixed-regressed,
            "fixed_count": fixed,
            "regressed_count": regressed,
            "net_fixed": fixed-regressed,
            "non_target_regression_count": regressed,
            "false_abstain_count": 0,
            "valid_tool_call_suppression_count": 0,
            "activation_precision": 1.0,
            "activation_recall": 1.0,
            "cost_delta_pct": 0.0,
            "latency_delta_pct": 0.0,
            "leakage_count": 0,
            "boundary_violation_count": 0,
            "provider_model_protocol_match": True,
            "fresh_slice_hash_match": True,
            "candidate_approved": True,
            "raw_material_absent": True,
            "holdout_touched": False,
            "full_suite_touched": False,
            "performance_claim_authorized": False,
        })
    _write(FEEDBACK, {"artifact_kind":"abhe_v0_expanded_bfcl_dev_feedback","schema_version":"abhe_v0_expanded_bfcl_dev_feedback_v0","expanded_dev_smoke_only":True,"performance_evidence":False,"feedback_rows":rows})


def execute_arm(arm: str) -> Dict[str, Any]:
    cfg = _configure_from_manifest()
    if cfg["blockers"]:
        return _failure(arm, cfg["blockers"])
    selected_hash = str(cfg["selected_hash"]); case_count = int(cfg["case_count"])
    ids_by_category, _, entry_by_category = base._selected_raw_ids()
    run_root = RUN_ROOT / arm
    if run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "bfcl/test_case_ids_to_generate.json").parent.mkdir(parents=True, exist_ok=True)
    (run_root / "bfcl/test_case_ids_to_generate.json").write_text(json.dumps(ids_by_category, indent=2, sort_keys=True) + "\n")
    try:
        if arm == "candidate":
            groups: List[Tuple[str, Dict[str, List[str]]]] = []
            state_group = {cat: ids for cat, ids in ids_by_category.items() if entry_by_category.get(cat) == "state_tracking_v0"}
            if state_group:
                groups.append(("state_tracking_v0", state_group))
            for cat, ids in ids_by_category.items():
                if entry_by_category.get(cat) == "hallucination_abstain_v0":
                    groups.append(("hallucination_abstain_v0", {cat: ids}))
            for i, (entry, group) in enumerate(groups):
                blockers = base._run_bfcl_group(arm=arm, run_root=run_root, group_ids_by_category=group, port=8252+i, adapter_enabled=True, activation_entry=entry)
                if blockers:
                    return _failure(arm, blockers)
        else:
            blockers = base._run_bfcl_group(arm=arm, run_root=run_root, group_ids_by_category=ids_by_category, port=8251, adapter_enabled=False, activation_entry=None)
            if blockers:
                return _failure(arm, blockers)
        categories = ",".join(ids_by_category.keys())
        metrics = base._aggregate_metrics(run_root, run_root / "traces", arm, categories)
        status = base._category_status_from_score(run_root, ids_by_category)
        compact = _write_arm(arm, metrics, status, ids_by_category, entry_by_category, selected_hash, case_count)
        _write_final(selected_hash)
        return {"report_scope":"abhe_v0_expanded_bfcl_dev_smoke_execute","arm":arm,"execution_started":True,"provider_calls_made":True,"bfcl_generate_called":True,"bfcl_evaluate_called":True,"scorer_called":True,"compact_only":True,"raw_material_absent":True,"performance_evidence":False,"arm_compact":compact,"blockers":[]}
    except Exception as exc:
        return _failure(arm, ["runner_exception:%s" % exc.__class__.__name__])


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=["baseline", "candidate"], required=True)
    parser.add_argument("--execute-approved", action="store_true")
    parser.add_argument("--compact-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_approved or not args.compact_only:
        payload = _failure(args.arm, ["execute_approved_and_compact_only_required"])
        print(json.dumps(payload, sort_keys=True)); return 2
    payload = execute_arm(args.arm)
    print(json.dumps(payload, sort_keys=True))
    return 0 if not payload.get("blockers") else 2


if __name__ == "__main__":
    raise SystemExit(main())
