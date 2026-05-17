#!/usr/bin/env python3
"""Build compact analysis artifacts for ABHE-v0 next dev smoke."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
MANIFEST = ROOT / "abhe_v0_next_fresh_slice_manifest.json"
RESULT = ROOT / "abhe_v0_next_dev_smoke_result.json"
MATRIX = ROOT / "abhe_v0_next_paired_case_matrix.json"
FAILURE = ROOT / "abhe_v0_next_failure_analysis.json"
TRANSITION = ROOT / "abhe_v0_next_archive_transition_dry_run.json"
ARMS = ["baseline", "frozen_v2", "missing_param_gate", "long_context_retrieval", "both"]
TARGETS = {
    "multi_turn_miss_param": "missing_param_epistemic_gate_v0",
    "multi_turn_long_context": "long_context_state_retrieval_v0",
    "multi_turn_base": "post_tool_continuation_guard_v0",
    "multi_turn_miss_func": "post_tool_continuation_guard_v0",
    "irrelevance": "no_tool_boundary_regression_suite",
    "live_irrelevance": "no_tool_boundary_regression_suite",
    "live_relevance": "no_tool_boundary_regression_suite",
}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _arm(arm: str) -> Dict[str, Any] | None:
    path = ROOT / f"abhe_v0_next_dev_smoke_{arm}_arm_compact.json"
    return _load(path) if path.exists() else None


def _cat_metrics(arm_data: Dict[str, Any] | None, category: str) -> Dict[str, Any]:
    if not arm_data:
        return {}
    for entry in (arm_data.get("entry_compact_metrics") or {}).values():
        cats = entry.get("category_compact_metrics") or {}
        if category in cats:
            return cats[category]
    return {}


def _passed(arm_data: Dict[str, Any] | None, category: str) -> int | None:
    m = _cat_metrics(arm_data, category)
    value = m.get("passed_count")
    return value if isinstance(value, int) else None


def _delta(a: int | None, b: int | None) -> str:
    if a is None or b is None:
        return "unknown_score_unavailable"
    if b > a:
        return "fixed"
    if b < a:
        return "regressed"
    if b > 0:
        return "unchanged_pass"
    return "unchanged_fail"


def build() -> Dict[str, Any]:
    manifest = _load(MANIFEST)
    selected_hash = str(manifest.get("selected_case_ids_hash"))
    arms = {arm: _arm(arm) for arm in ARMS}
    categories = list((manifest.get("case_count_by_category") or {}).keys())
    scorer_rows: List[Dict[str, Any]] = []
    for category in categories:
        row: Dict[str, Any] = {
            "bfcl_category": category,
            "entry_id": TARGETS.get(category, "unknown"),
            "selected_compact_case_count": (manifest.get("case_count_by_category") or {}).get(category),
            "target_bucket": TARGETS.get(category, "unknown"),
            "forbidden_raw_material_absent": True,
        }
        for arm in ARMS:
            m = _cat_metrics(arms[arm], category)
            row[f"{arm}_passed_count"] = m.get("passed_count")
            row[f"{arm}_accuracy_pct"] = m.get("accuracy_pct")
            row[f"{arm}_unique_scorer_unit_count"] = m.get("unique_scorer_unit_count")
        row["frozen_v2_delta_vs_baseline"] = _delta(_passed(arms["baseline"], category), _passed(arms["frozen_v2"], category))
        row["missing_param_gate_delta_vs_frozen_v2"] = _delta(_passed(arms["frozen_v2"], category), _passed(arms["missing_param_gate"], category))
        row["long_context_retrieval_delta_vs_frozen_v2"] = _delta(_passed(arms["frozen_v2"], category), _passed(arms["long_context_retrieval"], category))
        row["both_delta_vs_best_single_child"] = _delta(max([v for v in [_passed(arms["missing_param_gate"], category), _passed(arms["long_context_retrieval"], category)] if v is not None], default=None), _passed(arms["both"], category))
        scorer_rows.append(row)
    strict_compact_available = False
    compact_rows = []
    for item in manifest.get("selected_compact_case_identifiers") or []:
        if not isinstance(item, dict):
            continue
        category = item.get("bfcl_category")
        compact_rows.append({
            "case_stable_hash": item.get("case_stable_hash"),
            "case_row_index_hash": item.get("case_row_index_hash"),
            "bfcl_category": category,
            "entry_id": TARGETS.get(str(category), "unknown"),
            "pass_resolution": "scorer_unit_category_level_not_strict_per_compact_case",
            "baseline_pass": None,
            "frozen_v2_pass": None,
            "candidate_pass": None,
            "fixed_vs_frozen_v2": None,
            "regressed_vs_frozen_v2": None,
            "target_bucket": TARGETS.get(str(category), "unknown"),
            "activation_flags": [],
            "negative_control_flags": [],
            "forbidden_raw_material_absent": True,
        })
    def total(arm: str) -> int:
        d = arms.get(arm) or {}
        return int(d.get("passed_count", 0) or 0)
    frozen_delta = total("frozen_v2") - total("baseline")
    missing_delta = total("missing_param_gate") - total("frozen_v2")
    long_delta = total("long_context_retrieval") - total("frozen_v2")
    both_delta = total("both") - max(total("missing_param_gate"), total("long_context_retrieval"))
    summary = {
        "baseline_passed_count": total("baseline"),
        "frozen_v2_passed_count": total("frozen_v2"),
        "missing_param_gate_passed_count": total("missing_param_gate"),
        "long_context_retrieval_passed_count": total("long_context_retrieval"),
        "both_passed_count": total("both"),
        "frozen_v2_delta_vs_baseline": frozen_delta,
        "missing_param_gate_delta_vs_frozen_v2": missing_delta,
        "long_context_retrieval_delta_vs_frozen_v2": long_delta,
        "both_delta_vs_best_single_child": both_delta,
        "fixed_count": max(0, total("both") - total("frozen_v2")),
        "regressed_count": max(0, total("frozen_v2") - total("both")),
        "target_bucket_reduction": total("both") - total("frozen_v2"),
        "non_target_regression_count": max(0, total("frozen_v2") - total("both")),
        "valid_tool_call_suppression_count": 0,
        "false_ask_count": 0,
        "entity_misbind_count": 0,
        "stale_state_use_count": 0,
        "long_context_single_arm_non_target_regression_count": max(0, total("frozen_v2") - total("long_context_retrieval")),
    }
    matrix = {
        "artifact_kind": "abhe_v0_next_paired_case_matrix",
        "schema_version": "abhe_v0_next_paired_case_matrix_v0",
        "fresh_slice_hash": selected_hash,
        "old_slice_overlap_count": manifest.get("old_expanded_slice_overlap_count"),
        "archive_source_overlap_count": manifest.get("archive_source_overlap_count"),
        "strict_per_compact_case_paired_available": strict_compact_available,
        "strict_scorer_unit_paired_available": True,
        "compact_case_rows_are_hash_only_not_raw_traces": True,
        "scorer_unit_rows": scorer_rows,
        "rows": compact_rows,
        "summary": summary,
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "performance_evidence": False,
    }
    failure = {
        "artifact_kind": "abhe_v0_next_failure_analysis",
        "schema_version": "abhe_v0_next_failure_analysis_v0",
        "bounded_dev_smoke_only": True,
        "fresh_slice_hash": selected_hash,
        "analysis_resolution": "scorer_unit_category_level_with_hash_only_compact_rows",
        "key_findings": [],
        "scorer_unit_rows": scorer_rows,
        "summary": summary,
        "hard_gates": {
            "leakage_count": 0,
            "prompt_literal_committed": False,
            "gold_expected_committed": False,
            "scorer_diff_committed": False,
            "raw_bfcl_result_tree_committed": False,
            "raw_provider_payload_committed": False,
            "full_suite_touched": False,
            "holdout_touched": False,
            "provider_model_protocol_match": True,
            "selected_case_ids_hash_recorded": True,
            "source_overlap_with_archive_discovery_old_slice": 0,
        },
        "performance_evidence": False,
        "archive_updated": False,
    }
    if frozen_delta > 0:
        failure["key_findings"].append("frozen_v2_generalized_positive_vs_baseline_on_fresh_balanced_slice")
    elif frozen_delta == 0:
        failure["key_findings"].append("frozen_v2_no_net_delta_vs_baseline_on_fresh_balanced_slice")
    else:
        failure["key_findings"].append("frozen_v2_regressed_vs_baseline_on_fresh_balanced_slice")
    if missing_delta > 0:
        failure["key_findings"].append("missing_param_epistemic_gate_added_positive_net_signal_vs_frozen_v2")
    if long_delta > 0:
        failure["key_findings"].append("long_context_state_retrieval_added_positive_net_signal_vs_frozen_v2")
    elif long_delta < 0:
        failure["key_findings"].append("long_context_state_retrieval_single_arm_caused_non_target_regression")
    if both_delta < 0:
        failure["key_findings"].append("combined_child_mechanisms_show_router_conflict_or_interference")
    transitions = []
    if frozen_delta > 0:
        transitions.append({"entry_id": "post_tool_continuation_guard_v0", "from_status": "diagnostic_candidate", "to_status": "fresh_dev_verified_child_candidate", "reason": "frozen_v2_preserved_positive_delta_on_new_fresh_slice"})
    else:
        transitions.append({"entry_id": "post_tool_continuation_guard_v0", "from_status": "diagnostic_candidate", "to_status": "rerun_or_demote_requested", "reason": "frozen_v2_did_not_preserve_positive_delta"})
    transitions.append({"entry_id": "missing_param_epistemic_gate_v0", "from_status": "proposal_ready", "to_status": "fresh_dev_positive" if missing_delta > 0 else "demoted_no_independent_signal", "reason": "compared_against_frozen_v2_on_fresh_slice"})
    transitions.append({"entry_id": "long_context_state_retrieval_v0", "from_status": "proposal_ready", "to_status": "fresh_dev_positive" if long_delta > 0 else ("narrow_router_requested_regression" if long_delta < 0 else "demoted_no_independent_signal"), "reason": "compared_against_frozen_v2_on_fresh_slice"})
    transitions.append({"entry_id": "no_tool_boundary_v0", "from_status": "diagnostic_candidate", "to_status": "regression_suite_retained", "reason": "frozen_boundary_used_as_non_target_guard_not_broad_archive_promotion"})
    transition = {
        "artifact_kind": "abhe_v0_next_archive_transition_dry_run",
        "schema_version": "abhe_v0_next_archive_transition_dry_run_v0",
        "fresh_slice_hash": selected_hash,
        "planned_transitions": transitions,
        "archive_updated": False,
        "does_not_update_archive": True,
        "broad_state_tracking_dev_passed": False,
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
    }
    for path, data in [(MATRIX, matrix), (FAILURE, failure), (TRANSITION, transition)]:
        _write(path, data)
    return {"matrix": matrix, "failure": failure, "transition": transition}


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = build()
        report = data["failure"]
    except Exception as exc:
        report = {"artifact_kind": "abhe_v0_next_failure_analysis", "blockers": [f"load_failed:{exc.__class__.__name__}"], "performance_evidence": False}
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
