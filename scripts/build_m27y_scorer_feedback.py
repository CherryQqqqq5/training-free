#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
OUT = DEFAULT_ROOT / "m27y_scorer_feedback.json"
MD = DEFAULT_ROOT / "m27y_scorer_feedback.md"
BLOCKING_GAP_TYPES = {
    "proxy_tool_ok_scorer_tool_wrong",
    "proxy_arg_ok_scorer_arg_wrong",
    "proxy_ok_trajectory_failed",
    "proxy_activated_but_scorer_not_activated",
    "proxy_not_activated_but_scorer_activated",
}


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


def build_feedback(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    gap = _j(root / "m27x_scorer_proxy_gap.json", {}) or {}
    aa = _j(root / "m27aa_regression_patterns.json", {}) or {}
    summary = _j(root / "subset_summary.json", {}) or {}
    cases = gap.get("cases") if isinstance(gap.get("cases"), list) else []
    feedback_cases: list[dict[str, Any]] = []
    blocked_signatures: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    for case in cases:
        case_id = str(case.get("case_id") or "")
        gap_type = str(case.get("gap_type") or "")
        is_regression = bool(case.get("case_regressed"))
        if gap_type not in BLOCKING_GAP_TYPES and not is_regression:
            continue
        runtime_blocked = is_regression
        if is_regression:
            reason = "scorer_regression"
        elif gap_type == "proxy_tool_ok_scorer_tool_wrong":
            reason = "scorer_tool_mismatch_after_guidance"
        elif gap_type == "proxy_arg_ok_scorer_arg_wrong":
            reason = "scorer_arg_mismatch_after_guidance"
        elif gap_type == "proxy_ok_trajectory_failed":
            reason = "local_tool_arg_match_but_trajectory_failed"
        else:
            reason = gap_type
        reasons[reason] += 1
        offline_tool = case.get("offline_selected_tool")
        offline_args = case.get("offline_candidate_args")
        if runtime_blocked and isinstance(offline_tool, str) and offline_tool.strip() and isinstance(offline_args, dict):
            signature = {"tool": offline_tool.strip(), "args": offline_args}
            if signature not in blocked_signatures:
                blocked_signatures.append(signature)
        feedback_cases.append(
            {
                "case_id": case_id,
                "selected_tool": case.get("scorer_selected_tool"),
                "offline_selected_tool": case.get("offline_selected_tool"),
                "gap_type": gap_type,
                "case_regressed": is_regression,
                "feedback_action": "record_only" if runtime_blocked else "diagnostic_only",
                "intervention_mode_override": "record_only" if runtime_blocked else None,
                "runtime_blocked": runtime_blocked,
                "reason": reason,
                "candidate_policy_action": "reject_or_record_only_until_scorer_gap_fixed",
            }
        )
    regression_case_ids = sorted({str(case.get("case_id")) for case in cases if case.get("case_regressed")})
    covered_case_ids = sorted({case["case_id"] for case in feedback_cases})
    missing_regression_coverage = sorted(set(regression_case_ids) - set(covered_case_ids))
    report = {
        "report_scope": "m2_7y_scorer_feedback",
        "artifact_root": str(root),
        "code_fix_id": "m27y_scorer_feedback_overlay_v1",
        "fixed_by_code_change": True,
        "feedback_application": "downgrade_regression_candidates_to_record_only_and_keep_non_regression_gaps_diagnostic",
        "source_gap_report": str(root / "m27x_scorer_proxy_gap.json"),
        "baseline_accuracy": summary.get("baseline_accuracy"),
        "candidate_accuracy": summary.get("candidate_accuracy"),
        "net_case_gain": summary.get("net_case_gain"),
        "blocking_gap_types": sorted(BLOCKING_GAP_TYPES),
        "feedback_case_count": len(feedback_cases),
        "feedback_cases": feedback_cases,
        "blocked_candidate_signatures": blocked_signatures,
        "blocked_regression_patterns": aa.get("blocked_regression_patterns") or [],
        "scorer_feedback_covers_regression_patterns": bool(aa.get("scorer_feedback_covers_regression_patterns")),
        "m27aa_regression_patterns_passed": bool(aa.get("m27aa_regression_patterns_passed")),
        "pattern_source_report": str(root / "m27aa_regression_patterns.json") if (root / "m27aa_regression_patterns.json").exists() else None,
        "feedback_reason_distribution": dict(sorted(reasons.items())),
        "blocked_case_ids": covered_case_ids,
        "regression_case_ids": regression_case_ids,
        "missing_regression_coverage": missing_regression_coverage,
        "m27y_scorer_feedback_ready": bool(feedback_cases) and not missing_regression_coverage,
        "diagnostic": {
            "offline_only": True,
            "does_not_change_bfcl_results": True,
            "does_not_authorize_holdout_or_100_case": True,
        },
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# M2.7y Scorer Feedback",
            "",
            f"- Ready: `{report['m27y_scorer_feedback_ready']}`",
            f"- Feedback cases: `{report['feedback_case_count']}`",
            f"- Runtime-blocked signatures: `{len(report.get('blocked_candidate_signatures') or [])}`",
            f"- Regression cases covered: `{not report['missing_regression_coverage']}`",
            f"- Reason distribution: `{report['feedback_reason_distribution']}`",
            "",
            "This is an offline scorer-feedback overlay. It downgrades regression-causing candidates to record-only and keeps non-regression scorer gaps diagnostic-only; it does not rerun BFCL or prove performance.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = build_feedback(args.root)
    _write_json(args.output, report)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({k: report.get(k) for k in ["m27y_scorer_feedback_ready", "fixed_by_code_change", "feedback_case_count", "feedback_reason_distribution", "missing_regression_coverage"]}, indent=2, sort_keys=True))
    return 0 if report["m27y_scorer_feedback_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

