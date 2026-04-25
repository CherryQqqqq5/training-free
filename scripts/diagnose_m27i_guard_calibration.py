#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scripts.check_m27f_candidate_plan_diversity import DEFAULT_ARTIFACT_ROOT  # noqa: E402
from scripts.check_m27i_guard_preflight import render_markdown as render_preflight_markdown  # noqa: E402
from scripts.diagnose_m27i_regression_audit import evaluate_regression_audit  # noqa: E402


DEFAULT_PREFLIGHT = DEFAULT_ARTIFACT_ROOT / "m27i_guard_preflight.json"
DEFAULT_REGRESSION_AUDIT = DEFAULT_ARTIFACT_ROOT / "m27i_regression_audit.json"
DEFAULT_OUTPUT = DEFAULT_ARTIFACT_ROOT / "m27i_guard_calibration.json"
DEFAULT_MARKDOWN_OUTPUT = DEFAULT_ARTIFACT_ROOT / "m27i_guard_calibration.md"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_regression(path: Path, artifact_root: Path) -> dict[str, Any]:
    payload = _read_json(path)
    if payload:
        return payload
    return evaluate_regression_audit(artifact_root)


def _case_kind(case_id: str, fixed: set[str], regressed: set[str]) -> str:
    if case_id in fixed:
        return "fixed"
    if case_id in regressed:
        return "regressed"
    return "other"


def _rejected_candidates(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in plan.get("rejected_action_candidates") or [] if isinstance(row, dict)]


def _guard_reason(row: dict[str, Any]) -> str | None:
    guard = row.get("guard") if isinstance(row.get("guard"), dict) else {}
    reason = guard.get("reason")
    return str(reason) if reason else None


def _accepted_guard_reason(plan: dict[str, Any]) -> str | None:
    guard = plan.get("action_candidate_guard") if isinstance(plan.get("action_candidate_guard"), dict) else {}
    reason = guard.get("reason")
    return str(reason) if reason else None


def _case_final_guard_reason(case: dict[str, Any]) -> str | None:
    after = case.get("after_guard_plan") or {}
    if after.get("activated"):
        return _accepted_guard_reason(after)
    rejected = _rejected_candidates(after)
    if rejected:
        return _guard_reason(rejected[0])
    reason = after.get("blocked_reason")
    return str(reason) if reason else None


def _case_record(case: dict[str, Any], *, fixed: set[str], regressed: set[str]) -> dict[str, Any]:
    before = case.get("before_guard_plan") or {}
    after = case.get("after_guard_plan") or {}
    rejected = _rejected_candidates(after)
    all_reasons = [reason for reason in (_guard_reason(row) for row in rejected) if reason]
    top_rejected = rejected[0] if rejected else None
    accepted = after.get("selected_action_candidate") if isinstance(after.get("selected_action_candidate"), dict) else None
    return {
        "case_id": case.get("case_id"),
        "case_kind": _case_kind(str(case.get("case_id") or ""), fixed, regressed),
        "guard_status": case.get("guard_status"),
        "request_state_source": case.get("request_state_source"),
        "source_trace_id": case.get("source_trace_id"),
        "before_tool": before.get("selected_tool"),
        "after_tool": after.get("selected_tool"),
        "before_candidate": before.get("selected_action_candidate"),
        "accepted_candidate_by_case": accepted,
        "top_rejected_candidate_by_case": top_rejected,
        "case_level_guard_reason": _case_final_guard_reason(case),
        "top_candidate_rejection_reason": _guard_reason(top_rejected or {}),
        "all_candidate_rejection_reasons": all_reasons,
        "score_components_by_case": {
            "before_selected": before.get("selected_candidate_rank_scores"),
            "accepted": after.get("selected_candidate_rank_scores"),
            "top_rejected": (top_rejected or {}).get("candidate_rank_scores"),
        },
    }


def _recommendations(report: dict[str, Any], false_negative: list[str], false_positive: list[str]) -> list[str]:
    recommendations: list[str] = []
    after_count = int(report.get("plan_activated_count_after_guard") or 0)
    dominant = float(report.get("dominant_selected_next_tool_rate_after_guard") or 0.0)
    if after_count < 10:
        recommendations.append("increase_guard_recall_without_reenabling_weak_cwd_or_listing")
    if after_count > 20:
        recommendations.append("tighten_guard_to_reduce_over_activation")
    if false_negative:
        recommendations.append("recover_fixed_case_evidence_extraction")
    if false_positive:
        recommendations.append("tighten_regressed_case_acceptance")
    if dominant > 0.8:
        recommendations.append("improve_tool_distribution_or_reduce_dominant_tool")
    if not recommendations:
        recommendations.append("guard_preflight_ready")
    return recommendations


def evaluate_guard_calibration(
    preflight_path: Path = DEFAULT_PREFLIGHT,
    *,
    regression_audit_path: Path = DEFAULT_REGRESSION_AUDIT,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
) -> dict[str, Any]:
    preflight = _read_json(preflight_path)
    regression = _load_regression(regression_audit_path, artifact_root)
    fixed = {str(case_id) for case_id in regression.get("fixed_cases") or preflight.get("fixed_cases_guard_status") or []}
    regressed = {str(case_id) for case_id in regression.get("regressed_cases") or preflight.get("regressed_cases_guard_status") or []}
    cases = [_case_record(case, fixed=fixed, regressed=regressed) for case in preflight.get("cases") or []]
    by_id = {str(case.get("case_id")): case for case in cases}
    fixed_false_negative = [case_id for case_id in sorted(fixed) if by_id.get(case_id, {}).get("guard_status") == "guard_rejected"]
    regressed_false_positive = [
        case_id
        for case_id in sorted(regressed)
        if by_id.get(case_id, {}).get("guard_status") in {"guard_kept", "guard_changed_tool"}
    ]
    case_reason = {str(case.get("case_id")): case.get("case_level_guard_reason") for case in cases if case.get("case_id")}
    top_reason_counts = Counter(case.get("top_candidate_rejection_reason") for case in cases if case.get("top_candidate_rejection_reason"))
    final_reason_counts = Counter(case.get("case_level_guard_reason") for case in cases if case.get("case_level_guard_reason"))
    return {
        "preflight_path": str(preflight_path),
        "regression_audit_path": str(regression_audit_path),
        "artifact_root": str(artifact_root),
        "m2_7i_guard_preflight_passed": bool(preflight.get("m2_7i_guard_preflight_passed")),
        "plan_activated_count_after_guard": preflight.get("plan_activated_count_after_guard"),
        "selected_next_tool_distribution_after_guard": preflight.get("selected_next_tool_distribution_after_guard"),
        "fixed_cases_guard_false_negative": fixed_false_negative,
        "regressed_cases_guard_false_positive": regressed_false_positive,
        "case_level_guard_reason": case_reason,
        "case_level_guard_reason_distribution": dict(final_reason_counts),
        "top_candidate_rejection_reason_distribution": dict(top_reason_counts),
        "top_rejected_candidate_by_case": {
            str(case.get("case_id")): case.get("top_rejected_candidate_by_case") for case in cases if case.get("top_rejected_candidate_by_case")
        },
        "accepted_candidate_by_case": {
            str(case.get("case_id")): case.get("accepted_candidate_by_case") for case in cases if case.get("accepted_candidate_by_case")
        },
        "score_components_by_case": {
            str(case.get("case_id")): case.get("score_components_by_case") for case in cases if case.get("case_id")
        },
        "cases": cases,
        "calibration_recommendation": _recommendations(preflight, fixed_false_negative, regressed_false_positive),
        "diagnostic": {
            "checker_scope": "m2_7j_guard_calibration_no_upstream_model_call",
            "source_preflight_first_failed": (preflight.get("diagnostic") or {}).get("first_failed_criterion"),
            "preflight_markdown_renderer": render_preflight_markdown.__name__,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7j Guard Calibration",
        "",
        f"- Source preflight passed: `{report.get('m2_7i_guard_preflight_passed')}`",
        f"- After guard activations: `{report.get('plan_activated_count_after_guard')}`",
        f"- Fixed false negatives: `{report.get('fixed_cases_guard_false_negative')}`",
        f"- Regressed false positives: `{report.get('regressed_cases_guard_false_positive')}`",
        f"- Case-level reasons: `{report.get('case_level_guard_reason_distribution')}`",
        f"- Top rejected reasons: `{report.get('top_candidate_rejection_reason_distribution')}`",
        f"- Recommendations: `{report.get('calibration_recommendation')}`",
        "",
        "## Changed Cases",
        "",
        "| Case | Kind | Status | Before | After | Case Reason | Top Rejected Reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case in report.get("cases") or []:
        if case.get("case_kind") == "other":
            continue
        lines.append(
            "| {case_id} | {kind} | {status} | {before} | {after} | {reason} | {top} |".format(
                case_id=case.get("case_id"),
                kind=case.get("case_kind"),
                status=case.get("guard_status"),
                before=case.get("before_tool"),
                after=case.get("after_tool"),
                reason=case.get("case_level_guard_reason"),
                top=case.get("top_candidate_rejection_reason"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose M2.7j guard calibration false positives/negatives without BFCL/model calls.")
    parser.add_argument("--preflight", type=Path, default=DEFAULT_PREFLIGHT)
    parser.add_argument("--regression-audit", type=Path, default=DEFAULT_REGRESSION_AUDIT)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_guard_calibration(
        args.preflight,
        regression_audit_path=args.regression_audit,
        artifact_root=args.artifact_root,
    )
    text = json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
