#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_OUTPUT = DEFAULT_ROOT / "m27r_rule_retention.json"
DEFAULT_MD = DEFAULT_ROOT / "m27r_rule_retention.md"


def _read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def decide_rule(rule: dict[str, Any]) -> tuple[str, str]:
    activation = int(rule.get("activation_count") or 0)
    fixed = int(rule.get("fixed_count") or 0)
    regressed = int(rule.get("regressed_count") or 0)
    net = int(rule.get("net_case_gain") or 0)
    tool_rate = float(rule.get("tool_match_rate") or 0.0)
    arg_rate = float(rule.get("arg_match_rate") or 0.0)
    trajectory_fails = int(rule.get("trajectory_fail_count") or 0)
    if activation <= 0:
        return "reject", "no_activation_evidence"
    if regressed > 0 and net <= 0:
        return "reject", "regression_without_positive_net_gain"
    if net <= 0:
        return "reject", "no_positive_net_case_gain"
    if tool_rate < 0.6:
        return "reject", "tool_match_rate_below_retention_floor"
    if arg_rate < 0.6:
        return "reject", "arg_match_rate_below_retention_floor"
    if trajectory_fails > fixed:
        return "reject", "trajectory_failures_exceed_fixed_cases"
    if net > 0 and regressed == 0:
        return "retain", "positive_net_gain_with_low_regression_and_alignment_floor_met"
    return "demote", "mixed_local_signal_requires_revalidation"


def evaluate_rule_retention(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    summary = _read_json(root / "subset_summary.json", default={})
    case_rows = _read_jsonl(root / "subset_case_report.jsonl")
    report = _read_json(root / "m27f_rule_level_report.json", default={})
    selected_count = len(case_rows) or int(summary.get("selected_case_count") or 0)
    rules_out: list[dict[str, Any]] = []
    decisions: Counter[str] = Counter()
    for rule in report.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        decision, reason = decide_rule(rule)
        activated_ids = [str(case_id) for case_id in rule.get("activated_case_ids") or []]
        item = {
            "rule_id": rule.get("rule_id"),
            "activation_count": int(rule.get("activation_count") or len(activated_ids)),
            "fixed_count": int(rule.get("fixed_count") or 0),
            "regressed_count": int(rule.get("regressed_count") or 0),
            "net_case_gain": int(rule.get("net_case_gain") or 0),
            "tool_match_rate": float(rule.get("tool_match_rate") or 0.0),
            "arg_match_rate": float(rule.get("arg_match_rate") or 0.0),
            "trajectory_fail_count": int(rule.get("trajectory_fail_count") or 0),
            "not_activated_count": max(0, selected_count - int(rule.get("activation_count") or len(activated_ids))),
            "decision": decision,
            "reason": reason,
            "activated_case_ids": activated_ids,
        }
        decisions[decision] += 1
        rules_out.append(item)
    retained = decisions.get("retain", 0)
    report_out = {
        "report_scope": "m2_7r_rule_retention",
        "artifact_root": str(root),
        "source_rule_report": str(root / "m27f_rule_level_report.json"),
        "selected_case_count": selected_count,
        "case_report_trace_mapping": summary.get("case_report_trace_mapping"),
        "case_level_gate_allowed": summary.get("case_level_gate_allowed"),
        "rule_count": len(rules_out),
        "rules": rules_out,
        "decision_distribution": {key: decisions.get(key, 0) for key in ("retain", "demote", "reject")},
        "m27r_rule_retention_ready": bool(rules_out) and all(rule.get("decision") and rule.get("reason") for rule in rules_out),
        "diagnostic": {
            "current_rules_enter_retained_policy": retained > 0,
            "retain_requires_positive_net_gain_and_alignment_floor": True,
            "no_bfcl_rerun": True,
        },
    }
    return report_out


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7r Rule Retention",
        "",
        f"- Ready: `{report.get('m27r_rule_retention_ready')}`",
        f"- Decision distribution: `{report.get('decision_distribution')}`",
        "",
        "| Rule | Activations | Fixed | Regressed | Net | Tool Match | Arg Match | Traj Fails | Not Activated | Decision | Reason |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for rule in report.get("rules") or []:
        lines.append(
            f"| `{rule['rule_id']}` | {rule['activation_count']} | {rule['fixed_count']} | {rule['regressed_count']} | {rule['net_case_gain']} | {rule['tool_match_rate']} | {rule['arg_match_rate']} | {rule['trajectory_fail_count']} | {rule['not_activated_count']} | `{rule['decision']}` | `{rule['reason']}` |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose M2.7r rule retention decisions.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_rule_retention(args.root)
    _write_json(args.output, report)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "rule_count": report.get("rule_count"),
            "decision_distribution": report.get("decision_distribution"),
            "m27r_rule_retention_ready": report.get("m27r_rule_retention_ready"),
            "current_rules_enter_retained_policy": report.get("diagnostic", {}).get("current_rules_enter_retained_policy"),
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
