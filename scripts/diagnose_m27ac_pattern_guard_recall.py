#!/usr/bin/env python3
"""Diagnose recall collateral from M2.7aa scorer-feedback patterns."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
OUT = DEFAULT_ROOT / "m27ac_pattern_guard_recall.json"
MD = DEFAULT_ROOT / "m27ac_pattern_guard_recall.md"


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


def _pattern_hits(plan: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    hits: list[tuple[str, dict[str, Any]]] = []
    selected = plan.get("selected_action_candidate") if isinstance(plan.get("selected_action_candidate"), dict) else None
    if selected and selected.get("scorer_feedback_pattern_matched") and selected.get("matched_regression_guard_key"):
        hits.append((str(selected["matched_regression_guard_key"]), selected))
    for item in plan.get("rejected_action_candidates") or []:
        if not isinstance(item, dict):
            continue
        if item.get("scorer_feedback_pattern_matched") and item.get("matched_regression_guard_key"):
            hits.append((str(item["matched_regression_guard_key"]), item))
    return hits



def _hit_is_record_only(item: dict[str, Any]) -> bool:
    # M2.7ac measures collateral from pattern-level guards only. A candidate can
    # still be record-only due to the legacy exact signature overlay or another
    # runtime guard even when the matched pattern has been downgraded to
    # diagnostic_only; do not charge that collateral to the pattern recall gate.
    return item.get("scorer_feedback_pattern_action") == "record_only"

def _case_success_map(root: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    path = root / "subset_case_report.jsonl"
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("case_id"):
            rows[str(row["case_id"])] = row
    return rows


def evaluate(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    aa = _j(root / "m27aa_regression_patterns.json", {}) or {}
    preflight = _j(root / "m27i_guard_preflight.json", {}) or {}
    m = _j(root / "m27m_guidance_only_readiness.json", {}) or {}
    case_report = _case_success_map(root)
    fixed_ids = set((preflight.get("fixed_cases_guard_status") or {}).keys())
    raw_old_regression_ids = set(str(item) for item in aa.get("raw_old_regression_unresolved_case_ids") or aa.get("old_regression_unresolved_case_ids") or [])
    pattern_rows = {str(p.get("regression_guard_key")): p for p in aa.get("blocked_regression_patterns") or [] if isinstance(p, dict) and p.get("regression_guard_key")}
    stats: dict[str, dict[str, Any]] = {}
    for key, pattern in pattern_rows.items():
        stats[key] = {
            "pattern_key": key,
            "pattern": pattern,
            "regression_cases_blocked": [],
            "fixed_cases_blocked": [],
            "productive_nonregression_cases_blocked": [],
            "matched_candidate_count": 0,
            "matched_case_ids": [],
            "net_recall_loss": 0,
            "recommended_action": "diagnostic_only",
            "reason": None,
        }
    for case in preflight.get("cases") or []:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("case_id") or "")
        plan = case.get("after_guard_plan") if isinstance(case.get("after_guard_plan"), dict) else {}
        guard_status = str(case.get("guard_status") or "")
        row = case_report.get(case_id, {})
        for key, candidate in _pattern_hits(plan):
            if key not in stats:
                continue
            item = stats[key]
            item["matched_candidate_count"] += 1
            if case_id not in item["matched_case_ids"]:
                item["matched_case_ids"].append(case_id)
            blocked = (guard_status == "guard_rejected" or not plan.get("activated")) and _hit_is_record_only(candidate)
            if case_id in raw_old_regression_ids and blocked and case_id not in item["regression_cases_blocked"]:
                item["regression_cases_blocked"].append(case_id)
            elif case_id in fixed_ids and blocked and case_id not in item["fixed_cases_blocked"]:
                item["fixed_cases_blocked"].append(case_id)
            elif blocked and row.get("candidate_success") and not row.get("case_regressed") and case_id not in item["productive_nonregression_cases_blocked"]:
                item["productive_nonregression_cases_blocked"].append(case_id)
    for item in stats.values():
        item["regression_cases_blocked"] = sorted(item["regression_cases_blocked"])
        item["fixed_cases_blocked"] = sorted(item["fixed_cases_blocked"])
        item["productive_nonregression_cases_blocked"] = sorted(item["productive_nonregression_cases_blocked"])
        item["matched_case_ids"] = sorted(item["matched_case_ids"])
        item["net_recall_loss"] = len(item["fixed_cases_blocked"]) + len(item["productive_nonregression_cases_blocked"]) - len(item["regression_cases_blocked"])
        overbroad = item["matched_candidate_count"] > 6
        if item["fixed_cases_blocked"] or item["productive_nonregression_cases_blocked"] or overbroad:
            item["recommended_action"] = "diagnostic_only"
            reasons = []
            if item["fixed_cases_blocked"]:
                reasons.append("fixed_case_collateral")
            if item["productive_nonregression_cases_blocked"]:
                reasons.append("productive_nonregression_collateral")
            if overbroad:
                reasons.append("overbroad_pattern_match")
            item["reason"] = ",".join(reasons)
        elif item["regression_cases_blocked"]:
            item["recommended_action"] = "record_only"
            item["reason"] = "high_confidence_regression_only_pattern"
        else:
            item["recommended_action"] = "diagnostic_only"
            item["reason"] = "no_current_replay_regression_block"
    patterns = sorted(stats.values(), key=lambda x: x["pattern_key"])
    fixed_blocked = sorted({case_id for p in patterns for case_id in p["fixed_cases_blocked"]})
    productive_blocked = sorted({case_id for p in patterns for case_id in p["productive_nonregression_cases_blocked"]})
    activation = m.get("plan_activated_count_after_guard", preflight.get("plan_activated_count_after_guard"))
    dominant = m.get("dominant_selected_next_tool_rate_after_guard", preflight.get("dominant_selected_next_tool_rate_after_guard"))
    passed = (
        not fixed_blocked
        and not productive_blocked
        and isinstance(activation, int) and activation >= 10
        and isinstance(dominant, (int, float)) and dominant <= 0.8
    )
    return {
        "report_scope": "m2_7ac_pattern_guard_recall",
        "artifact_root": str(root),
        "patterns": patterns,
        "pattern_action_overrides": {p["pattern_key"]: p["recommended_action"] for p in patterns},
        "fixed_case_blocked_count": len(fixed_blocked),
        "fixed_cases_blocked": fixed_blocked,
        "productive_nonregression_case_blocked_count": len(productive_blocked),
        "productive_nonregression_cases_blocked": productive_blocked,
        "plan_activated_count_after_guard": activation,
        "dominant_selected_next_tool_rate_after_guard": dominant,
        "m27ac_pattern_guard_recall_passed": passed,
        "diagnostic": {
            "offline_only": True,
            "does_not_run_bfcl": True,
            "record_only_requires_no_fixed_or_productive_collateral": True,
            "does_not_authorize_holdout_or_100_case": True,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7ac Pattern Guard Recall",
        "",
        f"- Passed: `{report['m27ac_pattern_guard_recall_passed']}`",
        f"- Fixed cases blocked: `{report['fixed_case_blocked_count']}`",
        f"- Productive non-regression cases blocked: `{report['productive_nonregression_case_blocked_count']}`",
        f"- After-guard activations: `{report['plan_activated_count_after_guard']}`",
        "",
        "| Pattern | Regression blocked | Fixed blocked | Productive blocked | Matches | Action |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for p in report.get("patterns", []):
        lines.append(
            f"| `{p['pattern_key'][:80]}` | `{len(p['regression_cases_blocked'])}` | `{len(p['fixed_cases_blocked'])}` | `{len(p['productive_nonregression_cases_blocked'])}` | `{p['matched_candidate_count']}` | `{p['recommended_action']}` |"
        )
    lines.extend(["", "This is an offline collateral diagnostic only. It does not call BFCL or prove performance.", ""])
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
        print(json.dumps({k: report.get(k) for k in ["m27ac_pattern_guard_recall_passed", "fixed_case_blocked_count", "productive_nonregression_case_blocked_count", "plan_activated_count_after_guard", "dominant_selected_next_tool_rate_after_guard", "pattern_action_overrides"]}, indent=2, sort_keys=True))
    return 0 if report["m27ac_pattern_guard_recall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
