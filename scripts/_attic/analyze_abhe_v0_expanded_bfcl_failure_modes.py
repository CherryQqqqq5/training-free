#!/usr/bin/env python3
"""Build compact analysis for the ABHE-v0 expanded BFCL dev smoke."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_RESULT = ROOT / "abhe_v0_expanded_bfcl_dev_smoke_result.json"
DEFAULT_FEEDBACK = ROOT / "abhe_v0_expanded_bfcl_dev_feedback.json"
DEFAULT_TRACE_ANALYSIS = ROOT / "abhe_v0_expanded_bfcl_trace_analysis.json"
DEFAULT_OUTPUT = ROOT / "abhe_v0_expanded_bfcl_failure_analysis.json"
EXPECTED_HASH = "sha256:e4819b4c639b7fea383ccbe1c73e1591418cce61aceee0ce9a31af21ed2cffe2"


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _entry_feedback(feedback: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = feedback.get("feedback_rows")
    if not isinstance(rows, list):
        return {}
    return {str(row.get("entry_id")): row for row in rows if isinstance(row, dict)}


def build_analysis(
    *,
    result_path: Path = DEFAULT_RESULT,
    feedback_path: Path = DEFAULT_FEEDBACK,
    trace_analysis_path: Path = DEFAULT_TRACE_ANALYSIS,
) -> Dict[str, Any]:
    blockers: List[str] = []
    result = _load(result_path)
    feedback = _load(feedback_path)
    trace_analysis = _load(trace_analysis_path)
    if result.get("selected_case_ids_hash") != EXPECTED_HASH:
        blockers.append("selected_case_ids_hash_mismatch")
    if result.get("expanded_dev_smoke_only") is not True:
        blockers.append("expanded_dev_smoke_only_not_true")
    for key in [
        "performance_evidence",
        "performance_claim_authorized",
        "holdout_touched",
        "full_suite_touched",
        "raw_provider_payload_committed",
        "raw_bfcl_result_tree_committed",
        "gold_expected_committed",
        "scorer_diff_committed",
    ]:
        if result.get(key) is not False:
            blockers.append(f"{key}_not_false")
    if trace_analysis.get("raw_material_absent") is not True:
        blockers.append("trace_raw_material_absent_not_true")

    entry_rows = _entry_feedback(feedback)
    state = entry_rows.get("state_tracking_v0", {})
    relevance = entry_rows.get("hallucination_abstain_v0", {})
    trace_patterns = trace_analysis.get("all_trace_pattern_counts") or {}
    trace_entry_counts = trace_analysis.get("all_trace_entry_counts") or {}
    baseline_metrics = result.get("baseline_compact_metrics") or {}
    candidate_metrics = result.get("candidate_compact_metrics") or {}

    state_fixed = int(state.get("fixed_count", 0) or 0)
    state_regressed = int(state.get("regressed_count", 0) or 0)
    relevance_fixed = int(relevance.get("fixed_count", 0) or 0)
    relevance_regressed = int(relevance.get("regressed_count", 0) or 0)
    state_effect_label = ("partial_expanded_dev_signal_with_remaining_substrata_failures" if state_fixed > state_regressed and state_fixed > 0 else "no_expanded_dev_signal")
    state_recommended_action = ("narrow_router_requested" if state_fixed > state_regressed and state_fixed > 0 else "split_requested")
    relevance_effect_label = ("strong_expanded_dev_signal_but_should_split_for_precision" if relevance_fixed > relevance_regressed and relevance_fixed > 0 else "no_expanded_dev_signal")

    analysis = {
        "artifact_kind": "abhe_v0_expanded_bfcl_failure_analysis",
        "schema_version": "abhe_v0_expanded_bfcl_failure_analysis_v0",
        "selected_case_ids_hash": EXPECTED_HASH,
        "expanded_dev_smoke_only": True,
        "compact_only": True,
        "source_artifacts": {
            "result": str(result_path),
            "feedback": str(feedback_path),
            "trace_analysis": str(trace_analysis_path),
        },
        "headline_metrics": {
            "baseline_passed_count": baseline_metrics.get("passed_count"),
            "baseline_case_count": baseline_metrics.get("case_count"),
            "baseline_accuracy": baseline_metrics.get("accuracy"),
            "candidate_passed_count": candidate_metrics.get("passed_count"),
            "candidate_case_count": candidate_metrics.get("case_count"),
            "candidate_accuracy": candidate_metrics.get("accuracy"),
            "net_compact_pass_delta": (candidate_metrics.get("passed_count") or 0)
            - (baseline_metrics.get("passed_count") or 0),
        },
        "entry_effect_summary": {
            "state_tracking_v0": {
                "effect_label": state_effect_label,
                "baseline_accuracy": state.get("baseline_accuracy"),
                "candidate_accuracy": state.get("candidate_accuracy"),
                "fixed_count": state.get("fixed_count"),
                "regressed_count": state.get("regressed_count"),
                "target_bucket_reduction": state.get("target_bucket_reduction"),
                "likely_failure_mechanism": "post_tool_continuation_and_instance_state_mismatch_partly_fixed_by_continuation_guard_but_remaining_substrata_fail",
                "recommended_archive_action": state_recommended_action,
                "recommended_child_clusters": [
                    "post_tool_continuation_failure_v0",
                    "multi_turn_state_binding_v0",
                    "multi_turn_missing_function_recovery_v0",
                ],
            },
            "hallucination_abstain_v0": {
                "effect_label": relevance_effect_label,
                "baseline_accuracy": relevance.get("baseline_accuracy"),
                "candidate_accuracy": relevance.get("candidate_accuracy"),
                "fixed_count": relevance.get("fixed_count"),
                "regressed_count": relevance.get("regressed_count"),
                "target_bucket_reduction": relevance.get("target_bucket_reduction"),
                "likely_effective_mechanism": "entry_specific_no_tool_boundary_for_irrelevance_and_live_irrelevance",
                "recommended_archive_action": "split_or_conditional_dev_passed",
                "recommended_child_clusters": [
                    "irrelevance_no_tool_boundary_v0",
                    "live_irrelevance_no_tool_boundary_v0",
                    "live_relevance_guard_v0",
                ],
            },
        },
        "trace_signal_summary": {
            "trace_counts_by_arm": trace_analysis.get("trace_counts_by_arm"),
            "sanitized_trace_card_count": trace_analysis.get("sanitized_trace_card_count"),
            "all_trace_pattern_counts": trace_patterns,
            "all_trace_entry_counts": trace_entry_counts,
            "diagnostic_interpretation": {
                "state_tracking": "state guidance was applied frequently, but compact traces still show post-tool prose summaries and state mismatch symptoms",
                "relevance_boundary": "no-tool boundary is the strongest observed mechanism and should remain entry-specific",
            },
        },
        "overfit_controls": {
            "raw_case_identifier_allowlists_forbidden": True,
            "do_not_use_prompt_literals": True,
            "evaluator_target_conditions_forbidden": True,
            "refine_by_behavior_cluster_not_case": True,
            "next_eval_should_use_same_slice_diagnostic_then_new_fresh_slice_before_claim": True,
        },
        "algorithmic_recommendations": [
            {
                "priority": 1,
                "entry_id": "state_tracking_v0",
                "recommendation": "keep_post_tool_continuation_controller_and_split_remaining_state_substrata",
                "reason": "state_tracking improved after continuation guard but remaining multi-turn substrata still fail",
            },
            {
                "priority": 2,
                "entry_id": "hallucination_abstain_v0",
                "recommendation": "promote_no_tool_boundary_as_relevance_boundary_candidate_and split live relevance guard",
                "reason": "expanded dev fixed relevance/irrelevance compact units without false-abstain regression, but the cluster mixes no-tool and valid-tool-call behavior",
            },
            {
                "priority": 3,
                "entry_id": "state_tracking_v0",
                "recommendation": "add scorer-unit-level compact pairing before larger expansion",
                "reason": "multi-turn BFCL uses all-or-nothing state checks, so aggregate pass counts need mechanism labels before claims",
            },
        ],
        "archive_updated": False,
        "does_not_update_archive": True,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_claim_authorized": False,
        "performance_evidence": False,
        "blockers": sorted(set(blockers)),
        "next_required_action": "run_state_continuation_refinement_as_bounded_dev_diagnostic_only",
    }
    analysis["blockers"] = sorted(set(analysis["blockers"] + scan_value(analysis, label="abhe_v0_expanded_bfcl_failure_analysis")))
    analysis["abhe_v0_expanded_bfcl_failure_analysis_passed"] = not analysis["blockers"]
    return analysis


def write_analysis(path: Path, analysis: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--feedback", type=Path, default=DEFAULT_FEEDBACK)
    parser.add_argument("--trace-analysis", type=Path, default=DEFAULT_TRACE_ANALYSIS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        analysis = build_analysis(result_path=args.result, feedback_path=args.feedback, trace_analysis_path=args.trace_analysis)
        if args.write:
            write_analysis(args.output, analysis)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        analysis = {
            "artifact_kind": "abhe_v0_expanded_bfcl_failure_analysis",
            "abhe_v0_expanded_bfcl_failure_analysis_passed": False,
            "raw_material_absent": True,
            "performance_evidence": False,
            "blockers": [f"load_failed:{exc.__class__.__name__}"],
        }
    print(json.dumps(analysis, sort_keys=True) if args.compact else json.dumps(analysis, indent=2, sort_keys=True))
    return 1 if args.strict and not analysis.get("abhe_v0_expanded_bfcl_failure_analysis_passed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
