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

from scripts.check_m27i_guard_preflight import DEFAULT_ARTIFACT_ROOT, evaluate_guard_preflight  # noqa: E402

DEFAULT_ROOT = DEFAULT_ARTIFACT_ROOT
OUT = DEFAULT_ROOT / "m27u_tool_ranking.json"
MD = DEFAULT_ROOT / "m27u_tool_ranking.md"


def _j(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _postcondition_goal(candidate: dict[str, Any]) -> str:
    postcondition = candidate.get("postcondition") if isinstance(candidate.get("postcondition"), dict) else {}
    return {
        "file_content": "read_content",
        "file_exists": "create_file",
        "directory_exists": "create_directory",
        "matches": "search",
        "target_path_changed": "move_or_copy",
        "content_written": "write_content",
        "comparison_result": "compare",
        "current_directory_changed": "directory_navigation",
    }.get(str(postcondition.get("kind") or ""), "unknown")


def _plan_scores(plan: dict[str, Any]) -> dict[str, Any]:
    scores = plan.get("selected_candidate_rank_scores")
    return scores if isinstance(scores, dict) else {}


def _guard(plan: dict[str, Any]) -> dict[str, Any]:
    guard = plan.get("action_candidate_guard")
    return guard if isinstance(guard, dict) else {}


def _selected_candidate(plan: dict[str, Any]) -> dict[str, Any]:
    candidate = plan.get("selected_action_candidate")
    return candidate if isinstance(candidate, dict) else {}


def _candidate_family_match(plan: dict[str, Any]) -> bool:
    if not plan.get("activated"):
        return False
    candidate = _selected_candidate(plan)
    scores = _plan_scores(plan)
    if not candidate:
        return False
    if scores.get("postcondition_goal_matches_request") is True:
        return True
    effective_goal = str(scores.get("effective_pending_goal_family") or candidate.get("pending_goal_family") or "unknown")
    postcondition_goal = str(scores.get("postcondition_goal_family") or _postcondition_goal(candidate))
    return effective_goal != "unknown" and effective_goal == postcondition_goal


def _is_tool_mismatch(plan: dict[str, Any]) -> bool:
    if not plan.get("activated"):
        return False
    guard = _guard(plan)
    risk_flags = {str(item) for item in guard.get("risk_flags") or []}
    blocking_flags = {
        "unknown_pending_goal_for_guidance",
        "pending_goal_postcondition_request_mismatch",
        "cat_request_goal_mismatch",
        "required_arg_pair_incomplete",
    }
    if risk_flags & blocking_flags:
        return True
    return not _candidate_family_match(plan)


def _best_rejected(plan: dict[str, Any]) -> dict[str, Any] | None:
    rejected = [row for row in plan.get("rejected_action_candidates") or [] if isinstance(row, dict)]
    if not rejected:
        return None
    return rejected[0]


def evaluate(root: Path = DEFAULT_ROOT, *, refresh_replay: bool = True) -> dict[str, Any]:
    replay = evaluate_guard_preflight(artifact_root=root) if refresh_replay else _j(root / "m27i_guard_preflight.json", {})
    cases: list[dict[str, Any]] = []
    active_plans: list[dict[str, Any]] = []
    distribution: Counter[str] = Counter()
    for row in replay.get("cases") or []:
        plan = row.get("after_guard_plan") if isinstance(row.get("after_guard_plan"), dict) else {}
        if not plan.get("activated"):
            continue
        active_plans.append(plan)
        selected_tool = str(plan.get("selected_tool") or "none")
        distribution[selected_tool] += 1
        candidate = _selected_candidate(plan)
        scores = _plan_scores(plan)
        guard = _guard(plan)
        mismatch = _is_tool_mismatch(plan)
        if mismatch:
            cases.append(
                {
                    "case_id": row.get("case_id"),
                    "pending_goal_source": scores.get("pending_goal_source"),
                    "request_pending_goal": scores.get("request_pending_goal_family"),
                    "candidate_pending_goal": scores.get("candidate_pending_goal_family") or candidate.get("pending_goal_family"),
                    "effective_pending_goal": scores.get("effective_pending_goal_family"),
                    "selected_tool": selected_tool,
                    "postcondition_goal": scores.get("postcondition_goal_family") or _postcondition_goal(candidate),
                    "selected_candidate": candidate,
                    "selected_candidate_score_components": scores,
                    "better_candidate_not_selected": _best_rejected(plan),
                    "guard_reason": guard.get("reason"),
                    "guard_risk_flags": guard.get("risk_flags") or [],
                    "why_selected_won": {
                        "rank_score": scores.get("score"),
                        "arg_binding_score": scores.get("arg_binding_score"),
                        "state_compatibility_score": scores.get("state_compatibility_score"),
                        "literal_score": scores.get("literal_score"),
                        "intent_score": scores.get("intent_score"),
                        "recommended_rank": scores.get("recommended_rank"),
                    },
                    "failure_reason": "tool_mismatch_before_arg_realization",
                }
            )
    activated = len(active_plans)
    mismatch_count = len(cases)
    match_proxy = (activated - mismatch_count) / activated if activated else 0.0
    dominant = max(distribution.values()) / sum(distribution.values()) if distribution else 0.0
    scorer_summary = _j(root / "subset_summary.json", {}) or {}
    postmortem = _j(root / "m27q_postmortem.json", {}) or {}
    report = {
        "report_scope": "m2_7u_tool_ranking",
        "artifact_root": str(root),
        "activated_case_count": activated,
        "selected_next_tool_distribution": dict(sorted(distribution.items())),
        "dominant_selected_next_tool_rate": dominant,
        "tool_mismatch_before_arg_realization_count": mismatch_count,
        "offline_recommended_tool_match_proxy": match_proxy,
        "cases": cases,
        "last_scorer_tool_match_rate": scorer_summary.get("recommended_tool_match_rate_among_activated"),
        "last_scorer_failure_layer_distribution": postmortem.get("failure_layer_distribution"),
        "m27u_tool_ranking_passed": mismatch_count <= 2 and match_proxy >= 0.7 and dominant <= 0.8,
        "diagnostic": {
            "offline_only": True,
            "readiness_source": "source_trace_replay_current_rules",
            "last_scorer_metrics_retained_for_postmortem_only": True,
        },
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# M2.7u Tool Ranking",
            "",
            f"- Passed: `{report['m27u_tool_ranking_passed']}`",
            f"- Activated cases: `{report['activated_case_count']}`",
            f"- Mismatches: `{report['tool_mismatch_before_arg_realization_count']}`",
            f"- Match proxy: `{report['offline_recommended_tool_match_proxy']}`",
            f"- Distribution: `{report['selected_next_tool_distribution']}`",
            f"- Dominant rate: `{report['dominant_selected_next_tool_rate']}`",
            "",
            "This is an offline source-trace replay proxy. Last scorer metrics are retained for postmortem only.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--no-refresh-replay", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.root, refresh_replay=not args.no_refresh_replay)
    _write_json(args.output, report)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({k: report.get(k) for k in ["tool_mismatch_before_arg_realization_count", "offline_recommended_tool_match_proxy", "dominant_selected_next_tool_rate", "m27u_tool_ranking_passed"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
