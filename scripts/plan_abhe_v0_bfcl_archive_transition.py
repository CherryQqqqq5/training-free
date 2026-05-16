#!/usr/bin/env python3
"""Plan ABHE-v0 archive transitions from compact BFCL dev feedback without updating archive."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value
from scripts.check_abhe_v0_bfcl_dev_feedback import validate_feedback

DEFAULT_FEEDBACK = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_feedback.json")
DEFAULT_DELTA = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_same_slice_rerun_case_delta_analysis.json")
DEFAULT_STABILITY = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_same_slice_rerun_stability.json")
DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_archive_transition_plan.json")


def decide_transition(row: Dict[str, Any]) -> str:
    if row.get("leakage_count", 0) > 0 or row.get("boundary_violation_count", 0) > 0:
        return "rejected_boundary_failure"
    if row.get("target_bucket_reduction", 0) <= 0:
        return "demoted_no_mechanism_signal"
    if row.get("fixed_count", 0) <= row.get("regressed_count", 0):
        return "demoted_regression_not_controlled"
    if row.get("non_target_regression_count", 0) >= 3 or row.get("false_abstain_count", 0) >= 3:
        return "narrow_router_requested"
    if row.get("target_bucket_reduction", 0) > 0 and row.get("fixed_count", 0) > row.get("regressed_count", 0):
        return "dev_passed"
    return "split_requested"


def synthetic_feedback() -> Dict[str, Any]:
    base = {
        "case_list_hash": "synthetic_fixture_hash_not_real_validation",
        "baseline_accuracy": 0.0,
        "candidate_accuracy": 0.0,
        "target_bucket_reduction": 2,
        "fixed_count": 3,
        "regressed_count": 1,
        "net_fixed": 2,
        "non_target_regression_count": 0,
        "false_abstain_count": 0,
        "valid_tool_call_suppression_count": 0,
        "activation_precision": 0.8,
        "activation_recall": 0.7,
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
    }
    rows = []
    for entry_id in ["state_tracking_v0", "hallucination_abstain_v0"]:
        row = dict(base)
        row["entry_id"] = entry_id
        rows.append(row)
    return {
        "artifact_kind": "abhe_v0_bfcl_dev_feedback",
        "schema_version": "abhe_v0_bfcl_dev_feedback_v0",
        "bounded_dev_smoke_only": True,
        "performance_evidence": False,
        "feedback_rows": rows,
    }


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _delta_rows(delta: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}
    for row in delta.get("category_delta_rows", []):
        if isinstance(row, dict) and row.get("bfcl_category"):
            rows[str(row["bfcl_category"])] = row
    return rows


def _real_sublanes(delta: Dict[str, Any], stability: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = _delta_rows(delta)
    live_signal_changed = stability.get("live_irrelevance_signal_changed_from_prior") is True
    sublanes: List[Dict[str, Any]] = []
    if "multi_turn_long_context" in rows:
        sublanes.append({
            "entry_id": "state_tracking_v0",
            "sublane_id": "multi_turn_long_context_state_carryover_v0",
            "bfcl_category": "multi_turn_long_context",
            "observed_delta": rows["multi_turn_long_context"].get("delta"),
            "recommended_action": "retain_for_expanded_dev_verification",
        })
    if "multi_turn_miss_func" in rows:
        sublanes.append({
            "entry_id": "state_tracking_v0",
            "sublane_id": "multi_turn_miss_func_state_tool_availability_v0",
            "bfcl_category": "multi_turn_miss_func",
            "observed_delta": rows["multi_turn_miss_func"].get("delta"),
            "recommended_action": "narrow_or_redesign_before_claiming_state_tracking_generalization",
        })
    if "irrelevance" in rows:
        sublanes.append({
            "entry_id": "hallucination_abstain_v0",
            "sublane_id": "irrelevance_no_tool_boundary_v0",
            "bfcl_category": "irrelevance",
            "observed_delta": rows["irrelevance"].get("delta"),
            "recommended_action": "retain_for_expanded_dev_verification",
        })
    if "live_irrelevance" in rows:
        sublanes.append({
            "entry_id": "hallucination_abstain_v0",
            "sublane_id": "live_irrelevance_boundary_v0",
            "bfcl_category": "live_irrelevance",
            "observed_delta": rows["live_irrelevance"].get("delta"),
            "signal_changed_between_runs": live_signal_changed,
            "recommended_action": "split_requested_and_verify_on_expanded_dev_before_dev_passed",
        })
    if "live_relevance" in rows:
        sublanes.append({
            "entry_id": "hallucination_abstain_v0",
            "sublane_id": "live_relevance_guard_v0",
            "bfcl_category": "live_relevance",
            "observed_delta": rows["live_relevance"].get("delta"),
            "recommended_action": "guard_retained_no_false_abstain_signal",
        })
    return sublanes


def build_plan(
    feedback: Dict[str, Any],
    *,
    synthetic_fixture_only: bool,
    delta: Dict[str, Any] | None = None,
    stability: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    blockers = validate_feedback(feedback)
    transitions: List[Dict[str, Any]] = []
    real_split_mode = not synthetic_fixture_only and isinstance(delta, dict)
    for row in feedback.get("feedback_rows", []):
        entry_id = row.get("entry_id")
        to_status = decide_transition(row)
        if real_split_mode and entry_id == "hallucination_abstain_v0" and to_status == "dev_passed":
            to_status = "split_requested"
        transitions.append({
            "entry_id": entry_id,
            "from_status": "proposal_ready",
            "to_status": to_status,
            "archive_updated": False,
            "does_not_update_archive": True,
            "source": "synthetic_fixture" if synthetic_fixture_only else "compact_bfcl_dev_feedback",
            "bounded_dev_only": True,
        })
    sublanes = _real_sublanes(delta or {}, stability or {}) if real_split_mode else []
    plan = {
        "artifact_kind": "abhe_v0_bfcl_archive_transition_plan",
        "schema_version": "abhe_v0_bfcl_archive_transition_plan_v0",
        "synthetic_fixture_only": synthetic_fixture_only,
        "bounded_dev_smoke_only": True,
        "archive_updated": False,
        "does_not_update_archive": True,
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "planned_transitions": transitions,
        "planned_sublane_transitions": sublanes,
        "same_slice_rerun_stability_passed": (stability or {}).get("same_slice_rerun_stability_passed"),
        "strict_per_compact_case_paired_available": (delta or {}).get("strict_per_compact_case_paired_available"),
        "strict_scorer_unit_fixed_count": (delta or {}).get("strict_scorer_unit_fixed_count"),
        "strict_scorer_unit_regressed_count": (delta or {}).get("strict_scorer_unit_regressed_count"),
        "scaled_compact_fixed_count": (delta or {}).get("scaled_compact_fixed_count"),
        "scaled_compact_regressed_count": (delta or {}).get("scaled_compact_regressed_count"),
        "next_required_action": "request_expanded_40_60_case_dev_smoke_not_full_bfcl",
        "blockers": sorted(set(blockers)),
    }
    plan["blockers"] = sorted(set(plan["blockers"] + scan_value(plan, label="abhe_v0_bfcl_archive_transition_plan")))
    plan["abhe_v0_bfcl_archive_transition_plan_passed"] = not plan["blockers"]
    return plan


def write_plan(output: Path, plan: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feedback", type=Path, default=DEFAULT_FEEDBACK)
    parser.add_argument("--delta-analysis", type=Path, default=DEFAULT_DELTA)
    parser.add_argument("--stability", type=Path, default=DEFAULT_STABILITY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--synthetic-fixture-only", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        feedback = synthetic_feedback() if args.synthetic_fixture_only else _load(args.feedback)
        delta = None if args.synthetic_fixture_only or not args.delta_analysis.exists() else _load(args.delta_analysis)
        stability = None if args.synthetic_fixture_only or not args.stability.exists() else _load(args.stability)
        plan = build_plan(feedback, synthetic_fixture_only=args.synthetic_fixture_only, delta=delta, stability=stability)
        write_plan(args.output, plan)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        plan = {
            "report_scope": "abhe_v0_bfcl_archive_transition_plan",
            "abhe_v0_bfcl_archive_transition_plan_passed": False,
            "blockers": ["load_failed:%s" % exc],
            "archive_updated": False,
            "does_not_update_archive": True,
        }
    print(json.dumps(plan, sort_keys=True) if args.compact else json.dumps(plan, indent=2, sort_keys=True))
    return 1 if args.strict and not plan.get("abhe_v0_bfcl_archive_transition_plan_passed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
