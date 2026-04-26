#!/usr/bin/env python3
"""M2.7ae CTSPC-v0 failure-mode audit and route decision.

Offline-only diagnostic. It freezes the latest durable M2.7 dev scorer failure
into a failure-mode audit, an ablation planning manifest, and a CTSPC-v0 status
artifact. It must not call BFCL/model and must not emit scorer commands.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
OUT = DEFAULT_ROOT / "m27ae_failure_mode_audit.json"
MD = DEFAULT_ROOT / "m27ae_failure_mode_audit.md"
ABLATION_OUT = DEFAULT_ROOT / "m27ae_ablation_matrix.json"
ABLATION_MD = DEFAULT_ROOT / "m27ae_ablation_matrix.md"
STATUS_OUT = DEFAULT_ROOT / "m27ae_ctspc_v0_status.json"
STATUS_MD = DEFAULT_ROOT / "m27ae_ctspc_v0_status.md"

ACTION_POLICY_SOURCES = {"action_policy", "arg_realization"}
REPAIR_KINDS = {
    "coerce_no_tool_text_to_empty",
    "resolve_contextual_string_arg",
    "strip_assistant_content_with_tool_calls",
}


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _bool(row: dict[str, Any], key: str) -> bool:
    value = row.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def _gap_map(root: Path) -> dict[str, dict[str, Any]]:
    gap = _read_json(root / "m27x_scorer_proxy_gap.json", {}) or {}
    return {str(case.get("case_id")): case for case in gap.get("cases") or [] if isinstance(case, dict) and case.get("case_id")}


def _first_divergence_layer(row: dict[str, Any], gap_case: dict[str, Any] | None = None) -> str:
    activated = _bool(row, "policy_plan_activated")
    tool_match = _bool(row, "recommended_tool_match")
    arg_match = _bool(row, "raw_normalized_arg_match") or _bool(row, "final_normalized_arg_match")
    repairs = set(row.get("repair_kinds") or [])
    gap_type = (gap_case or {}).get("gap_type")
    if not activated:
        if "coerce_no_tool_text_to_empty" in repairs:
            return "no_tool_repair"
        if repairs & REPAIR_KINDS:
            return "repair_stack"
        return "no_intervention"
    if not tool_match:
        return "action_selection"
    if not arg_match:
        return "argument_realization"
    if gap_type == "proxy_ok_trajectory_failed":
        return "trajectory_continuation"
    if repairs & {"strip_assistant_content_with_tool_calls", "resolve_contextual_string_arg"}:
        return "repair_stack_or_trajectory"
    return "trajectory_continuation"


def _regression_source(row: dict[str, Any], gap_case: dict[str, Any] | None = None) -> str:
    activated = _bool(row, "policy_plan_activated")
    candidate_success = _bool(row, "candidate_success")
    baseline_success = _bool(row, "baseline_success")
    tool_match = _bool(row, "recommended_tool_match")
    arg_match = _bool(row, "raw_normalized_arg_match") or _bool(row, "final_normalized_arg_match")
    repairs = set(row.get("repair_kinds") or [])
    if baseline_success and not candidate_success:
        if not activated:
            if "coerce_no_tool_text_to_empty" in repairs:
                return "no_tool_repair"
            if repairs & REPAIR_KINDS:
                return "repair_policy"
            return "no_intervention_baseline_variance"
        if not tool_match:
            return "action_policy"
        if not arg_match:
            return "action_policy"
        if repairs & {"strip_assistant_content_with_tool_calls", "resolve_contextual_string_arg"}:
            return "trajectory_continuation"
        return "trajectory_continuation"
    if _bool(row, "case_fixed"):
        return "fixed_signal"
    if activated and not candidate_success:
        if not tool_match or not arg_match:
            return "action_policy"
        return "trajectory_continuation"
    return "ambiguous"


def _suggested_next_action(source: str, row: dict[str, Any]) -> str:
    if source == "action_policy":
        return "redesign_trajectory_policy"
    if source in {"repair_policy", "no_tool_repair"}:
        return "split_repair_stack"
    if source == "trajectory_continuation":
        return "redesign_trajectory_policy"
    if source == "no_intervention_baseline_variance":
        return "baseline_variance_audit"
    if source == "fixed_signal":
        return "preserve_as_diagnostic_only_signal"
    return "manual_trace_audit"


def _case_audit(row: dict[str, Any], gap_case: dict[str, Any] | None = None) -> dict[str, Any]:
    source = _regression_source(row, gap_case)
    divergence = _first_divergence_layer(row, gap_case)
    return {
        "case_id": row.get("case_id"),
        "baseline_success": row.get("baseline_success"),
        "candidate_success": row.get("candidate_success"),
        "case_fixed": bool(row.get("case_fixed")),
        "case_regressed": bool(row.get("case_regressed")),
        "policy_plan_activated": bool(row.get("policy_plan_activated")),
        "selected_tool": row.get("selected_next_tool"),
        "tool_match": bool(row.get("recommended_tool_match")),
        "arg_match": bool(row.get("raw_normalized_arg_match") or row.get("final_normalized_arg_match")),
        "repair_kinds": row.get("repair_kinds") or [],
        "first_divergence_layer": divergence,
        "regression_source": source,
        "scorer_proxy_gap_type": (gap_case or {}).get("gap_type"),
        "suggested_next_action": _suggested_next_action(source, row),
    }


def _route_decision(source_distribution: Counter[str], ambiguous_count: int) -> str:
    repair = source_distribution.get("repair_policy", 0) + source_distribution.get("no_tool_repair", 0)
    action = source_distribution.get("action_policy", 0) + source_distribution.get("trajectory_continuation", 0)
    if repair and action:
        return "split_repair_stack + pivot_to_lower_risk_slice"
    if action:
        return "redesign_trajectory_policy"
    if repair:
        return "split_repair_stack"
    if ambiguous_count:
        return "pivot_to_lower_risk_slice"
    return "pivot_to_lower_risk_slice"


def build_ablation_manifest(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    variants = [
        ("candidate_none", {"ctspc_policy": "off", "repairs": "off"}, "Measure baseline-like behavior without CTSPC intervention."),
        ("compatibility_repairs_only", {"ctspc_policy": "off", "compatibility_repairs": "on"}, "Isolate repair stack contribution without action guidance."),
        ("action_guidance_only", {"action_guidance": "on", "compatibility_repairs": "off"}, "Isolate action policy without repair stack side effects."),
        ("repair_without_action", {"action_guidance": "off", "repair_stack": "on"}, "Check whether repair/no-tool coercion causes regressions."),
        ("action_without_repair", {"action_guidance": "on", "repair_stack": "off"}, "Check whether local action guidance alone damages trajectory."),
    ]
    return {
        "report_scope": "m2_7ae_ablation_matrix_manifest",
        "artifact_root": str(root),
        "offline_plan_only": True,
        "no_bfcl_or_model_call": True,
        "planned_commands": [],
        "candidate_commands": [],
        "ablation_variants": [
            {
                "ablation_id": name,
                "config_delta": delta,
                "expected_diagnostic_question": question,
                "required_future_approval": True,
                "contains_executable_scorer_command": False,
            }
            for name, delta, question in variants
        ],
    }


def build_ctspc_status(root: Path, summary: dict[str, Any], retention: dict[str, Any] | None = None) -> dict[str, Any]:
    retention = retention or {}
    decisions = retention.get("decision_distribution") or {}
    retained = int(decisions.get("retain") or 0)
    net = summary.get("net_case_gain")
    return {
        "report_scope": "m2_7ae_ctspc_v0_status",
        "artifact_root": str(root),
        "status": "diagnostic_experimental",
        "scorer_default": "off",
        "retain": retained,
        "retained_rule_count": retained,
        "dev_rerun_authorized": False,
        "holdout_authorized": False,
        "next_allowed_work": "audit_or_redesign_only",
        "ctspc_v0_frozen": retained == 0 and net is not None and int(net) < 0,
        "latest_dev_scorer_net_case_gain": net,
        "diagnostic": {
            "negative_dev_scorer_blocks_retain": bool(net is not None and int(net) < 0),
            "not_performance_evidence": True,
            "holdout_remains_frozen": True,
        },
    }


def evaluate(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    summary = _read_json(root / "subset_summary.json", {}) or {}
    rows = _read_jsonl(root / "subset_case_report.jsonl")
    gaps = _gap_map(root)
    retention = _read_json(root / "m27w_rule_retention.json", {}) or {}
    durable = summary.get("case_report_trace_mapping") == "prompt_user_prefix" and summary.get("case_level_gate_allowed") is True

    audited_cases: list[dict[str, Any]] = []
    for row in rows:
        if row.get("case_regressed") or row.get("case_fixed") or row.get("policy_plan_activated"):
            audited_cases.append(_case_audit(row, gaps.get(str(row.get("case_id")))))

    regressed = [case for case in audited_cases if case.get("case_regressed")]
    fixed = [case for case in audited_cases if case.get("case_fixed")]
    activated_failures = [case for case in audited_cases if case.get("policy_plan_activated") and not case.get("candidate_success")]
    source_distribution = Counter(str(case.get("regression_source")) for case in regressed)
    divergence_distribution = Counter(str(case.get("first_divergence_layer")) for case in regressed)
    ambiguous = source_distribution.get("ambiguous", 0)
    activated_missing_divergence = [case.get("case_id") for case in activated_failures if not case.get("first_divergence_layer")]
    route = _route_decision(source_distribution, ambiguous)

    report = {
        "report_scope": "m2_7ae_failure_mode_audit",
        "artifact_root": str(root),
        "durable_evidence": durable,
        "baseline_accuracy": summary.get("baseline_accuracy"),
        "candidate_accuracy": summary.get("candidate_accuracy"),
        "net_case_gain": summary.get("net_case_gain"),
        "case_report_trace_mapping": summary.get("case_report_trace_mapping"),
        "case_level_gate_allowed": summary.get("case_level_gate_allowed"),
        "case_fixed_count": len(fixed),
        "case_regressed_count": len(regressed),
        "regression_source_distribution": dict(sorted(source_distribution.items())),
        "first_divergence_layer_distribution": dict(sorted(divergence_distribution.items())),
        "ambiguous_regression_count": ambiguous,
        "activated_failure_missing_divergence_case_ids": activated_missing_divergence,
        "cases": audited_cases,
        "regression_cases": regressed,
        "fixed_cases": fixed,
        "m27ae_failure_mode_audit_passed": bool(durable and len(regressed) == int(summary.get("case_regressed_count") or len(regressed)) and len(fixed) == int(summary.get("case_fixed_count") or len(fixed)) and not activated_missing_divergence),
        "m27ae_route_decision_ready": True,
        "route_decision": route,
        "diagnostic": {
            "no_bfcl_or_model_call": True,
            "do_not_rerun_dev_or_holdout": True,
            "recommended_next_work": route,
        },
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7ae Failure-Mode Audit",
        "",
        f"- Passed: `{report['m27ae_failure_mode_audit_passed']}`",
        f"- Durable evidence: `{report['durable_evidence']}`",
        f"- Baseline/Candidate accuracy: `{report['baseline_accuracy']}` / `{report['candidate_accuracy']}`",
        f"- Net case gain: `{report['net_case_gain']}`",
        f"- Regression sources: `{report['regression_source_distribution']}`",
        f"- First divergence layers: `{report['first_divergence_layer_distribution']}`",
        f"- Route decision: `{report['route_decision']}`",
        "",
        "## Regression Cases",
    ]
    for case in report.get("regression_cases", []):
        lines.append(
            f"- `{case['case_id']}` source=`{case['regression_source']}` "
            f"divergence=`{case['first_divergence_layer']}` repairs=`{case['repair_kinds']}`"
        )
    lines.extend(["", "This is an offline audit only. It does not authorize dev, holdout, 100-case, M2.8, or full BFCL scorer runs.", ""])
    return "\n".join(lines)


def render_ablation_markdown(report: dict[str, Any]) -> str:
    lines = ["# M2.7ae Ablation Matrix Manifest", "", "Offline plan only; no scorer commands are emitted.", ""]
    for item in report["ablation_variants"]:
        lines.append(f"- `{item['ablation_id']}`: {item['expected_diagnostic_question']}")
    lines.append("")
    return "\n".join(lines)


def render_status_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# CTSPC-v0 Status",
        "",
        f"- Status: `{report['status']}`",
        f"- Frozen: `{report['ctspc_v0_frozen']}`",
        f"- Scorer default: `{report['scorer_default']}`",
        f"- Retained rules: `{report['retained_rule_count']}`",
        f"- Dev rerun authorized: `{report['dev_rerun_authorized']}`",
        f"- Holdout authorized: `{report['holdout_authorized']}`",
        f"- Next allowed work: `{report['next_allowed_work']}`",
        "",
    ])

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--ablation-output", type=Path, default=ABLATION_OUT)
    parser.add_argument("--ablation-markdown-output", type=Path, default=ABLATION_MD)
    parser.add_argument("--status-output", type=Path, default=STATUS_OUT)
    parser.add_argument("--status-markdown-output", type=Path, default=STATUS_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    report = evaluate(args.root)
    ablation = build_ablation_manifest(args.root)
    status = build_ctspc_status(args.root, _read_json(args.root / "subset_summary.json", {}) or {}, _read_json(args.root / "m27w_rule_retention.json", {}) or {})
    _write_json(args.output, report)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    _write_json(args.ablation_output, ablation)
    args.ablation_markdown_output.write_text(render_ablation_markdown(ablation), encoding="utf-8")
    _write_json(args.status_output, status)
    args.status_markdown_output.write_text(render_status_markdown(status), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "m27ae_failure_mode_audit_passed": report.get("m27ae_failure_mode_audit_passed"),
            "m27ae_route_decision_ready": report.get("m27ae_route_decision_ready"),
            "route_decision": report.get("route_decision"),
            "regression_source_distribution": report.get("regression_source_distribution"),
            "ctspc_v0_frozen": status.get("ctspc_v0_frozen"),
            "scorer_default": status.get("scorer_default"),
            "retain": status.get("retain"),
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
