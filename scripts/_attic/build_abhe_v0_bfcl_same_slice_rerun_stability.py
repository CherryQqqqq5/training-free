#!/usr/bin/env python3
"""Build ABHE-v0 same-slice rerun stability evidence from compact artifacts."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_PRIOR = ROOT / "abhe_v0_bfcl_same_slice_prior_snapshot.json"
DEFAULT_OUTPUT = ROOT / "abhe_v0_bfcl_same_slice_rerun_stability.json"
RESULT = ROOT / "abhe_v0_bfcl_dev_smoke_result.json"
FEEDBACK = ROOT / "abhe_v0_bfcl_dev_feedback.json"
DELTA = ROOT / "abhe_v0_bfcl_same_slice_rerun_case_delta_analysis.json"
TRACE = ROOT / "abhe_v0_bfcl_same_slice_rerun_trace_analysis.json"
EXPECTED_HASH = "sha256:8e28826895c76afd14fb2ec07550b871ea50df25c0666881dad39be86450991f"


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _feedback_by_entry(feedback: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(row.get("entry_id")): row
        for row in feedback.get("feedback_rows", [])
        if isinstance(row, dict)
    }


def compact_snapshot(*, label: str) -> Dict[str, Any]:
    result = _load(RESULT)
    feedback = _load(FEEDBACK)
    delta = _load(DELTA)
    rows = _feedback_by_entry(feedback)
    state_row = rows.get("state_tracking_v0") or {}
    hallucination_row = rows.get("hallucination_abstain_v0") or {}
    return {
        "artifact_kind": "abhe_v0_bfcl_same_slice_run_snapshot",
        "schema_version": "abhe_v0_bfcl_same_slice_run_snapshot_v0",
        "label": label,
        "snapshot_created_at_unix": int(time.time()),
        "bounded_dev_smoke_only": True,
        "selected_case_ids_hash": result.get("selected_case_ids_hash"),
        "baseline_passed_count": (result.get("baseline_compact_metrics") or {}).get("passed_count"),
        "candidate_passed_count": (result.get("candidate_compact_metrics") or {}).get("passed_count"),
        "baseline_accuracy": (result.get("baseline_compact_metrics") or {}).get("accuracy"),
        "candidate_accuracy": (result.get("candidate_compact_metrics") or {}).get("accuracy"),
        "state_tracking_candidate_accuracy": state_row.get("candidate_accuracy"),
        "state_tracking_fixed_count": state_row.get("fixed_count"),
        "state_tracking_regressed_count": state_row.get("regressed_count"),
        "hallucination_candidate_accuracy": hallucination_row.get("candidate_accuracy"),
        "hallucination_fixed_count": hallucination_row.get("fixed_count"),
        "hallucination_regressed_count": hallucination_row.get("regressed_count"),
        "hallucination_false_abstain_count": hallucination_row.get("false_abstain_count"),
        "hallucination_valid_tool_call_suppression_count": hallucination_row.get("valid_tool_call_suppression_count"),
        "strict_scorer_unit_fixed_count": delta.get("strict_scorer_unit_fixed_count"),
        "scaled_compact_fixed_count": delta.get("scaled_compact_fixed_count"),
        "scaled_compact_regressed_count": delta.get("scaled_compact_regressed_count"),
        "state_tracking_signal_summary": delta.get("state_tracking_signal_summary"),
        "hallucination_abstain_signal_summary": delta.get("hallucination_abstain_signal_summary"),
        "strict_per_compact_case_paired_available": delta.get("strict_per_compact_case_paired_available"),
        "raw_material_absent": True,
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
    }


def snapshot_prior(path: Path) -> Dict[str, Any]:
    snap = compact_snapshot(label="prior_before_same_slice_rerun")
    snap["artifact_kind"] = "abhe_v0_bfcl_same_slice_prior_snapshot"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snap


def _abs_delta(a: Any, b: Any) -> Optional[int]:
    if isinstance(a, int) and isinstance(b, int):
        return abs(a - b)
    return None


def build_stability(prior_path: Path = DEFAULT_PRIOR, trace_path: Path = TRACE) -> Dict[str, Any]:
    prior = _load(prior_path)
    current = compact_snapshot(label="same_slice_rerun")
    feedback = _load(FEEDBACK)
    rows = _feedback_by_entry(feedback)
    delta = _load(DELTA)
    trace = _load(trace_path) if trace_path.exists() else {}
    blockers: List[str] = []

    if current.get("selected_case_ids_hash") != EXPECTED_HASH or prior.get("selected_case_ids_hash") != EXPECTED_HASH:
        blockers.append("selected_case_ids_hash_mismatch")
    baseline_delta = _abs_delta(prior.get("baseline_passed_count"), current.get("baseline_passed_count"))
    candidate_delta = _abs_delta(prior.get("candidate_passed_count"), current.get("candidate_passed_count"))
    if baseline_delta is None or baseline_delta > 2:
        blockers.append("baseline_same_slice_unstable")
    if candidate_delta is None or candidate_delta > 2:
        blockers.append("candidate_same_slice_unstable")
    if not isinstance(current.get("candidate_passed_count"), int) or current["candidate_passed_count"] < 15:
        blockers.append("candidate_passed_count_below_expanded_dev_threshold")

    state_row = rows.get("state_tracking_v0") or {}
    hallucination_row = rows.get("hallucination_abstain_v0") or {}
    if state_row.get("candidate_accuracy", 0) <= state_row.get("baseline_accuracy", 0):
        blockers.append("state_tracking_not_improved_over_baseline")
    if state_row.get("regressed_count", 0) != 0:
        blockers.append("state_tracking_regression_detected")
    if hallucination_row.get("candidate_accuracy", 0) <= hallucination_row.get("baseline_accuracy", 0):
        blockers.append("hallucination_not_improved_over_baseline")
    if hallucination_row.get("regressed_count", 0) != 0:
        blockers.append("hallucination_regression_detected")
    if hallucination_row.get("false_abstain_count", 0) != 0:
        blockers.append("hallucination_false_abstain_detected")
    if hallucination_row.get("valid_tool_call_suppression_count", 0) != 0:
        blockers.append("valid_tool_call_suppression_detected")
    if abs(float(hallucination_row.get("cost_delta_pct", 0) or 0)) > 5.0:
        blockers.append("cost_delta_bound_exceeded")
    if abs(float(hallucination_row.get("latency_delta_pct", 0) or 0)) > 20.0:
        blockers.append("latency_delta_bound_exceeded")
    if delta.get("scaled_compact_regressed_count") != 0:
        blockers.append("scaled_compact_regression_detected")
    if "irrelevance" not in str(delta.get("hallucination_abstain_signal_summary", "")):
        blockers.append("irrelevance_fixed_signal_missing")

    prior_live_status = "unknown"
    prior_signal = prior.get("hallucination_abstain_signal_summary")
    if isinstance(prior_signal, str):
        prior_live_status = "fixed" if "live_irrelevance" in prior_signal else "not_fixed"
    live_rows = [
        row
        for row in delta.get("category_delta_rows", [])
        if isinstance(row, dict) and row.get("bfcl_category") == "live_irrelevance"
    ]
    current_live_delta = live_rows[0].get("delta") if live_rows else "missing"
    live_signal_changed = prior_live_status == "not_fixed" and current_live_delta == "fixed"
    if not live_rows:
        blockers.append("live_irrelevance_missing_from_delta_analysis")

    if trace_path.exists():
        if trace.get("raw_material_absent") is not True or trace.get("performance_evidence") is not False:
            blockers.append("trace_boundary_invalid")
    else:
        blockers.append("same_slice_rerun_trace_analysis_missing")

    for key in ["performance_evidence", "holdout_touched", "full_suite_touched"]:
        if any(snapshot.get(key) not in (False, None) for snapshot in [current, prior]):
            blockers.append("%s_not_false" % key)

    report = {
        "artifact_kind": "abhe_v0_bfcl_same_slice_rerun_stability",
        "schema_version": "abhe_v0_bfcl_same_slice_rerun_stability_v0",
        "bounded_dev_smoke_only": True,
        "selected_case_ids_hash": EXPECTED_HASH,
        "prior_snapshot_path": str(prior_path),
        "rerun_trace_analysis_path": str(trace_path),
        "prior_snapshot": prior,
        "rerun_snapshot": current,
        "same_slice_stability_criteria": {
            "baseline_passed_count_abs_delta_max": 2,
            "candidate_passed_count_abs_delta_max": 2,
            "candidate_passed_count_min": 15,
            "entry_candidate_accuracy_must_exceed_baseline": True,
            "strict_scorer_unit_fixed_count_min": 3,
            "regressed_count_required": 0,
            "false_abstain_count_required": 0,
            "valid_tool_call_suppression_count_required": 0,
            "cost_delta_pct_abs_max": 5.0,
            "latency_delta_pct_abs_max": 20.0,
            "live_irrelevance_delta_recorded_not_gate": True,
        },
        "baseline_passed_count_abs_delta": baseline_delta,
        "candidate_passed_count_abs_delta": candidate_delta,
        "prior_live_irrelevance_status": prior_live_status,
        "live_irrelevance_rerun_delta": current_live_delta,
        "live_irrelevance_signal_changed_from_prior": live_signal_changed,
        "same_slice_rerun_stable": not blockers,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "next_required_action": "prepare_expanded_40_60_case_dev_smoke_review_package_not_full_bfcl",
        "blockers": sorted(set(blockers)),
    }
    report["blockers"] = sorted(
        set(report["blockers"] + scan_value(report, label="abhe_v0_bfcl_same_slice_rerun_stability"))
    )
    report["same_slice_rerun_stability_passed"] = not report["blockers"]
    return report


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-prior", action="store_true")
    parser.add_argument("--prior", type=Path, default=DEFAULT_PRIOR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--trace-analysis", type=Path, default=TRACE)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = snapshot_prior(args.prior) if args.snapshot_prior else build_stability(args.prior, args.trace_analysis)
        if args.write and not args.snapshot_prior:
            write_json(args.output, data)
    except Exception as exc:
        data = {
            "artifact_kind": "abhe_v0_bfcl_same_slice_rerun_stability",
            "same_slice_rerun_stability_passed": False,
            "raw_material_absent": True,
            "performance_evidence": False,
            "blockers": ["load_failed:%s" % exc.__class__.__name__],
        }
    print(json.dumps(data, sort_keys=True) if args.compact else json.dumps(data, indent=2, sort_keys=True))
    return 1 if args.strict and not (data.get("same_slice_rerun_stability_passed") or args.snapshot_prior) else 0


if __name__ == "__main__":
    raise SystemExit(main())
