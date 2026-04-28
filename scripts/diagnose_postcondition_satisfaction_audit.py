#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_PROTOCOL = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk/postcondition_guided_dev_smoke_protocol.json")
DEFAULT_RESULT = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk/postcondition_guided_dev_smoke_result.json")
DEFAULT_OUT = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk/postcondition_satisfaction_audit.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk/postcondition_satisfaction_audit.md")
SATISFACTION_KEYS = {
    "diff_lines",
    "matching_lines",
    "last_lines",
    "current_directory_content",
    "sorted_content",
    "content",
    "result",
}
WEAK_KEYS = {"current_working_directory", "matches", "files", "entries"}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _tool_json_objects(request: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in request.get("messages") or []:
        if not isinstance(msg, dict) or msg.get("role") != "tool":
            continue
        content = msg.get("content")
        if not isinstance(content, str):
            continue
        try:
            parsed = json.loads(content)
        except Exception:
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def _keys(objs: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for obj in objs:
        keys.update(str(k) for k in obj.keys())
    return keys


def _classify(case: dict[str, Any], protocol: dict[str, Any], result_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    trace_path = Path(str(protocol["trace_root"])) / str(case["trace_relative_path"])
    trace = _load_json(trace_path)
    request = trace.get("request") if isinstance(trace, dict) else {}
    tool_objs = _tool_json_objects(request if isinstance(request, dict) else {})
    observed_keys = sorted(_keys(tool_objs))
    satisfaction = sorted(set(observed_keys).intersection(SATISFACTION_KEYS))
    weak = sorted(set(observed_keys).intersection(WEAK_KEYS))
    result = result_by_id.get(str(case.get("candidate_id")), {})
    if satisfaction:
        label = "postcondition_already_satisfied_or_terminal_evidence_present"
    elif weak and case.get("runtime_plan_activated"):
        label = "postcondition_ambiguous_prior_observation_weak"
    elif case.get("runtime_plan_activated"):
        label = "postcondition_unmet_candidate"
    else:
        label = "runtime_scope_mismatch_diagnostic_inactive"
    return {
        "candidate_id": case.get("candidate_id"),
        "postcondition_gap": case.get("postcondition_gap"),
        "runtime_plan_activated": bool(case.get("runtime_plan_activated")),
        "runtime_plan_selected_tool": case.get("runtime_plan_selected_tool"),
        "runtime_plan_blocked_reason": case.get("runtime_plan_blocked_reason"),
        "observed_tool_output_keys": observed_keys,
        "satisfaction_witness_keys": satisfaction,
        "weak_observation_keys": weak,
        "candidate_tool_call_count": len(result.get("candidate_tool_calls") or []),
        "baseline_tool_call_count": len(result.get("baseline_tool_calls") or []),
        "postcondition_satisfaction_label": label,
        "recommended_action": "reject_from_positive_smoke_until_gap_filter_fixed" if satisfaction else "keep_for_manual_gap_review",
    }


def evaluate(protocol_path: Path = DEFAULT_PROTOCOL, result_path: Path = DEFAULT_RESULT) -> dict[str, Any]:
    protocol = _load_json(protocol_path)
    result = _load_json(result_path)
    result_by_id = {str(row.get("candidate_id")): row for row in result.get("case_results") or [] if isinstance(row, dict)}
    records = [_classify(case, protocol, result_by_id) for case in protocol.get("selected_smoke_cases") or []]
    distribution = Counter(row["postcondition_satisfaction_label"] for row in records)
    already = int(distribution.get("postcondition_already_satisfied_or_terminal_evidence_present", 0))
    strong_unmet = int(distribution.get("postcondition_unmet_candidate", 0))
    return {
        "report_scope": "postcondition_satisfaction_audit",
        "bfcl_scorer_run": False,
        "holdout_run": False,
        "does_not_authorize_retain_or_sota_claim": True,
        "protocol_path": str(protocol_path),
        "smoke_result_path": str(result_path),
        "case_count": len(records),
        "runtime_activated_case_count": sum(int(row["runtime_plan_activated"]) for row in records),
        "postcondition_already_satisfied_count": already,
        "postcondition_unmet_strong_count": strong_unmet,
        "postcondition_ambiguous_or_inactive_count": len(records) - already - strong_unmet,
        "satisfaction_label_distribution": dict(sorted(distribution.items())),
        "candidate_mining_gap_filter_passed": strong_unmet > 0 and already == 0,
        "recommended_next_action": "fix_postcondition_candidate_mining_satisfaction_filter_before_any_rerun",
        "no_dev_rerun_recommended": True,
        "do_not_strengthen_to_exact_tool_choice": True,
        "candidate_commands": [],
        "planned_commands": [],
        "case_records": records,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Postcondition Satisfaction Audit",
        "",
        f"- Cases: `{report['case_count']}`",
        f"- Runtime activated cases: `{report['runtime_activated_case_count']}`",
        f"- Already satisfied / terminal evidence present: `{report['postcondition_already_satisfied_count']}`",
        f"- Strong unmet candidates: `{report['postcondition_unmet_strong_count']}`",
        f"- Candidate mining gap filter passed: `{report['candidate_mining_gap_filter_passed']}`",
        f"- Recommended next action: `{report['recommended_next_action']}`",
        f"- Does not authorize retain/SOTA claim: `{report['does_not_authorize_retain_or_sota_claim']}`",
        "",
        "| Label | Count |",
        "| --- | ---: |",
    ]
    for label, count in report["satisfaction_label_distribution"].items():
        lines.append(f"| {label} | {count} |")
    lines.extend(["", "No raw prompts, raw responses, scorer trees, or BFCL result trees are included.", ""])
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], out: Path, md: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md.write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.protocol, args.result)
    write_outputs(report, args.output, args.markdown_output)
    if args.compact:
        keys = [
            "case_count",
            "runtime_activated_case_count",
            "postcondition_already_satisfied_count",
            "postcondition_unmet_strong_count",
            "postcondition_ambiguous_or_inactive_count",
            "candidate_mining_gap_filter_passed",
            "recommended_next_action",
            "candidate_commands",
            "planned_commands",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
