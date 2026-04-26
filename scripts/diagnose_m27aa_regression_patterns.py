#!/usr/bin/env python3
"""Diagnose pattern-level scorer-feedback guards for M2.7aa."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_RULES = Path("outputs/phase2_subset/bfcl_ctspc_subset30_v1/candidate_rules")
OUT = DEFAULT_ROOT / "m27aa_regression_patterns.json"
MD = DEFAULT_ROOT / "m27aa_regression_patterns.md"
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


def _jl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tool_family(tool: Any) -> str:
    name = str(tool or "").strip()
    return {
        "cat": "read_content",
        "touch": "create_file",
        "mkdir": "create_directory",
        "grep": "search",
        "find": "search",
        "cp": "move_or_copy",
        "mv": "move_or_copy",
        "echo": "write_content",
        "diff": "compare",
        "cd": "directory_navigation",
    }.get(name, name or "unknown")


def postcondition_family(postcondition: Any) -> str:
    if not isinstance(postcondition, dict):
        return "unknown"
    kind = str(postcondition.get("kind") or "").strip()
    return {
        "file_content": "read_content",
        "file_exists": "create_file",
        "directory_exists": "create_directory",
        "matches": "search",
        "target_path_changed": "move_or_copy",
        "content_written": "write_content",
        "comparison": "compare",
        "directory_navigation": "directory_navigation",
    }.get(kind, kind or "unknown")


def _source_from_validation(v_case: dict[str, Any] | None) -> str:
    if not isinstance(v_case, dict):
        return "unknown"
    validation = v_case.get("canonical_arg_validation") or {}
    sources = sorted({str(item.get("source")) for item in validation.values() if isinstance(item, dict) and item.get("source")})
    return "+".join(sources) if sources else "unknown"


def _normalise_flags(flags: Any) -> list[str]:
    if not isinstance(flags, list):
        return []
    return sorted({str(flag) for flag in flags if str(flag).strip()})


def _load_rule_candidates(rules_dir: Path) -> list[dict[str, Any]]:
    if yaml is None or not rules_dir.exists():
        return []
    candidates: list[dict[str, Any]] = []
    for path in sorted(rules_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        containers: list[dict[str, Any]] = []
        if isinstance(data, dict):
            containers.extend(data.get("rules") or [])
            containers.extend(data.get("policy_units") or [])
        for container in containers:
            decision = ((container.get("action") or {}).get("decision_policy") or {}) if isinstance(container.get("action"), dict) else {}
            action_candidates = decision.get("action_candidates") or container.get("action_candidates") or []
            rule_id = container.get("rule_id") or container.get("name")
            for candidate in action_candidates:
                if isinstance(candidate, dict):
                    item = dict(candidate)
                    item.setdefault("rule_id", rule_id)
                    candidates.append(item)
    return candidates


def _args_match(left: Any, right: Any) -> bool:
    return isinstance(left, dict) and isinstance(right, dict) and left == right


def _find_rule_candidate(rule_candidates: list[dict[str, Any]], tool: Any, args: Any) -> dict[str, Any]:
    tool_name = str(tool or "")
    if not tool_name:
        return {}
    for candidate in rule_candidates:
        if str(candidate.get("tool") or "") == tool_name and _args_match(candidate.get("args"), args):
            return candidate
    for candidate in rule_candidates:
        if str(candidate.get("tool") or "") == tool_name:
            return candidate
    return {}


def _pattern_key(pattern: dict[str, Any], *, include_gap_type: bool) -> str:
    keys = [
        "selected_tool_family",
        "postcondition_family",
        "binding_source",
        "baseline_success_proxy",
    ]
    if include_gap_type:
        keys.append("gap_type")
    body = {key: pattern.get(key) for key in keys}
    body["trajectory_risk_flags"] = sorted(pattern.get("trajectory_risk_flags") or [])
    body["repair_kinds"] = sorted(pattern.get("repair_kinds") or [])
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _pattern_from_case(
    case: dict[str, Any],
    *,
    v_case: dict[str, Any] | None,
    rule_candidate: dict[str, Any],
) -> dict[str, Any]:
    selected_tool = case.get("offline_selected_tool") or case.get("scorer_selected_tool")
    candidate_args = case.get("offline_candidate_args") if isinstance(case.get("offline_candidate_args"), dict) else {}
    post = rule_candidate.get("postcondition") if isinstance(rule_candidate, dict) else {}
    binding_source = (rule_candidate.get("binding_source") if isinstance(rule_candidate, dict) else None) or _source_from_validation(v_case)
    risk_flags = _normalise_flags(rule_candidate.get("trajectory_risk_flags") if isinstance(rule_candidate, dict) else [])
    repair_kinds = sorted({str(item) for item in (case.get("repair_kinds") or []) if str(item).strip()})
    pattern = {
        "selected_tool_family": tool_family(selected_tool),
        "postcondition_family": postcondition_family(post),
        "binding_source": str(binding_source or "unknown"),
        "trajectory_risk_flags": risk_flags,
        "repair_kinds": repair_kinds,
        "gap_type": str(case.get("gap_type") or "no_proxy_gap"),
        "baseline_success_proxy": bool(case.get("baseline_success")),
    }
    pattern["shared_pattern_key"] = _pattern_key(pattern, include_gap_type=True)
    pattern["regression_guard_key"] = _pattern_key(pattern, include_gap_type=False)
    return pattern


def evaluate(root: Path = DEFAULT_ROOT, rules_dir: Path = DEFAULT_RULES) -> dict[str, Any]:
    summary = _j(root / "subset_summary.json", {}) or {}
    gap = _j(root / "m27x_scorer_proxy_gap.json", {}) or {}
    feedback = _j(root / "m27y_scorer_feedback.json", {}) or {}
    z = _j(root / "m27z_feedback_effect.json", {}) or {}
    v = _j(root / "m27v_arg_realization.json", {}) or {}
    current_rows = _jl(root / "subset_case_report.jsonl")
    current_by_id = {str(row.get("case_id")): row for row in current_rows if row.get("case_id")}
    v_by_id = {str(row.get("case_id")): row for row in (v.get("cases") or []) if isinstance(row, dict) and row.get("case_id")}
    rule_candidates = _load_rule_candidates(rules_dir)

    old_regression_ids = {str(item) for item in feedback.get("regression_case_ids") or []}
    z_still_regressed = set(z.get("previous_regression_cases_still_regressed") or [])
    z_new_regressions = {str(item.get("case_id")) for item in (z.get("new_regression_cases") or []) if isinstance(item, dict) and item.get("case_id")}
    gap_cases = gap.get("cases") if isinstance(gap.get("cases"), list) else []
    gap_by_id = {str(case.get("case_id")): case for case in gap_cases if isinstance(case, dict) and case.get("case_id")}

    relevant_ids = set()
    for case in gap_cases:
        gap_type = str(case.get("gap_type") or "")
        if gap_type in BLOCKING_GAP_TYPES or case.get("case_regressed") or str(case.get("case_id")) in old_regression_ids:
            relevant_ids.add(str(case.get("case_id")))
    relevant_ids.update(old_regression_ids)
    relevant_ids.update(z_new_regressions)
    relevant_ids.update(z_still_regressed)

    cases: list[dict[str, Any]] = []
    regression_guard_keys: set[str] = set()
    for case_id in sorted(relevant_ids):
        gap_case = dict(gap_by_id.get(case_id) or {})
        current = current_by_id.get(case_id) or {}
        if current:
            gap_case.setdefault("case_id", case_id)
            for key in ["baseline_success", "candidate_success", "case_fixed", "case_regressed", "repair_kinds", "selected_next_tool"]:
                gap_case.setdefault(key, current.get(key))
            gap_case.setdefault("scorer_selected_tool", current.get("selected_next_tool"))
        v_case = v_by_id.get(case_id)
        tool = gap_case.get("offline_selected_tool") or gap_case.get("scorer_selected_tool")
        args = gap_case.get("offline_candidate_args") or ((v_case or {}).get("candidate_arg_json") if isinstance(v_case, dict) else {}) or {}
        rule_candidate = _find_rule_candidate(rule_candidates, tool, args)
        pattern = _pattern_from_case(gap_case, v_case=v_case, rule_candidate=rule_candidate)
        old = case_id in old_regression_ids
        still_regressed = case_id in z_still_regressed or bool(current.get("case_regressed") and old)
        new_regression = case_id in z_new_regressions or (bool(current.get("case_regressed")) and not old)
        regression_like = still_regressed or new_regression or bool(gap_case.get("case_regressed"))
        if regression_like:
            regression_guard_keys.add(pattern["regression_guard_key"])
        cases.append(
            {
                "case_id": case_id,
                "old_or_new_regression": "old_unresolved" if still_regressed else ("new_regression" if new_regression else ("old_resolved" if old else "gap_only")),
                "policy_activated": bool(current.get("policy_plan_activated")),
                "selected_tool": tool,
                "candidate_args": args,
                "binding_source": pattern["binding_source"],
                "pending_goal": (rule_candidate.get("pending_goal_family") if isinstance(rule_candidate, dict) else None) or "unknown",
                "postcondition": rule_candidate.get("postcondition") if isinstance(rule_candidate, dict) else {},
                "postcondition_family": pattern["postcondition_family"],
                "trajectory_risk_flags": pattern["trajectory_risk_flags"],
                "repair_kinds": pattern["repair_kinds"],
                "gap_type": pattern["gap_type"],
                "baseline_success": bool(gap_case.get("baseline_success")),
                "candidate_success": bool(gap_case.get("candidate_success")),
                "case_regressed": bool(current.get("case_regressed") or gap_case.get("case_regressed")),
                "case_fixed": bool(current.get("case_fixed") or gap_case.get("case_fixed")),
                "shared_pattern_key": pattern["shared_pattern_key"],
                "regression_guard_key": pattern["regression_guard_key"],
                "suggested_guard": "record_only" if regression_like else "diagnostic_pending_pattern_check",
                "rule_id": rule_candidate.get("rule_id") if isinstance(rule_candidate, dict) else None,
            }
        )

    for case in cases:
        if case["suggested_guard"] == "diagnostic_pending_pattern_check":
            if case["regression_guard_key"] in regression_guard_keys:
                case["diagnostic_gap_safety"] = "diagnostic_unsafe_gap"
                case["suggested_guard"] = "record_only"
            else:
                case["diagnostic_gap_safety"] = "diagnostic_safe_gap"
                case["suggested_guard"] = "diagnostic_only"
        else:
            case["diagnostic_gap_safety"] = None

    pattern_groups: dict[str, dict[str, Any]] = {}
    for case in cases:
        key = case["regression_guard_key"]
        group = pattern_groups.setdefault(
            key,
            {
                "regression_guard_key": key,
                "case_ids": [],
                "regression_case_ids": [],
                "diagnostic_gap_case_ids": [],
                "suggested_guard": "diagnostic_only",
                "example": {k: case.get(k) for k in ["binding_source", "postcondition_family", "trajectory_risk_flags", "repair_kinds"]},
            },
        )
        group["case_ids"].append(case["case_id"])
        if case["case_regressed"] or case["old_or_new_regression"] in {"old_unresolved", "new_regression"}:
            group["regression_case_ids"].append(case["case_id"])
            group["suggested_guard"] = "record_only"
        elif case.get("diagnostic_gap_safety"):
            group["diagnostic_gap_case_ids"].append(case["case_id"])

    old_unresolved = [case["case_id"] for case in cases if case["old_or_new_regression"] == "old_unresolved"]
    new_regression_patterns = sorted({case["regression_guard_key"] for case in cases if case["old_or_new_regression"] == "new_regression"})
    unsafe = [case["case_id"] for case in cases if case.get("diagnostic_gap_safety") == "diagnostic_unsafe_gap"]
    regression_patterns = [group for group in pattern_groups.values() if group["regression_case_ids"]]
    blocked_patterns = [
        {
            "regression_guard_key": group["regression_guard_key"],
            "selected_tool_family": json.loads(group["regression_guard_key"]).get("selected_tool_family"),
            "postcondition_family": json.loads(group["regression_guard_key"]).get("postcondition_family"),
            "binding_source": json.loads(group["regression_guard_key"]).get("binding_source"),
            "trajectory_risk_flags": json.loads(group["regression_guard_key"]).get("trajectory_risk_flags") or [],
            "repair_kinds": json.loads(group["regression_guard_key"]).get("repair_kinds") or [],
            "baseline_success_proxy": json.loads(group["regression_guard_key"]).get("baseline_success_proxy"),
            "case_ids": sorted(set(group["regression_case_ids"])),
            "action": "record_only",
        }
        for group in regression_patterns
    ]
    covered_keys = {item["regression_guard_key"] for item in blocked_patterns}
    regression_keys = {group["regression_guard_key"] for group in regression_patterns}
    coverage = (len(covered_keys & regression_keys) / len(regression_keys)) if regression_keys else 1.0
    passed = (not old_unresolved) and (not new_regression_patterns) and coverage == 1.0 and not unsafe and bool(regression_patterns)
    report = {
        "report_scope": "m2_7aa_regression_patterns",
        "artifact_root": str(root),
        "case_report_trace_mapping": summary.get("case_report_trace_mapping"),
        "case_level_gate_allowed": summary.get("case_level_gate_allowed"),
        "latest_dev_net_case_gain": summary.get("net_case_gain"),
        "cases": cases,
        "pattern_groups": sorted(pattern_groups.values(), key=lambda item: item["regression_guard_key"]),
        "blocked_regression_patterns": blocked_patterns,
        "old_regression_unresolved_case_ids": old_unresolved,
        "old_regression_unresolved_count": len(old_unresolved),
        "new_regression_pattern_keys": new_regression_patterns,
        "new_regression_pattern_count": len(new_regression_patterns),
        "regression_pattern_coverage": coverage,
        "diagnostic_unsafe_gap_case_ids": unsafe,
        "diagnostic_unsafe_gap_count": len(unsafe),
        "scorer_feedback_covers_regression_patterns": coverage == 1.0 and bool(regression_patterns),
        "m27aa_regression_patterns_passed": passed,
        "diagnostic": {
            "offline_only": True,
            "does_not_authorize_holdout_or_100_case": True,
            "pattern_gate_requires_future_code_or_scorer_evidence": not passed,
        },
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7aa Regression Patterns",
        "",
        f"- Passed: `{report['m27aa_regression_patterns_passed']}`",
        f"- Old unresolved regressions: `{report['old_regression_unresolved_count']}`",
        f"- New regression patterns: `{report['new_regression_pattern_count']}`",
        f"- Regression pattern coverage: `{report['regression_pattern_coverage']}`",
        f"- Diagnostic unsafe gaps: `{report['diagnostic_unsafe_gap_count']}`",
        "",
        "## Regression / Gap Cases",
    ]
    for case in report.get("cases", []):
        lines.append(
            f"- `{case['case_id']}`: `{case['old_or_new_regression']}`, tool=`{case.get('selected_tool')}`, "
            f"binding=`{case.get('binding_source')}`, gap=`{case.get('gap_type')}`, guard=`{case.get('suggested_guard')}`"
        )
    lines.extend(["", "This is an offline pattern abstraction diagnostic. It does not run BFCL or prove scorer performance.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--rules-dir", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.root, args.rules_dir)
    _write_json(args.output, report)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in ["m27aa_regression_patterns_passed", "old_regression_unresolved_count", "new_regression_pattern_count", "regression_pattern_coverage", "diagnostic_unsafe_gap_count", "scorer_feedback_covers_regression_patterns"]}, indent=2, sort_keys=True))
    return 0 if report["m27aa_regression_patterns_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
