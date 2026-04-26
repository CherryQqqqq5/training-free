#!/usr/bin/env python3
"""Diagnose recall-aware fallback selection for M2.7ad.

This is an offline replay diagnostic. It does not call BFCL or any model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
OUT = DEFAULT_ROOT / "m27ad_fallback_selection.json"
MD = DEFAULT_ROOT / "m27ad_fallback_selection.md"
MIN_ACTIVATION = 10
MAX_DOMINANT_RATE = 0.8


def _j(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _brief(candidate: Any, *, status: str) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None
    guard = candidate.get("guard") if isinstance(candidate.get("guard"), dict) else {}
    scores = candidate.get("candidate_rank_scores") if isinstance(candidate.get("candidate_rank_scores"), dict) else {}
    risk_flags = candidate.get("trajectory_risk_flags") or scores.get("trajectory_risk_flags") or guard.get("risk_flags") or []
    return {
        "status": status,
        "tool": candidate.get("tool"),
        "args": candidate.get("args") or {},
        "binding_source": candidate.get("binding_source") or "+".join(scores.get("binding_sources") or []),
        "postcondition": candidate.get("postcondition") or scores.get("postcondition") or {},
        "trajectory_risk_flags": risk_flags,
        "intervention_mode": candidate.get("intervention_mode") or guard.get("intervention_mode"),
        "guard_reason": guard.get("reason"),
        "rank_tuple": candidate.get("rank_tuple"),
        "matched_regression_guard_key": candidate.get("matched_regression_guard_key"),
        "scorer_feedback_pattern_matched": bool(candidate.get("scorer_feedback_pattern_matched")),
        "scorer_feedback_pattern_action": candidate.get("scorer_feedback_pattern_action"),
        "scorer_feedback_fallback_guard_matched": bool(candidate.get("scorer_feedback_fallback_guard_matched")),
        "matched_fallback_guard_key": candidate.get("matched_fallback_guard_key"),
        "scorer_feedback_fallback_action": candidate.get("scorer_feedback_fallback_action"),
        "fallback_selection_class": candidate.get("fallback_selection_class"),
        "fallback_selection_action": candidate.get("fallback_selection_action"),
        "fallback_selection_reason": candidate.get("fallback_selection_reason"),
        "fallback_selection_risk_score": candidate.get("fallback_selection_risk_score"),
    }


def _case_map(preflight: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(case.get("case_id")): case for case in preflight.get("cases") or [] if isinstance(case, dict) and case.get("case_id")}


def _gap_map(gap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(case.get("case_id")): case for case in gap.get("cases") or [] if isinstance(case, dict) and case.get("case_id")}


def _risk_class(selected: dict[str, Any] | None, gap_case: dict[str, Any], *, block_all_breaks: bool) -> tuple[str, str, str, int]:
    if not selected:
        repair_kinds = set(gap_case.get("repair_kinds") or [])
        if "coerce_no_tool_text_to_empty" in repair_kinds:
            return "repair_policy_or_no_tool_coercion", "diagnostic_only", "no selected action candidate and scorer repair/no-tool evidence is present", 0
        return "ambiguous_regression", "diagnostic_only", "no selected fallback candidate; insufficient causal evidence", 0
    flags = set(selected.get("trajectory_risk_flags") or [])
    binding = str(selected.get("binding_source") or "")
    gap_type = str(gap_case.get("gap_type") or "")
    baseline_success = bool(gap_case.get("baseline_success"))
    weak_prior = "prior_tool_output" in binding or any("weak" in str(flag) for flag in flags)
    trajectory_sensitive = "trajectory_sensitive_tool" in flags or selected.get("tool") in {"cat", "touch", "mkdir"}
    pattern_overlap = bool(selected.get("scorer_feedback_pattern_matched"))
    risk_score = sum([baseline_success, weak_prior, trajectory_sensitive, pattern_overlap, gap_type == "proxy_arg_ok_scorer_arg_wrong"])
    if risk_score >= 4 and not block_all_breaks:
        return "unsafe_fallback", "record_only", "high-risk fallback can be blocked without breaking M2.7m activation", risk_score
    if risk_score >= 4 and block_all_breaks:
        return "fallback_chain_recall_tradeoff", "diagnostic_only", "fallback is risky, but blocking the chain would break M2.7m activation readiness", risk_score
    if risk_score >= 2:
        return "ambiguous_fallback", "diagnostic_only", "fallback has partial regression-risk features but not enough evidence for hard blocking", risk_score
    return "safe_fallback", "guidance", "fallback has low regression-risk evidence", risk_score


def evaluate(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    ab = _j(root / "m27ab_unresolved_regression_repair.json", {}) or {}
    ac = _j(root / "m27ac_pattern_guard_recall.json", {}) or {}
    gap = _j(root / "m27x_scorer_proxy_gap.json", {}) or {}
    preflight = _j(root / "m27i_guard_preflight.json", {}) or {}
    m = _j(root / "m27m_guidance_only_readiness.json", {}) or {}
    by_case = _case_map(preflight)
    by_gap = _gap_map(gap)
    unresolved = [str(item) for item in (ab.get("old_regression_unresolved_case_ids_after_repair") or ab.get("pattern_ineffective_case_ids") or [])]
    activated = int(m.get("plan_activated_count_after_guard") or preflight.get("plan_activated_count_after_guard") or 0)
    dominant = m.get("dominant_selected_next_tool_rate_after_guard", preflight.get("dominant_selected_next_tool_rate_after_guard"))
    m27m_passed = bool(m.get("m2_7m_preflight_passed") and m.get("m2_7m_guidance_only_readiness_passed"))
    fixed_blocked = int(ac.get("fixed_case_blocked_count") or 0)

    cases: list[dict[str, Any]] = []
    allowed_residual = 0
    unsafe_unblocked = 0
    block_all_breaks_any = False
    for case_id in unresolved:
        preflight_case = by_case.get(case_id, {})
        plan = preflight_case.get("after_guard_plan") if isinstance(preflight_case.get("after_guard_plan"), dict) else {}
        before = preflight_case.get("before_guard_plan") if isinstance(preflight_case.get("before_guard_plan"), dict) else {}
        selected = _brief(plan.get("selected_action_candidate"), status="selected")
        rejected = [_brief(item, status="rejected") for item in (plan.get("rejected_action_candidates") or [])]
        rejected = [item for item in rejected if item]
        blocked_fallbacks = [item for item in rejected if item.get("scorer_feedback_fallback_guard_matched") or item.get("scorer_feedback_fallback_action") == "record_only"]
        pattern_fallbacks = [item for item in ([selected] if selected else []) + rejected if item and item.get("scorer_feedback_pattern_matched")]
        activation_if_block_all = activated - (1 if selected else 0)
        activation_if_allow_low_risk = activated
        block_all_breaks = activation_if_block_all < MIN_ACTIVATION
        block_all_breaks_any = block_all_breaks_any or block_all_breaks
        gap_case = by_gap.get(case_id, {})
        klass, action, reason, risk_score = _risk_class(selected, gap_case, block_all_breaks=block_all_breaks)
        if klass in {"fallback_chain_recall_tradeoff", "repair_policy_or_no_tool_coercion"}:
            allowed_residual += 1
        if klass == "unsafe_fallback":
            unsafe_unblocked += 1
        cases.append(
            {
                "case_id": case_id,
                "primary_candidate": _brief(before.get("selected_action_candidate"), status="primary_before_guard"),
                "fallback_candidates_ranked": pattern_fallbacks,
                "which_fallback_was_blocked": blocked_fallbacks,
                "next_fallback_selected": selected,
                "why_next_fallback_selected": reason,
                "activation_if_block_all": activation_if_block_all,
                "activation_if_allow_low_risk": activation_if_allow_low_risk,
                "block_all_would_break_m27m_readiness": block_all_breaks,
                "regression_risk": {
                    "class": klass,
                    "score": risk_score,
                    "gap_type": gap_case.get("gap_type"),
                    "baseline_success_proxy": bool(gap_case.get("baseline_success")),
                },
                "fixed_case_collateral": {
                    "fixed_case_blocked_count": fixed_blocked,
                    "productive_nonregression_case_blocked_count": int(ac.get("productive_nonregression_case_blocked_count") or 0),
                },
                "repair_no_tool_evidence": {
                    "repair_kinds": gap_case.get("repair_kinds") or [],
                    "has_coerce_no_tool_text_to_empty": "coerce_no_tool_text_to_empty" in set(gap_case.get("repair_kinds") or []),
                },
                "fallback_selection_class": klass,
                "fallback_selection_action": action,
                "fallback_selection_reason": reason,
            }
        )

    unresolved_count = len(unresolved)
    old_unresolved_ok = unresolved_count == 0 or (unresolved_count <= 1 and allowed_residual == unresolved_count)
    readiness_ok = m27m_passed and activated >= MIN_ACTIVATION and isinstance(dominant, (int, float)) and dominant <= MAX_DOMINANT_RATE and fixed_blocked <= 1
    passed = bool(readiness_ok and old_unresolved_ok and unsafe_unblocked == 0)
    return {
        "report_scope": "m2_7ad_fallback_selection",
        "artifact_root": str(root),
        "source_reports": {
            "m27ab": str(root / "m27ab_unresolved_regression_repair.json"),
            "m27aa": str(root / "m27aa_regression_patterns.json"),
            "m27ac": str(root / "m27ac_pattern_guard_recall.json"),
            "m27x": str(root / "m27x_scorer_proxy_gap.json"),
        },
        "cases": cases,
        "old_regression_unresolved_count_after_repair": unresolved_count,
        "fallback_chain_recall_tradeoff_count": sum(1 for case in cases if case.get("fallback_selection_class") == "fallback_chain_recall_tradeoff"),
        "repair_policy_or_no_tool_coercion_count": sum(1 for case in cases if case.get("fallback_selection_class") == "repair_policy_or_no_tool_coercion"),
        "unsafe_fallback_unblocked_count": unsafe_unblocked,
        "block_all_would_break_m27m_readiness": block_all_breaks_any,
        "m2_7m_guidance_only_readiness_passed": m27m_passed,
        "plan_activated_count_after_guard": activated,
        "dominant_selected_next_tool_rate_after_guard": dominant,
        "fixed_case_blocked_count": fixed_blocked,
        "m27ad_fallback_selection_passed": passed,
        "diagnostic": {
            "offline_only": True,
            "does_not_run_bfcl": True,
            "allows_residual_only_when_recall_tradeoff_or_repair_policy": True,
            "does_not_authorize_holdout_or_100_case": True,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7ad Fallback Selection",
        "",
        f"- Passed: `{report['m27ad_fallback_selection_passed']}`",
        f"- Old unresolved after repair: `{report['old_regression_unresolved_count_after_repair']}`",
        f"- Fallback recall tradeoffs: `{report['fallback_chain_recall_tradeoff_count']}`",
        f"- Unsafe fallback unblocked: `{report['unsafe_fallback_unblocked_count']}`",
        f"- Activation after guard: `{report['plan_activated_count_after_guard']}`",
        "",
        "## Cases",
    ]
    for case in report.get("cases", []):
        selected = case.get("next_fallback_selected") or {}
        lines.append(
            f"- `{case['case_id']}`: class=`{case['fallback_selection_class']}`, action=`{case['fallback_selection_action']}`, "
            f"selected=`{selected.get('tool')}` args=`{selected.get('args')}`"
        )
        lines.append(f"  - reason: {case['fallback_selection_reason']}")
    lines.extend(["", "This is an offline diagnostic only. It does not call BFCL or prove performance.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.root)
    _write_json(args.output, report)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        keys = [
            "m27ad_fallback_selection_passed",
            "old_regression_unresolved_count_after_repair",
            "fallback_chain_recall_tradeoff_count",
            "unsafe_fallback_unblocked_count",
            "block_all_would_break_m27m_readiness",
            "m2_7m_guidance_only_readiness_passed",
            "plan_activated_count_after_guard",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    return 0 if report["m27ad_fallback_selection_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
