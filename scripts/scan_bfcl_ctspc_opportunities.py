#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_phase2_target_subset import (
    TARGET_ACTION_TOOLS,
    TARGET_LABELS,
    _case_number,
    _read_jsonl,
    candidate_case_infos,
)


def _candidate_generatable(row: dict[str, Any]) -> bool:
    return bool(row.get("compiler_candidate_generatable"))


def scan_opportunities(source_run_root: Path, category: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in candidate_case_infos(source_run_root, category):
        labels = set(item.get("failure_labels") or [])
        target_tools = set(item.get("target_action_tools_present") or [])
        row = {
            "case_id": item["case_id"],
            "category": category,
            "baseline_success": not bool(item.get("failure_bonus")),
            "baseline_wrong": bool(item.get("failure_bonus")),
            "schema_source": item.get("schema_source"),
            "available_tools_in_case_schema": item.get("available_tools_in_case_schema") or [],
            "target_action_tools_present": sorted(target_tools),
            "schema_local": bool(target_tools),
            "schema_tool_present": bool(target_tools),
            "compiler_candidate_generatable": False,
            "candidate_rule_generatable": False,
            "candidate_generatable": _candidate_generatable(item),
            "failure_labels": sorted(labels),
            "failure_family_overlap": sorted(labels.intersection(TARGET_LABELS)),
            "keyword_score": int(item.get("keyword_score") or 0),
        }
        rows.append(row)
    rows.sort(
        key=lambda row: (
            not row["baseline_wrong"],
            not row["schema_local"],
            -int(row["keyword_score"]),
            _case_number(str(row["case_id"])),
        )
    )
    return rows


def select_opportunities(rows: list[dict[str, Any]], *, max_cases: int, require_baseline_wrong: bool = True) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        if require_baseline_wrong and not row.get("baseline_wrong"):
            continue
        if not row.get("schema_local"):
            continue
        selected.append(row)
        if len(selected) >= max_cases:
            break
    return selected


def summarize_opportunities(rows: list[dict[str, Any]], selected: list[dict[str, Any]]) -> dict[str, Any]:
    target_tools: Counter[str] = Counter()
    families: Counter[str] = Counter()
    schema_sources: Counter[str] = Counter()
    for row in rows:
        schema_sources[str(row.get("schema_source") or "unknown")] += 1
        if row.get("schema_local"):
            target_tools.update(str(tool) for tool in row.get("target_action_tools_present") or [])
        for label in row.get("failure_labels") or []:
            families[str(label)] += 1
    return {
        "total_cases": len(rows),
        "baseline_wrong_count": sum(row.get("baseline_wrong") is True for row in rows),
        "schema_local_case_count": sum(row.get("schema_local") is True for row in rows),
        "schema_tool_present_count": sum(row.get("schema_tool_present") is True for row in rows),
        "compiler_candidate_generatable_count": sum(row.get("compiler_candidate_generatable") is True for row in rows),
        "candidate_rule_generatable_count": sum(row.get("candidate_rule_generatable") is True for row in rows),
        "candidate_generatable_count": sum(row.get("candidate_generatable") is True for row in rows),
        "selected_case_count": len(selected),
        "selected_case_ids": [row["case_id"] for row in selected],
        "cases_by_target_tool": dict(sorted(target_tools.items())),
        "cases_by_failure_family": dict(sorted(families.items())),
        "overlap_with_ACTIONABLE_NO_TOOL_DECISION": sum(
            "(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)" in set(row.get("failure_labels") or []) for row in rows
        ),
        "overlap_with_POST_TOOL_PROSE_SUMMARY": sum(
            "(POST_TOOL,POST_TOOL_PROSE_SUMMARY)" in set(row.get("failure_labels") or []) for row in rows
        ),
        "schema_source_distribution": dict(sorted(schema_sources.items())),
        "schema_selection_ready": len(selected) >= 30,
        "selection_ready": len(selected) >= 30,
        "paired_execution_ready": False,
    }


def render_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# BFCL CTSPC Opportunity Scan",
        "",
        f"- Total cases: `{summary['total_cases']}`",
        f"- Baseline wrong: `{summary['baseline_wrong_count']}`",
        f"- Schema-local cases: `{summary['schema_local_case_count']}`",
        f"- Schema tool present cases: `{summary['schema_tool_present_count']}`",
        f"- Compiler candidate-generatable cases: `{summary['compiler_candidate_generatable_count']}`",
        f"- Candidate rule-generatable cases: `{summary['candidate_rule_generatable_count']}`",
        f"- Selected cases: `{summary['selected_case_count']}`",
        f"- Selection ready: `{summary['selection_ready']}`",
        "",
        "## Target Tools",
        "",
    ]
    for tool, count in (summary.get("cases_by_target_tool") or {}).items():
        lines.append(f"- `{tool}`: `{count}`")
    lines.extend(["", "## Selected Cases", ""])
    for case_id in summary.get("selected_case_ids") or []:
        lines.append(f"- `{case_id}`")
    return "\n".join(lines) + "\n"


def write_outputs(out_root: Path, rows: list[dict[str, Any]], selected: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    with (out_root / "scan_report.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (out_root / "selected_cases.jsonl").open("w", encoding="utf-8") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out_root / "scan_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_root / "category_opportunity_table.md").write_text(render_summary(summary), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan BFCL artifacts for CTSPC opportunity cases without running BFCL.")
    parser.add_argument("--source-run-root", type=Path, required=True)
    parser.add_argument("--category", default="multi_turn_miss_param")
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--max-cases", type=int, default=30)
    parser.add_argument("--allow-correct-baseline", action="store_true")
    args = parser.parse_args()

    rows = scan_opportunities(args.source_run_root, args.category)
    selected = select_opportunities(rows, max_cases=args.max_cases, require_baseline_wrong=not args.allow_correct_baseline)
    summary = summarize_opportunities(rows, selected)
    write_outputs(args.out_root, rows, selected, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
