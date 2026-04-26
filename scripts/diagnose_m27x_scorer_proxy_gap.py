#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
OUT = DEFAULT_ROOT / "m27x_scorer_proxy_gap.json"
MD = DEFAULT_ROOT / "m27x_scorer_proxy_gap.md"
BLOCKING_GAP_TYPES = {"proxy_tool_ok_scorer_tool_wrong", "proxy_arg_ok_scorer_arg_wrong", "proxy_ok_trajectory_failed", "proxy_activated_but_scorer_not_activated", "proxy_not_activated_but_scorer_activated"}


def _j(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _jl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _case_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("case_id")): row for row in rows if row.get("case_id")}


def _gap_type(row: dict[str, Any], offline: dict[str, Any] | None) -> str:
    proxy_activated = offline is not None
    scorer_activated = bool(row.get("policy_plan_activated"))
    proxy_tool_ok = bool(offline and offline.get("proxy_tool_match", True))
    proxy_arg_ok = bool(offline and offline.get("arg_realization_proxy_ready"))
    scorer_tool_ok = bool(row.get("recommended_tool_match"))
    scorer_arg_ok = bool(row.get("raw_normalized_arg_match"))
    candidate_success = bool(row.get("candidate_success"))

    if proxy_activated and not scorer_activated:
        return "proxy_activated_but_scorer_not_activated"
    if not proxy_activated and scorer_activated:
        return "proxy_not_activated_but_scorer_activated"
    if proxy_tool_ok and not scorer_tool_ok:
        return "proxy_tool_ok_scorer_tool_wrong"
    if proxy_arg_ok and not scorer_arg_ok:
        return "proxy_arg_ok_scorer_arg_wrong"
    if proxy_tool_ok and proxy_arg_ok and scorer_tool_ok and scorer_arg_ok and not candidate_success:
        return "proxy_ok_trajectory_failed"
    return "no_proxy_gap"


def evaluate(root: Path = DEFAULT_ROOT, *, fixed_by_code_change: bool = False) -> dict[str, Any]:
    summary = _j(root / "subset_summary.json", {}) or {}
    postmortem = _j(root / "m27q_postmortem.json", {}) or {}
    offline = _j(root / "m27tw_offline_summary.json", {}) or {}
    feedback = _j(root / "m27y_scorer_feedback.json", {}) or {}
    feedback_case_ids = {str(item) for item in feedback.get("blocked_case_ids") or []}
    u = _j(root / "m27u_tool_ranking.json", {}) or {}
    v = _j(root / "m27v_arg_realization.json", {}) or {}
    rows = _jl(root / "subset_case_report.jsonl")

    u_cases = _case_map(u.get("cases") or [])
    v_cases = _case_map(v.get("cases") or [])
    cases: list[dict[str, Any]] = []
    distribution: Counter[str] = Counter()
    for row in rows:
        case_id = str(row.get("case_id") or "")
        v_case = v_cases.get(case_id)
        u_case = u_cases.get(case_id)
        offline_case = None
        if v_case or u_case:
            offline_case = {
                "offline_selected_tool": (v_case or {}).get("selected_tool") or (u_case or {}).get("selected_tool"),
                "offline_candidate_args": (v_case or {}).get("candidate_arg_json"),
                "offline_arg_match_proxy": (v_case or {}).get("arg_realization_proxy_ready"),
                "proxy_tool_match": False if u_case else True,
                "arg_realization_proxy_ready": (v_case or {}).get("arg_realization_proxy_ready"),
            }
        gap = _gap_type(row, offline_case)
        distribution[gap] += 1
        feedback_applied = case_id in feedback_case_ids
        cases.append(
            {
                "case_id": case_id,
                "offline_selected_tool": (offline_case or {}).get("offline_selected_tool"),
                "scorer_selected_tool": row.get("selected_next_tool"),
                "offline_candidate_args": (offline_case or {}).get("offline_candidate_args"),
                "scorer_emitted_args": None,
                "emitted_args_available": False,
                "offline_arg_match_proxy": (offline_case or {}).get("offline_arg_match_proxy"),
                "real_raw_arg_match": row.get("raw_normalized_arg_match"),
                "offline_tool_match_proxy": (offline_case or {}).get("proxy_tool_match"),
                "real_tool_match": row.get("recommended_tool_match"),
                "baseline_success": row.get("baseline_success"),
                "candidate_success": row.get("candidate_success"),
                "case_fixed": row.get("case_fixed"),
                "case_regressed": row.get("case_regressed"),
                "proxy_activated": offline_case is not None,
                "scorer_activated": row.get("policy_plan_activated"),
                "repair_kinds": row.get("repair_kinds") or [],
                "gap_type": gap,
                "scorer_feedback_applied": feedback_applied,
                "feedback_action": "record_only" if feedback_applied else None,
            }
        )

    regressed = [case for case in cases if case.get("case_regressed")]
    explained_gap_types = BLOCKING_GAP_TYPES
    gap_count = sum(count for key, count in distribution.items() if key in explained_gap_types)
    gap_case_ids = {case["case_id"] for case in cases if case.get("gap_type") in explained_gap_types}
    regression_case_ids = {case["case_id"] for case in cases if case.get("case_regressed")}
    feedback_ready = bool(feedback.get("m27y_scorer_feedback_ready"))
    feedback_covers_gap = bool(gap_case_ids) and gap_case_ids.issubset(feedback_case_ids)
    feedback_covers_regressions = regression_case_ids.issubset(feedback_case_ids)
    effective_fixed_by_code_change = bool(fixed_by_code_change or (feedback_ready and feedback_covers_gap and feedback_covers_regressions and feedback.get("fixed_by_code_change")))
    report = {
        "report_scope": "m2_7x_scorer_proxy_gap",
        "artifact_root": str(root),
        "baseline_accuracy": summary.get("baseline_accuracy"),
        "candidate_accuracy": summary.get("candidate_accuracy"),
        "net_case_gain": summary.get("net_case_gain"),
        "case_report_trace_mapping": summary.get("case_report_trace_mapping"),
        "case_level_gate_allowed": summary.get("case_level_gate_allowed"),
        "offline_tool_match_proxy": (offline.get("tool_ranking") or {}).get("offline_recommended_tool_match_proxy"),
        "offline_arg_match_proxy": (offline.get("arg_realization") or {}).get("raw_arg_match_rate_proxy"),
        "last_scorer_tool_match_rate": summary.get("recommended_tool_match_rate_among_activated"),
        "last_scorer_raw_arg_match_rate": summary.get("raw_normalized_arg_match_rate_among_activated"),
        "gap_type_distribution": dict(sorted(distribution.items())),
        "gap_case_count": gap_count,
        "regressed_case_count": len(regressed),
        "regression_cases": regressed,
        "cases": cases,
        "m27x_scorer_proxy_gap_explained": gap_count > 0,
        "fixed_by_code_change": effective_fixed_by_code_change,
        "m27y_scorer_feedback_ready": feedback_ready,
        "scorer_feedback_case_count": len(feedback_case_ids),
        "scorer_feedback_covers_gap_cases": feedback_covers_gap,
        "scorer_feedback_covers_regression_cases": feedback_covers_regressions,
        "scorer_feedback_code_fix_id": feedback.get("code_fix_id"),
        "m27x_scorer_proxy_gap_passed": gap_count > 0 and effective_fixed_by_code_change,
        "diagnostic": {
            "offline_proxy_is_not_scorer_evidence": True,
            "emitted_args_unavailable_from_case_report": True,
            "postmortem_recommended_next_focus": postmortem.get("recommended_next_focus"),
            "do_not_rerun_bfcl_until_gap_has_code_fix": not effective_fixed_by_code_change,
        },
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7x Scorer-Proxy Gap",
        "",
        f"- Gap explained: `{report['m27x_scorer_proxy_gap_explained']}`",
        f"- Fixed by code change: `{report['fixed_by_code_change']}`",
        f"- Passed: `{report['m27x_scorer_proxy_gap_passed']}`",
        f"- Baseline/Candidate accuracy: `{report['baseline_accuracy']}` / `{report['candidate_accuracy']}`",
        f"- Net case gain: `{report['net_case_gain']}`",
        f"- Gap distribution: `{report['gap_type_distribution']}`",
        f"- Regressed cases: `{report['regressed_case_count']}`",
        "",
        "This is an offline diagnostic. It explains why source-trace proxy readiness did not become scorer gain; it does not authorize rerun.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--fixed-by-code-change", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.root, fixed_by_code_change=args.fixed_by_code_change)
    _write_json(args.output, report)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({k: report.get(k) for k in ["m27x_scorer_proxy_gap_explained", "fixed_by_code_change", "m27x_scorer_proxy_gap_passed", "gap_type_distribution", "regressed_case_count"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

