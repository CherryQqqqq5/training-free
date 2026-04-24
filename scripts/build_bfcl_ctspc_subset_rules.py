#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_phase2_target_subset import (
    TARGET_ACTION_TOOLS,
    _compile_subset_rules,
    _mined_policy_signals_by_case,
    _read_jsonl,
    candidate_policy_tool_distribution,
    materialize_selected_traces,
    prune_rule_policy_tools,
    rules_have_ctspc_actions,
)


def _load_selected_cases(path: Path) -> list[dict[str, Any]]:
    rows = _read_jsonl(path)
    return [row for row in rows if isinstance(row.get("case_id"), str)]


def _selected_schema_tools(rows: list[dict[str, Any]]) -> set[str]:
    tools: set[str] = set()
    for row in rows:
        for tool in row.get("target_action_tools_present") or []:
            if isinstance(tool, str) and tool in TARGET_ACTION_TOOLS:
                tools.add(tool)
    return tools


def _schema_local_case_count(rows: list[dict[str, Any]]) -> int:
    return sum(bool(row.get("target_action_tools_present")) for row in rows)


def _compiler_candidate_case_count(failures_path: Path, selected_tools: set[str]) -> int:
    signals = _mined_policy_signals_by_case(failures_path)
    count = 0
    for entry in signals.values():
        recommended = set(entry.get("mined_recommended_tools_before_prune") or [])
        candidates = set(entry.get("mined_action_candidates_before_prune") or [])
        if recommended.union(candidates).intersection(selected_tools):
            count += 1
    return count


def _rules_schema_local(rule_path: Path, selected_tools: set[str]) -> bool:
    distribution = candidate_policy_tool_distribution(rule_path)
    if not distribution:
        return False
    rule_tools = set(distribution)
    return rule_tools.issubset(TARGET_ACTION_TOOLS) and rule_tools.issubset(selected_tools)


def _render_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# BFCL CTSPC Subset Rule Summary",
        "",
        f"- Selected cases: `{summary['selected_case_count']}`",
        f"- Schema-local cases: `{summary['schema_local_case_count']}`",
        f"- Compiler candidate-generatable cases: `{summary['compiler_candidate_generatable_count']}`",
        f"- Kept action candidates: `{summary['kept_action_candidate_count']}`",
        f"- Candidate rules have CTSPC actions: `{summary['candidate_rules_have_ctspc_actions']}`",
        f"- Candidate rules schema-local: `{summary['candidate_rules_schema_local']}`",
        f"- Gate passed: `{summary['gate_passed']}`",
        "",
        "## Candidate Policy Tool Distribution",
        "",
    ]
    distribution = summary.get("candidate_policy_tool_distribution") or {}
    if not distribution:
        lines.append("- none")
    for tool, count in distribution.items():
        lines.append(f"- `{tool}`: `{count}`")
    return "\n".join(lines) + "\n"


def build_candidate_rule_summary(
    *,
    selected_cases: list[dict[str, Any]],
    out_rules: Path,
    compile_status: dict[str, Any] | None = None,
    selected_trace_manifest: dict[str, Any] | None = None,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    selected_tools = _selected_schema_tools(selected_cases)
    rule_path = out_rules / "rule.yaml"
    failures_path = out_rules / "failures.jsonl"
    prune_result = {}
    if compile_status and isinstance(compile_status.get("policy_tool_prune"), dict):
        prune_result = compile_status.get("policy_tool_prune") or {}
    kept_action_candidate_count = int(prune_result.get("kept_action_candidate_count") or 0)
    compiler_candidate_count = _compiler_candidate_case_count(failures_path, selected_tools) if failures_path.exists() else 0
    candidate_rules_have_ctspc_actions = rules_have_ctspc_actions(rule_path)
    candidate_rules_schema_local = _rules_schema_local(rule_path, selected_tools)
    summary = {
        "selected_case_count": len(selected_cases),
        "schema_local_case_count": _schema_local_case_count(selected_cases),
        "schema_tool_present_count": _schema_local_case_count(selected_cases),
        "compiler_candidate_generatable_count": compiler_candidate_count,
        "candidate_rule_generatable_count": kept_action_candidate_count,
        "kept_action_candidate_count": kept_action_candidate_count,
        "selected_schema_tools": sorted(selected_tools),
        "candidate_rules_available": rule_path.exists(),
        "candidate_rules_have_ctspc_actions": candidate_rules_have_ctspc_actions,
        "candidate_rules_schema_local": candidate_rules_schema_local,
        "candidate_policy_tool_distribution": candidate_policy_tool_distribution(rule_path),
        "compile_status": compile_status or {},
        "selected_trace_manifest": selected_trace_manifest or {},
        "failure_reason": failure_reason,
    }
    summary["gate_passed"] = (
        summary["selected_case_count"] == 30
        and summary["schema_local_case_count"] == 30
        and summary["compiler_candidate_generatable_count"] >= 20
        and summary["kept_action_candidate_count"] >= 20
        and summary["candidate_rules_have_ctspc_actions"] is True
        and summary["candidate_rules_schema_local"] is True
    )
    return summary


def write_summary(out_rules: Path, summary: dict[str, Any]) -> None:
    out_rules.mkdir(parents=True, exist_ok=True)
    (out_rules / "candidate_rule_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_rules / "candidate_rule_summary.md").write_text(_render_summary(summary), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build schema-local CTSPC rules for a selected BFCL subset without running BFCL.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-run-root", type=Path, required=True)
    parser.add_argument("--selected-cases", type=Path, required=True)
    parser.add_argument("--category", default="multi_turn_miss_param")
    parser.add_argument("--out-rules", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    source_run_root = args.source_run_root if args.source_run_root.is_absolute() else (repo / args.source_run_root).resolve()
    selected_cases_path = args.selected_cases if args.selected_cases.is_absolute() else (repo / args.selected_cases).resolve()
    out_rules = args.out_rules if args.out_rules.is_absolute() else (repo / args.out_rules).resolve()
    selected_cases = _load_selected_cases(selected_cases_path)
    selected_ids = [str(row["case_id"]) for row in selected_cases]
    selected_trace_manifest: dict[str, Any] = {}
    compile_status: dict[str, Any] = {}
    failure_reason: str | None = None

    try:
        selected_trace_manifest = materialize_selected_traces(
            source_run_root=source_run_root,
            category=args.category,
            selected_ids=selected_ids,
            out_dir=out_rules / "source_selected_traces",
        )
        compile_status = _compile_subset_rules(
            repo,
            out_rules / "source_selected_traces",
            out_rules,
            out_rules / "logs",
        )
        selected_tools = _selected_schema_tools(selected_cases)
        selected_prune = prune_rule_policy_tools(out_rules / "rule.yaml", allowed_tools=selected_tools)
        compile_status["selected_schema_policy_tool_prune"] = selected_prune
        if isinstance(compile_status.get("policy_tool_prune"), dict):
            compile_status["policy_tool_prune"] = selected_prune
        (out_rules / "compile_status.json").write_text(
            json.dumps(compile_status, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        failure_reason = str(exc)

    summary = build_candidate_rule_summary(
        selected_cases=selected_cases,
        out_rules=out_rules,
        compile_status=compile_status,
        selected_trace_manifest=selected_trace_manifest,
        failure_reason=failure_reason,
    )
    write_summary(out_rules, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if failure_reason:
        raise SystemExit(1)
    if not summary["gate_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
