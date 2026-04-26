#!/usr/bin/env python3
"""M2.7q postmortem and rule-retention diagnostics.

This script is offline-only. It reads the latest M2.7f-lite subset artifacts and
summarizes why M2.7p offline readiness did not become scorer-level gain.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_OUTPUT = DEFAULT_ROOT / "m27q_postmortem.json"
DEFAULT_MARKDOWN = DEFAULT_ROOT / "m27q_postmortem.md"

POSTCONDITION_TO_GOAL = {
    "file_content": "read_content",
    "file_exists": "create_file",
    "directory_exists": "create_directory",
    "matches": "search",
    "target_path_changed": "move_or_copy",
}


def _read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _bool(row: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = row.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
    return False


def _number(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _case_id(row: dict[str, Any]) -> str:
    return str(row.get("case_id") or row.get("id") or row.get("test_case_id") or "")


def _selected_candidate(row: dict[str, Any]) -> dict[str, Any]:
    candidate = row.get("selected_action_candidate") or row.get("accepted_action_candidate") or {}
    if isinstance(candidate, dict):
        return candidate
    return {}


def _semantic_candidate_issues(row: dict[str, Any]) -> list[str]:
    candidate = _selected_candidate(row)
    issues: list[str] = []
    if not candidate:
        return issues

    postcondition = candidate.get("postcondition") or {}
    kind = postcondition.get("kind") if isinstance(postcondition, dict) else None
    pending_goal = (
        candidate.get("pending_goal_family")
        or row.get("pending_goal_family")
        or row.get("selected_pending_goal_family")
    )
    intervention_mode = candidate.get("intervention_mode")
    risk_score = candidate.get("trajectory_risk_score")
    risk_flags = candidate.get("trajectory_risk_flags") or []

    if not kind:
        issues.append("postcondition_missing")
    elif kind in POSTCONDITION_TO_GOAL:
        expected_goal = POSTCONDITION_TO_GOAL[kind]
        if pending_goal and pending_goal != "unknown" and pending_goal != expected_goal:
            issues.append("pending_goal_postcondition_mismatch")
    else:
        issues.append("unknown_postcondition_kind")

    if intervention_mode in {"record_only", "weak_guidance"}:
        issues.append(f"intervention_mode_{intervention_mode}")

    try:
        if risk_score is not None and float(risk_score) >= 0.75:
            issues.append("high_trajectory_risk_score")
    except (TypeError, ValueError):
        pass

    if risk_flags:
        issues.append("trajectory_risk_flags_present")

    return issues


def classify_case(row: dict[str, Any]) -> dict[str, Any]:
    """Classify a single case-report row into M2.7q failure layers."""
    case_id = _case_id(row)
    baseline_success = _bool(row, "baseline_success", "baseline_correct")
    candidate_success = _bool(row, "candidate_success", "candidate_correct")
    activated = _bool(row, "policy_plan_activated", "plan_activated", "activated")
    fixed = _bool(row, "case_fixed") or (candidate_success and not baseline_success)
    regressed = _bool(row, "case_regressed") or (baseline_success and not candidate_success)
    recommended_tool_match = _bool(row, "recommended_tool_match", "recommended_next_tool_match")
    raw_arg_match = _bool(row, "raw_normalized_arg_match", "raw_arg_match")
    final_arg_match = _bool(row, "final_normalized_arg_match", "final_arg_match")

    layers: list[str] = []
    semantic_issues = _semantic_candidate_issues(row)
    if not activated:
        layers.append("not_activated")
    elif semantic_issues:
        layers.append("semantic_candidate_wrong")
    elif not recommended_tool_match:
        layers.append("tool_match_low")
    elif not (raw_arg_match or final_arg_match):
        layers.append("arg_match_low")
    elif not candidate_success:
        layers.append("trajectory_continuation_or_postcondition")
    else:
        layers.append("aligned_success")

    if regressed and "regression" not in layers:
        layers.append("regression")
    if fixed and "fixed" not in layers:
        layers.append("fixed")

    if regressed:
        primary_layer = "regression"
    else:
        primary_layer = layers[0]

    case_kind = "fixed" if fixed else "regressed" if regressed else "unchanged"
    if not activated:
        case_kind = "not_activated"

    return {
        "case_id": case_id,
        "case_kind": case_kind,
        "primary_failure_layer": primary_layer,
        "failure_layers": layers,
        "semantic_candidate_issues": semantic_issues,
        "baseline_success": baseline_success,
        "candidate_success": candidate_success,
        "policy_plan_activated": activated,
        "case_fixed": fixed,
        "case_regressed": regressed,
        "selected_next_tool": row.get("selected_next_tool"),
        "recommended_next_tool": row.get("recommended_next_tool"),
        "emitted_tool": row.get("emitted_tool") or row.get("candidate_emitted_tool"),
        "recommended_tool_match": recommended_tool_match,
        "raw_normalized_arg_match": raw_arg_match,
        "final_normalized_arg_match": final_arg_match,
        "repair_kinds": row.get("repair_kinds") or row.get("candidate_repair_kinds") or [],
        "selected_action_candidate": _selected_candidate(row),
        "rule_id": row.get("rule_id") or row.get("selected_rule_id"),
    }


def _failed_gate_criteria(summary: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    mapping = summary.get("case_report_trace_mapping")
    gate_allowed = summary.get("case_level_gate_allowed")
    if mapping != "prompt_user_prefix" or gate_allowed is False:
        failures.append("case_level_trace_attribution_allowed")
    if _number(summary, "candidate_accuracy") <= _number(summary, "baseline_accuracy"):
        failures.append("candidate_accuracy_gt_baseline_accuracy")
    if int(summary.get("case_fixed_count") or 0) <= int(summary.get("case_regressed_count") or 0):
        failures.append("case_fixed_gt_regressed")
    if int(summary.get("net_case_gain") or 0) < 2:
        failures.append("net_case_gain_min_2")
    if int(summary.get("policy_plan_activated_count") or 0) <= 0:
        failures.append("policy_plan_activated_positive")
    if _number(summary, "recommended_tool_match_rate_among_activated") < 0.6:
        failures.append("recommended_tool_match_rate_min_0_6")
    if _number(summary, "raw_normalized_arg_match_rate_among_activated") < 0.6:
        failures.append("raw_arg_match_rate_min_0_6")
    if int(summary.get("stop_allowed_false_positive_count") or 0) != 0:
        failures.append("stop_allowed_false_positive_zero")
    return failures


def _load_rule_retention(root: Path) -> dict[str, Any]:
    report = _read_json(root / "m27f_rule_level_report.json", default={})
    rules = report.get("rules") or report.get("rule_retention") or []
    normalized = []
    decisions = Counter()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        item = {
            "rule_id": rule.get("rule_id"),
            "activation_count": rule.get("activation_count", 0),
            "fixed_count": rule.get("fixed_count", 0),
            "regressed_count": rule.get("regressed_count", 0),
            "net_case_gain": rule.get("net_case_gain", 0),
            "tool_match_rate": rule.get("tool_match_rate", 0.0),
            "arg_match_rate": rule.get("arg_match_rate", 0.0),
            "trajectory_fail_count": rule.get("trajectory_fail_count", 0),
            "decision": rule.get("decision", "reject"),
        }
        decisions[str(item["decision"])] += 1
        normalized.append(item)
    return {
        "source": str(root / "m27f_rule_level_report.json"),
        "rule_count": len(normalized),
        "decision_distribution": dict(sorted(decisions.items())),
        "rules": normalized,
    }


def _next_focus(summary: dict[str, Any], layer_counts: Counter[str], rule_retention: dict[str, Any], durable: bool) -> str:
    if not durable:
        return "trace_attribution_or_completeness"
    if _number(summary, "candidate_accuracy") < _number(summary, "baseline_accuracy"):
        return "regression_and_rule_retention"
    if _number(summary, "raw_normalized_arg_match_rate_among_activated") < 0.6:
        return "binding_serialization_or_argument_realization"
    if layer_counts.get("trajectory_continuation_or_postcondition", 0) >= layer_counts.get("tool_match_low", 0):
        return "trajectory_state_or_postcondition"
    if layer_counts.get("tool_match_low", 0) > 0:
        return "guidance_or_selected_tool_ranking"
    decisions = rule_retention.get("decision_distribution", {})
    if decisions.get("reject", 0) == rule_retention.get("rule_count", 0) and rule_retention.get("rule_count", 0):
        return "rule_retention_reject_or_demote"
    return "m2_7r_offline_readiness_planning"


def evaluate_postmortem(root: Path) -> dict[str, Any]:
    manifest = _read_json(root / "paired_subset_manifest.json", default={})
    summary = _read_json(root / "subset_summary.json")
    rows = _read_jsonl(root / "subset_case_report.jsonl")
    rule_retention = _load_rule_retention(root)

    cases = [classify_case(row) for row in rows]
    case_kind_counts = Counter(case["case_kind"] for case in cases)
    layer_counts: Counter[str] = Counter()
    for case in cases:
        for layer in case["failure_layers"]:
            layer_counts[layer] += 1

    durable = (
        summary.get("case_report_trace_mapping") == "prompt_user_prefix"
        and summary.get("case_level_gate_allowed") is not False
    )
    failed = _failed_gate_criteria(summary)
    focus = _next_focus(summary, layer_counts, rule_retention, durable)

    report = {
        "report_scope": "m2_7q_postmortem_rule_retention",
        "artifact_root": str(root),
        "selected_case_count": len(manifest.get("selected_case_ids") or []),
        "case_report_row_count": len(rows),
        "evidence_status": "durable" if durable else "diagnostic_only",
        "case_report_trace_mapping": summary.get("case_report_trace_mapping"),
        "case_level_gate_allowed": summary.get("case_level_gate_allowed"),
        "baseline_accuracy": summary.get("baseline_accuracy"),
        "candidate_accuracy": summary.get("candidate_accuracy"),
        "case_fixed_count": summary.get("case_fixed_count"),
        "case_regressed_count": summary.get("case_regressed_count"),
        "net_case_gain": summary.get("net_case_gain"),
        "policy_plan_activated_count": summary.get("policy_plan_activated_count"),
        "recommended_tool_match_rate_among_activated": summary.get("recommended_tool_match_rate_among_activated"),
        "raw_normalized_arg_match_rate_among_activated": summary.get("raw_normalized_arg_match_rate_among_activated"),
        "stop_allowed_false_positive_count": summary.get("stop_allowed_false_positive_count"),
        "failed_gate_criteria": failed,
        "case_kind_distribution": dict(sorted(case_kind_counts.items())),
        "failure_layer_distribution": dict(sorted(layer_counts.items())),
        "cases": cases,
        "rule_retention": rule_retention,
        "recommended_next_focus": focus,
        "recommendations": _recommendations(focus, rule_retention),
        "m2_7q_postmortem_passed": durable and bool(rows),
        "diagnostic": {
            "no_bfcl_rerun": True,
            "no_100_case": True,
            "no_m2_8": True,
            "no_full_bfcl": True,
            "dev_subset_only": True,
            "next_stage_requires_offline_m2_7r_gate": True,
        },
    }
    return report


def _recommendations(focus: str, rule_retention: dict[str, Any]) -> list[str]:
    recommendations = ["do_not_rerun_m2_7f_on_this_30_case_dev_subset_without_new_offline_gate"]
    if focus == "binding_serialization_or_argument_realization":
        recommendations.append("plan_m2_7r_binding_serialization_and_argument_realization")
    elif focus == "trajectory_state_or_postcondition":
        recommendations.append("plan_m2_7r_postcondition_to_pending_subgoal_calibration")
    elif focus == "regression_and_rule_retention":
        recommendations.append("demote_or_reject_rules_with_nonpositive_net_case_gain")
    elif focus == "guidance_or_selected_tool_ranking":
        recommendations.append("inspect_selected_tool_ranking_and_guidance_realization")
    elif focus == "trace_attribution_or_completeness":
        recommendations.append("repair_trace_attribution_before_interpreting_case_level_metrics")
    if rule_retention.get("decision_distribution", {}).get("reject", 0):
        recommendations.append("keep_current_default_rule_decision_reject_unless_rule_has_positive_local_evidence")
    return recommendations


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7q Postmortem And Rule Retention",
        "",
        "## Summary",
        "",
        f"- Evidence status: `{report['evidence_status']}`",
        f"- Trace mapping: `{report.get('case_report_trace_mapping')}`",
        f"- Case-level gate allowed: `{report.get('case_level_gate_allowed')}`",
        f"- Accuracy: baseline `{report.get('baseline_accuracy')}`, candidate `{report.get('candidate_accuracy')}`",
        f"- Fixed/regressed/net: `{report.get('case_fixed_count')}` / `{report.get('case_regressed_count')}` / `{report.get('net_case_gain')}`",
        f"- Tool match rate: `{report.get('recommended_tool_match_rate_among_activated')}`",
        f"- Raw arg match rate: `{report.get('raw_normalized_arg_match_rate_among_activated')}`",
        f"- Recommended next focus: `{report.get('recommended_next_focus')}`",
        "",
        "## Failed Gate Criteria",
        "",
    ]
    if report["failed_gate_criteria"]:
        lines.extend(f"- `{item}`" for item in report["failed_gate_criteria"])
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Failure Layers",
        "",
        "| Layer | Count |",
        "| --- | ---: |",
    ])
    for key, value in report["failure_layer_distribution"].items():
        lines.append(f"| `{key}` | {value} |")

    lines.extend([
        "",
        "## Rule Retention",
        "",
        "| Rule | Activations | Fixed | Regressed | Net | Tool Match | Arg Match | Trajectory Fails | Decision |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ])
    for rule in report["rule_retention"]["rules"]:
        lines.append(
            "| `{rule_id}` | {activation_count} | {fixed_count} | {regressed_count} | {net_case_gain} | {tool_match_rate} | {arg_match_rate} | {trajectory_fail_count} | `{decision}` |".format(**rule)
        )

    lines.extend([
        "",
        "## Recommendations",
        "",
    ])
    lines.extend(f"- `{item}`" for item in report["recommendations"])
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--compact", action="store_true", help="Print compact JSON summary to stdout")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate_postmortem(args.root)
    _write_json(args.output, report)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report))

    if args.compact:
        compact_keys = [
            "evidence_status",
            "case_report_trace_mapping",
            "case_level_gate_allowed",
            "baseline_accuracy",
            "candidate_accuracy",
            "case_fixed_count",
            "case_regressed_count",
            "net_case_gain",
            "recommended_tool_match_rate_among_activated",
            "raw_normalized_arg_match_rate_among_activated",
            "failed_gate_criteria",
            "failure_layer_distribution",
            "recommended_next_focus",
            "m2_7q_postmortem_passed",
        ]
        print(json.dumps({key: report.get(key) for key in compact_keys}, indent=2, sort_keys=True))
    else:
        print(f"Wrote {args.output}")
        print(f"Wrote {args.markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
