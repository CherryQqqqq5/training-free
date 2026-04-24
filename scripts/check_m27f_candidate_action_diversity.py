from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from scripts.run_phase2_target_subset import TARGET_ACTION_TOOLS, candidate_policy_tool_distribution


DEFAULT_REPORT_PATH = Path("outputs/artifacts/bfcl_ctspc_subset30_v1/subset_case_report.jsonl")
DEFAULT_RULE_PATH = Path("outputs/phase2_subset/bfcl_ctspc_subset30_v1/candidate_rules/rule.yaml")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _rule_tools_are_schema_local(rule_path: Path) -> bool:
    if not rule_path.exists():
        return False
    payload = yaml.safe_load(rule_path.read_text(encoding="utf-8")) or {}
    tools: set[str] = set()
    for rule in payload.get("rules") or []:
        policy = (((rule or {}).get("action") or {}).get("decision_policy") or {})
        for tool in policy.get("recommended_tools") or []:
            if isinstance(tool, str) and tool:
                tools.add(tool)
        next_policy = policy.get("next_tool_policy") or {}
        for tool in next_policy.get("recommended_tools") or []:
            if isinstance(tool, str) and tool:
                tools.add(tool)
        for candidate in policy.get("action_candidates") or []:
            if isinstance(candidate, dict):
                tool = candidate.get("tool")
                if isinstance(tool, str) and tool:
                    tools.add(tool)
                for rec in candidate.get("recommended_tools") or []:
                    if isinstance(rec, str) and rec:
                        tools.add(rec)
    return bool(tools) and tools.issubset(TARGET_ACTION_TOOLS)


def evaluate_candidate_action_diversity(
    report_path: Path = DEFAULT_REPORT_PATH,
    *,
    rule_path: Path = DEFAULT_RULE_PATH,
    dominant_threshold: float = 0.8,
) -> dict[str, Any]:
    rows = _read_jsonl(report_path)
    activated = [row for row in rows if row.get("policy_plan_activated") is True]
    distribution = Counter(str(row.get("selected_next_tool")) for row in activated if row.get("selected_next_tool"))
    activated_count = len(activated)
    dominant_tool, dominant_count = (None, 0)
    if distribution:
        dominant_tool, dominant_count = distribution.most_common(1)[0]
    dominant_rate = (dominant_count / activated_count) if activated_count else 0.0
    recommended_matches = sum(row.get("recommended_tool_match") is True for row in activated)
    raw_normalized_matches = sum(row.get("raw_normalized_arg_match") is True for row in activated)
    schema_local = _rule_tools_are_schema_local(rule_path)
    not_single_tool_collapsed = not (activated_count > 1 and len(distribution) == 1)
    gate_passed = bool(activated_count) and dominant_rate <= dominant_threshold and not_single_tool_collapsed and schema_local
    return {
        "case_report_path": str(report_path),
        "rule_path": str(rule_path),
        "m2_7f_candidate_action_diversity_passed": gate_passed,
        "activated_count": activated_count,
        "selected_next_tool_distribution": dict(sorted(distribution.items(), key=lambda item: (-item[1], item[0]))),
        "dominant_selected_next_tool": dominant_tool,
        "dominant_selected_next_tool_rate": dominant_rate,
        "dominant_threshold": dominant_threshold,
        "recommended_tool_match_rate_among_activated": recommended_matches / activated_count if activated_count else 0.0,
        "raw_normalized_arg_match_rate_among_activated": raw_normalized_matches / activated_count if activated_count else 0.0,
        "candidate_policy_tool_distribution": candidate_policy_tool_distribution(rule_path),
        "candidate_policy_tools_schema_local": schema_local,
        "diagnostic": {
            "do_not_rerun_m2_7f_until_passed": not gate_passed,
            "first_failed_criterion": None
            if gate_passed
            else (
                "no_activation"
                if not activated_count
                else "candidate_policy_tools_schema_local"
                if not schema_local
                else "selected_next_tool_single_tool_collapse"
                if not not_single_tool_collapsed
                else "dominant_selected_next_tool_rate"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check M2.7f candidate action diversity before rerun.")
    parser.add_argument("--case-report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--rule", type=Path, default=DEFAULT_RULE_PATH)
    parser.add_argument("--dominant-threshold", type=float, default=0.8)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_candidate_action_diversity(
        args.case_report,
        rule_path=args.rule,
        dominant_threshold=args.dominant_threshold,
    )
    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2))
    return 0 if report["m2_7f_candidate_action_diversity_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
