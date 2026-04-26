#!/usr/bin/env python3
"""Diagnose whether M2.7aa regression patterns are effective in current replay."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
OUT = DEFAULT_ROOT / "m27ab_unresolved_regression_repair.json"
MD = DEFAULT_ROOT / "m27ab_unresolved_regression_repair.md"
DEFAULT_CASES = ["multi_turn_miss_param_9", "multi_turn_miss_param_35", "multi_turn_miss_param_39"]


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


def _candidate_brief(candidate: Any) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None
    return {
        "tool": candidate.get("tool"),
        "args": candidate.get("args") or {},
        "binding_source": candidate.get("binding_source"),
        "intervention_mode": candidate.get("intervention_mode"),
        "scorer_feedback_pattern_matched": bool(candidate.get("scorer_feedback_pattern_matched")),
        "matched_regression_guard_key": candidate.get("matched_regression_guard_key"),
        "scorer_feedback_pattern_action": candidate.get("scorer_feedback_pattern_action"),
        "scorer_feedback_action": candidate.get("scorer_feedback_action"),
        "scorer_feedback_reason": candidate.get("scorer_feedback_reason"),
        "scorer_feedback_fallback_guard_matched": bool(candidate.get("scorer_feedback_fallback_guard_matched")),
        "matched_fallback_guard_key": candidate.get("matched_fallback_guard_key"),
        "scorer_feedback_fallback_action": candidate.get("scorer_feedback_fallback_action"),
    }


def _rejected_feedback_hits(plan: dict[str, Any], guard_key: str | None) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for item in plan.get("rejected_action_candidates") or []:
        if not isinstance(item, dict):
            continue
        matched_key = item.get("matched_regression_guard_key")
        pattern_matched = bool(item.get("scorer_feedback_pattern_matched"))
        if pattern_matched or (guard_key and matched_key == guard_key):
            hits.append(item)
    return hits


def _is_record_only_rejection(item: dict[str, Any]) -> bool:
    guard = item.get("guard") if isinstance(item.get("guard"), dict) else {}
    flags = guard.get("risk_flags") if isinstance(guard.get("risk_flags"), list) else []
    return (
        guard.get("intervention_mode") == "record_only"
        or item.get("scorer_feedback_action") == "record_only"
        or item.get("scorer_feedback_pattern_action") == "record_only"
        or item.get("scorer_feedback_fallback_action") == "record_only"
        or "scorer_feedback_record_only" in flags
        or "scorer_feedback_fallback_record_only" in flags
    )


def _case_plan_maps(root: Path) -> dict[str, dict[str, Any]]:
    preflight = _j(root / "m27i_guard_preflight.json", {}) or {}
    cases = preflight.get("cases") if isinstance(preflight.get("cases"), list) else []
    return {str(case.get("case_id")): case for case in cases if isinstance(case, dict) and case.get("case_id")}


def evaluate(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    aa = _j(root / "m27aa_regression_patterns.json", {}) or {}
    y = _j(root / "m27y_scorer_feedback.json", {}) or {}
    z = _j(root / "m27z_feedback_effect.json", {}) or {}
    plan_by_id = _case_plan_maps(root)
    aa_cases = {str(case.get("case_id")): case for case in (aa.get("cases") or []) if isinstance(case, dict) and case.get("case_id")}
    source_ids = list(aa.get("raw_old_regression_unresolved_case_ids") or aa.get("old_regression_unresolved_case_ids") or []) or DEFAULT_CASES
    source_ids = [str(item) for item in source_ids]

    cases: list[dict[str, Any]] = []
    effective_ids: list[str] = []
    ineffective_ids: list[str] = []
    for case_id in source_ids:
        aa_case = aa_cases.get(case_id, {})
        preflight_case = plan_by_id.get(case_id, {})
        plan = preflight_case.get("after_guard_plan") if isinstance(preflight_case.get("after_guard_plan"), dict) else {}
        selected = plan.get("selected_action_candidate") if isinstance(plan.get("selected_action_candidate"), dict) else None
        guard_key = aa_case.get("regression_guard_key")
        rejected_hits = _rejected_feedback_hits(plan, guard_key)
        selected_key = selected.get("matched_regression_guard_key") if isinstance(selected, dict) else None
        selected_pattern_matched = bool(selected and selected.get("scorer_feedback_pattern_matched"))
        selected_fallback_matched = bool(selected and selected.get("scorer_feedback_fallback_guard_matched"))
        fallback_hits = [item for item in rejected_hits if item.get("scorer_feedback_fallback_guard_matched")]
        effective = False
        outcome = "pattern_not_observed_in_replay"
        source_classification = "ambiguous_regression"
        reason = "No rejected current-replay candidate carried the regression pattern metadata."
        if selected and selected_fallback_matched:
            outcome = "post_feedback_fallback_candidate_still_selected"
            source_classification = "post_feedback_fallback_candidate"
            reason = "Fallback guard matched, but the candidate remained selected for hard guidance."
        elif selected and selected_pattern_matched and guard_key and selected_key != guard_key:
            outcome = "post_feedback_fallback_candidate"
            source_classification = "post_feedback_fallback_candidate"
            reason = "The original regression pattern was blocked or bypassed, but another scorer-feedback pattern candidate became hard guidance."
        elif rejected_hits and any(_is_record_only_rejection(item) for item in rejected_hits):
            effective = True
            if fallback_hits and any(_is_record_only_rejection(item) for item in fallback_hits):
                outcome = "post_feedback_fallback_record_only_rejection"
                source_classification = "post_feedback_fallback_candidate"
                reason = "Runtime fallback guard downgraded the post-feedback unsafe candidate before hard guidance."
            else:
                outcome = "pattern_record_only_rejection"
                source_classification = "action_pattern_effective"
                reason = "Runtime pattern guard matched and downgraded the unsafe candidate before hard guidance."
        elif selected and (selected_pattern_matched or (guard_key and selected_key == guard_key)):
            outcome = "pattern_matched_but_still_selected"
            source_classification = "action_pattern_not_effective"
            reason = "Regression pattern matched, but the candidate remained selected for hard guidance."
        elif selected is None and aa_case.get("selected_tool") in {None, "", "unknown"}:
            effective = True
            outcome = "no_proxy_candidate_absent_or_guard_rejected"
            source_classification = "repair_policy_or_no_tool_coercion"
            reason = "The unresolved scorer regression had no offline unsafe action candidate, and current replay does not select one."
        elif selected is None:
            outcome = "guard_rejected_without_pattern_metadata"
            source_classification = "ambiguous_regression"
            reason = "Current replay blocks the case, but not via an explicit scorer-feedback pattern match."
        elif selected:
            outcome = "unsafe_candidate_still_selected"
            source_classification = "ambiguous_regression"
            reason = "Current replay still selects an action candidate for an old regression case without pattern feedback metadata."

        if effective:
            effective_ids.append(case_id)
        else:
            ineffective_ids.append(case_id)
        cases.append(
            {
                "case_id": case_id,
                "regression_guard_key": guard_key,
                "policy_activation": bool(plan.get("activated")),
                "selected_candidate": _candidate_brief(selected),
                "feedback_pattern_match": bool(rejected_hits or selected_pattern_matched or (guard_key and selected_key == guard_key)),
                "matched_rejected_candidates": [
                    {
                        "tool": item.get("tool"),
                        "args": item.get("args") or {},
                        "guard_reason": (item.get("guard") or {}).get("reason") if isinstance(item.get("guard"), dict) else None,
                        "guard_intervention_mode": (item.get("guard") or {}).get("intervention_mode") if isinstance(item.get("guard"), dict) else None,
                        "matched_regression_guard_key": item.get("matched_regression_guard_key"),
                        "scorer_feedback_pattern_action": item.get("scorer_feedback_pattern_action"),
                        "scorer_feedback_reason": item.get("scorer_feedback_reason"),
                        "scorer_feedback_fallback_guard_matched": bool(item.get("scorer_feedback_fallback_guard_matched")),
                        "matched_fallback_guard_key": item.get("matched_fallback_guard_key"),
                        "scorer_feedback_fallback_action": item.get("scorer_feedback_fallback_action"),
                    }
                    for item in rejected_hits
                ],
                "guard_outcome": outcome,
                "regression_source_classification": source_classification,
                "repair_kinds": aa_case.get("repair_kinds") or [],
                "binding_source": aa_case.get("binding_source"),
                "selected_tool_family": aa_case.get("selected_tool"),
                "why_still_unresolved": None if effective else reason,
                "pattern_effective": effective,
                "previous_regression_status": {
                    "still_regressed_after_m27z": case_id in set(z.get("previous_regression_cases_still_regressed") or []),
                    "was_regression_feedback_case": case_id in set(y.get("regression_case_ids") or []),
                },
            }
        )

    total = len(source_ids)
    effective_coverage = (len(effective_ids) / total) if total else 1.0
    report = {
        "report_scope": "m2_7ab_unresolved_regression_repair",
        "artifact_root": str(root),
        "source_old_regression_case_ids": source_ids,
        "cases": cases,
        "pattern_effective_case_ids": effective_ids,
        "pattern_ineffective_case_ids": ineffective_ids,
        "old_regression_unresolved_case_ids_after_repair": ineffective_ids,
        "old_regression_unresolved_count_after_repair": len(ineffective_ids),
        "pattern_effective_coverage": effective_coverage,
        "m27ab_unresolved_regression_repair_passed": len(ineffective_ids) == 0 and effective_coverage == 1.0,
        "diagnostic": {
            "offline_only": True,
            "does_not_run_bfcl": True,
            "pattern_covered_is_not_enough_without_effective_replay_block": True,
            "does_not_authorize_holdout_or_100_case": True,
        },
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7ab Unresolved Regression Repair",
        "",
        f"- Passed: `{report['m27ab_unresolved_regression_repair_passed']}`",
        f"- Pattern effective coverage: `{report['pattern_effective_coverage']}`",
        f"- Unresolved after repair: `{report['old_regression_unresolved_count_after_repair']}`",
        "",
        "## Cases",
    ]
    for case in report.get("cases", []):
        lines.append(
            f"- `{case['case_id']}`: effective=`{case['pattern_effective']}`, outcome=`{case['guard_outcome']}`, "
            f"tool=`{(case.get('selected_candidate') or {}).get('tool')}`"
        )
        if case.get("why_still_unresolved"):
            lines.append(f"  - unresolved: {case['why_still_unresolved']}")
    lines.extend(["", "This is an offline replay diagnostic only. It does not call BFCL or prove performance.", ""])
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
        print(json.dumps({k: report.get(k) for k in ["m27ab_unresolved_regression_repair_passed", "pattern_effective_coverage", "old_regression_unresolved_count_after_repair", "pattern_ineffective_case_ids"]}, indent=2, sort_keys=True))
    return 0 if report["m27ab_unresolved_regression_repair_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
