#!/usr/bin/env python3
"""M2.8-pre repair stack contribution split.

Offline-only diagnostic. This separates compatibility/decision-adjacent repair
signals from CTSPC action-policy signals so the frozen CTSPC-v0 line is not used
as a scorer driver.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
OUT = DEFAULT_ROOT / "repair_stack_contribution.json"
MD = DEFAULT_ROOT / "repair_stack_contribution.md"

COMPATIBILITY_REPAIRS = {
    "resolve_contextual_string_arg",
    "repair_json",
    "coerce_types",
    "drop_unknown_key",
    "fill_default",
    "arguments_changed",
}
DECISION_ADJACENT_REPAIRS = {
    "coerce_no_tool_text_to_empty",
    "termination_to_tool_retry",
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


def classify_repair_kind(kind: str) -> str:
    if kind in COMPATIBILITY_REPAIRS:
        return "compatibility"
    if kind in DECISION_ADJACENT_REPAIRS or "no_tool" in kind or kind.startswith("termination"):
        return "decision_adjacent"
    return "unknown"


def _regression_source_map(root: Path) -> dict[str, str]:
    audit = _read_json(root / "m27ae_failure_mode_audit.json", {}) or {}
    return {str(row.get("case_id")): str(row.get("regression_source") or "ambiguous") for row in audit.get("cases") or []}


def _decision(stats: dict[str, Any]) -> str:
    fixed = int(stats.get("fixed_cases") or 0)
    regressed = int(stats.get("regressed_cases") or 0)
    net = fixed - regressed
    if regressed > fixed:
        return "disable"
    if regressed:
        return "guard"
    if net > 0:
        return "keep"
    return "guard"


def evaluate(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    rows = _read_jsonl(root / "subset_case_report.jsonl")
    summary = _read_json(root / "subset_summary.json", {}) or {}
    source_by_case = _regression_source_map(root)
    repairs: dict[str, dict[str, Any]] = {}
    repair_cases: dict[str, set[str]] = defaultdict(set)
    interaction: dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        case_id = str(row.get("case_id") or "")
        kinds = [str(k) for k in (row.get("repair_kinds") or []) if str(k).strip()]
        if not kinds:
            continue
        source = source_by_case.get(case_id) or ("action_policy" if row.get("policy_plan_activated") else "repair_policy")
        for kind in kinds:
            item = repairs.setdefault(
                kind,
                {
                    "repair_kind": kind,
                    "repair_class": classify_repair_kind(kind),
                    "enabled_cases": 0,
                    "fixed_cases": 0,
                    "regressed_cases": 0,
                    "net_case_gain": 0,
                    "interaction_with_action_policy": 0,
                    "interaction_with_repair_policy": 0,
                    "interaction_with_trajectory_continuation": 0,
                    "decision": "guard",
                    "case_ids": [],
                },
            )
            repair_cases[kind].add(case_id)
            if row.get("case_fixed"):
                item["fixed_cases"] += 1
            if row.get("case_regressed"):
                item["regressed_cases"] += 1
            interaction[kind][source] += 1

    for kind, item in repairs.items():
        item["enabled_cases"] = len(repair_cases[kind])
        item["case_ids"] = sorted(repair_cases[kind])
        item["net_case_gain"] = int(item["fixed_cases"]) - int(item["regressed_cases"])
        item["interaction_with_action_policy"] = interaction[kind].get("action_policy", 0)
        item["interaction_with_repair_policy"] = interaction[kind].get("repair_policy", 0) + interaction[kind].get("no_tool_repair", 0)
        item["interaction_with_trajectory_continuation"] = interaction[kind].get("trajectory_continuation", 0)
        item["decision"] = _decision(item)

    decisions = Counter(str(item["decision"]) for item in repairs.values())
    return {
        "report_scope": "m2_8pre_repair_stack_contribution",
        "artifact_root": str(root),
        "offline_diagnostic_only": True,
        "no_bfcl_or_model_call": True,
        "planned_commands": [],
        "candidate_commands": [],
        "latest_dev_scorer_net_case_gain": summary.get("net_case_gain"),
        "repair_kind_count": len(repairs),
        "repairs": dict(sorted(repairs.items())),
        "decision_distribution": dict(sorted(decisions.items())),
        "repair_stack_split_ready": True,
        "diagnostic": {
            "ctspc_action_policy_separated": True,
            "does_not_authorize_scorer": True,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.8-pre Repair Stack Contribution",
        "",
        f"- Ready: `{report['repair_stack_split_ready']}`",
        f"- Repair kinds: `{report['repair_kind_count']}`",
        f"- Decisions: `{report['decision_distribution']}`",
        "",
        "| Repair | Class | Enabled | Fixed | Regressed | Net | Decision |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in report.get("repairs", {}).values():
        lines.append(
            f"| `{item['repair_kind']}` | `{item['repair_class']}` | `{item['enabled_cases']}` | `{item['fixed_cases']}` | `{item['regressed_cases']}` | `{item['net_case_gain']}` | `{item['decision']}` |"
        )
    lines.extend(["", "Offline diagnostic only. No scorer commands are emitted.", ""])
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
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "repair_stack_split_ready": report.get("repair_stack_split_ready"),
            "repair_kind_count": report.get("repair_kind_count"),
            "decision_distribution": report.get("decision_distribution"),
            "planned_commands": report.get("planned_commands"),
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
