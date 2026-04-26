#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_HOLDOUT = Path("outputs/artifacts/bfcl_ctspc_holdout30_v1")
OUT = DEFAULT_ROOT / "m27w_rule_retention.json"
MD = DEFAULT_ROOT / "m27w_rule_retention.md"


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
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _holdout_ready(holdout_root: Path) -> bool:
    holdout = _j(holdout_root / "holdout_manifest.json", {}) or {}
    selected = int(holdout.get("selected_case_count") or 0)
    generatable = int(holdout.get("candidate_generatable_count") or 0)
    overlap = holdout.get("overlap_with_dev_case_ids") or []
    return bool(holdout.get("m27tw_holdout_manifest_ready")) and selected >= 20 and generatable >= 15 and not overlap


def decide(rule: dict[str, Any], holdout_ready: bool, offline_ready: bool = False, *, dev_scorer_net_case_gain: int | None = None) -> tuple[str, str, dict[str, Any]]:
    net = int(rule.get("net_case_gain") or 0)
    regressed = int(rule.get("regressed_count") or 0)
    fixed = int(rule.get("fixed_count") or 0)
    tool = float(rule.get("tool_match_rate") or 0.0)
    arg = float(rule.get("arg_match_rate") or 0.0)
    trajectory_fail = int(rule.get("trajectory_fail_count") or 0)
    blockers: list[str] = []
    if regressed > 0:
        blockers.append("has_regression")
    if net < 0:
        blockers.append("negative_dev_net_gain")
    if tool < 0.6:
        blockers.append("dev_tool_match_below_floor")
    if arg < 0.6:
        blockers.append("dev_arg_match_below_floor")
    if trajectory_fail > max(fixed, 0):
        blockers.append("trajectory_fail_exceeds_fixed")
    if not holdout_ready:
        blockers.append("holdout_manifest_not_ready")
    if not offline_ready:
        blockers.append("offline_u_v_readiness_not_passed")
    if dev_scorer_net_case_gain is not None and dev_scorer_net_case_gain < 0:
        blockers.append("negative_overall_dev_scorer_net_gain")

    positive_zero_regression = net > 0 and regressed == 0 and fixed > 0 and tool >= 0.6 and arg >= 0.6 and trajectory_fail <= fixed
    if positive_zero_regression and holdout_ready and offline_ready:
        return "demote", "dev_positive_holdout_scorer_required_before_retain", {"retain_blocked_by": "missing_holdout_scorer_evidence", "blockers": blockers}
    return "reject", "no_positive_retention_signal", {"retain_blocked_by": "missing_positive_dev_and_holdout_evidence", "blockers": blockers}


def _regression_cases(root: Path) -> list[dict[str, Any]]:
    postmortem = _j(root / "m27q_postmortem.json", {}) or {}
    cases = postmortem.get("cases") if isinstance(postmortem.get("cases"), list) else []
    if cases:
        source = cases
    else:
        source = _jl(root / "subset_case_report.jsonl")
    out = []
    for row in source:
        if not row.get("case_regressed"):
            continue
        out.append(
            {
                "case_id": row.get("case_id"),
                "policy_plan_activated": row.get("policy_plan_activated"),
                "selected_tool": row.get("selected_next_tool"),
                "emitted_tool": row.get("emitted_tool"),
                "tool_match": row.get("recommended_tool_match"),
                "raw_arg_match": row.get("raw_normalized_arg_match"),
                "final_arg_match": row.get("final_normalized_arg_match"),
                "repair_kinds": row.get("repair_kinds") or [],
                "rule_id": row.get("rule_id"),
                "selected_action_candidate": row.get("selected_action_candidate") or {},
                "failure_mechanism": row.get("primary_failure_layer") or "regression",
                "candidate_policy_action": "reject_or_record_only_until_gap_fixed",
            }
        )
    return out


def evaluate(root: Path = DEFAULT_ROOT, holdout_root: Path = DEFAULT_HOLDOUT) -> dict[str, Any]:
    base = _j(root / "m27r_rule_retention.json", {}) or _j(root / "m27f_rule_level_report.json", {}) or {}
    u = _j(root / "m27u_tool_ranking.json", {}) or {}
    v = _j(root / "m27v_arg_realization.json", {}) or {}
    summary = _j(root / "subset_summary.json", {}) or {}
    feedback = _j(root / "m27y_scorer_feedback.json", {}) or {}
    holdout_manifest_ready = _holdout_ready(holdout_root)
    offline_ready = bool(u.get("m27u_tool_ranking_passed") and v.get("m27v_arg_realization_passed"))
    dev_scorer_net = summary.get("net_case_gain") if isinstance(summary.get("net_case_gain"), int) else None
    feedback_ready = bool(feedback.get("m27y_scorer_feedback_ready") and feedback.get("fixed_by_code_change"))
    rules: list[dict[str, Any]] = []
    distribution: Counter[str] = Counter()
    for rule in base.get("rules") or []:
        decision, reason, extra = decide(rule, holdout_manifest_ready, offline_ready, dev_scorer_net_case_gain=dev_scorer_net)
        item = {
            **rule,
            "decision": decision,
            "reason": reason,
            "dev_only_signal": bool(int(rule.get("activation_count") or 0) > 0),
            "holdout_manifest_ready": holdout_manifest_ready,
            "holdout_required_for_retain": True,
            "holdout_scorer_evidence_available": False,
            "dev_scorer_net_case_gain": dev_scorer_net,
            "decision_blocker": extra,
        }
        rules.append(item)
        distribution[decision] += 1
    demote_or_retain = distribution.get("demote", 0) + distribution.get("retain", 0)
    regressions = _regression_cases(root)
    feedback_case_ids = {str(item) for item in feedback.get("blocked_case_ids") or []}
    regression_ids = {str(case.get("case_id")) for case in regressions}
    scorer_feedback_covers_regressions = bool(regression_ids) and regression_ids.issubset(feedback_case_ids)
    report = {
        "report_scope": "m2_7w_rule_retention",
        "artifact_root": str(root),
        "holdout_root": str(holdout_root),
        "holdout_manifest_ready": holdout_manifest_ready,
        "holdout_scorer_evidence_available": False,
        "offline_u_v_readiness_passed": offline_ready,
        "dev_scorer_net_case_gain": dev_scorer_net,
        "scorer_override_applied": dev_scorer_net is not None,
        "rule_count": len(rules),
        "rules": rules,
        "regression_cases": regressions,
        "regression_case_count": len(regressions),
        "decision_distribution": {key: distribution.get(key, 0) for key in ["retain", "demote", "reject"]},
        "m27y_scorer_feedback_ready": feedback_ready,
        "scorer_feedback_covers_regressions": scorer_feedback_covers_regressions,
        "m27w_rule_retention_passed": (demote_or_retain >= 1 and holdout_manifest_ready and offline_ready) or (holdout_manifest_ready and offline_ready and feedback_ready and scorer_feedback_covers_regressions and distribution.get("retain", 0) == 0),
        "diagnostic": {
            "dev_only_cannot_promote_to_retained_memory": True,
            "retain_requires_future_holdout_scorer_evidence": True,
            "negative_dev_scorer_blocks_retain": bool(dev_scorer_net is not None and dev_scorer_net < 0),
            "regression_candidates_rejected_or_record_only_until_gap_fixed": feedback_ready and scorer_feedback_covers_regressions,
            "offline_readiness_only": True,
        },
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# M2.7w Rule Retention",
            "",
            f"- Passed: `{report['m27w_rule_retention_passed']}`",
            f"- Holdout manifest ready: `{report['holdout_manifest_ready']}`",
            f"- Offline U/V readiness: `{report['offline_u_v_readiness_passed']}`",
            f"- Dev scorer net case gain: `{report['dev_scorer_net_case_gain']}`",
            f"- Decisions: `{report['decision_distribution']}`",
            f"- Regression cases: `{report['regression_case_count']}`",
            "",
            "Retain remains blocked until holdout scorer evidence exists; negative dev scorer evidence forces regression-causing candidates to reject or record-only.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--holdout-root", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.root, args.holdout_root)
    _write_json(args.output, report)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({k: report.get(k) for k in ["holdout_manifest_ready", "offline_u_v_readiness_passed", "dev_scorer_net_case_gain", "decision_distribution", "regression_case_count", "m27y_scorer_feedback_ready", "scorer_feedback_covers_regressions", "m27w_rule_retention_passed"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

