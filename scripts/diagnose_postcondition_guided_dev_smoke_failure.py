#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_RESULT = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk/postcondition_guided_dev_smoke_result.json")
DEFAULT_OUT = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk/postcondition_guided_dev_smoke_failure_diagnosis.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk/postcondition_guided_dev_smoke_failure_diagnosis.md")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _message_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") if isinstance(response, dict) else None
    if not isinstance(choices, list) or not choices:
        return ""
    msg = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content")
    return content if isinstance(content, str) else ""


def _raw_for_case(result: dict[str, Any]) -> dict[str, Any]:
    path = result.get("raw_trace_path")
    if not isinstance(path, str) or not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return _load_json(p)
    except Exception:
        return {}


def classify_case(result: dict[str, Any]) -> dict[str, Any]:
    raw = _raw_for_case(result)
    baseline_raw = ((raw.get("baseline") or {}).get("raw_response") if isinstance(raw, dict) else {}) or {}
    candidate_raw = ((raw.get("candidate") or {}).get("raw_response") if isinstance(raw, dict) else {}) or {}
    baseline_content = _message_content(baseline_raw)
    candidate_content = _message_content(candidate_raw)
    activated = bool(result.get("policy_plan_activated"))
    candidate_tool_calls = list(result.get("candidate_tool_calls") or [])
    baseline_tool_calls = list(result.get("baseline_tool_calls") or [])
    if not activated:
        source = "runtime_scope_mismatch_diagnostic_inactive"
    elif not candidate_tool_calls:
        source = "model_ignored_soft_guidance_or_gap_overestimated"
    elif result.get("candidate_recommended_tool_match") is not True:
        source = "candidate_tool_not_recommended_family"
    elif result.get("case_fixed"):
        source = "candidate_progressed_recommended_tool"
    else:
        source = "no_measurable_delta"
    return {
        "candidate_id": result.get("candidate_id"),
        "postcondition_gap": result.get("postcondition_gap"),
        "policy_plan_activated": activated,
        "policy_selected_tool": result.get("policy_selected_tool"),
        "baseline_tool_call_count": len(baseline_tool_calls),
        "candidate_tool_call_count": len(candidate_tool_calls),
        "candidate_recommended_tool_match": bool(result.get("candidate_recommended_tool_match")),
        "case_fixed": bool(result.get("case_fixed")) if activated else False,
        "case_regressed": bool(result.get("case_regressed")) if activated else False,
        "baseline_finish_reason": result.get("baseline_finish_reason"),
        "candidate_finish_reason": result.get("candidate_finish_reason"),
        "baseline_text_response_present": bool(baseline_content.strip()),
        "candidate_text_response_present": bool(candidate_content.strip()),
        "failure_source": source,
    }


def evaluate(result_path: Path = DEFAULT_RESULT) -> dict[str, Any]:
    result = _load_json(result_path)
    cases = [classify_case(row) for row in result.get("case_results") or []]
    distribution = Counter(str(row["failure_source"]) for row in cases)
    activated = [row for row in cases if row["policy_plan_activated"]]
    no_tool_activated = [row for row in activated if row["candidate_tool_call_count"] == 0]
    diagnosis_passed = bool(result.get("stop_loss_passed"))
    return {
        "report_scope": "postcondition_guided_dev_smoke_failure_diagnosis",
        "bfcl_scorer_run": False,
        "holdout_run": False,
        "does_not_authorize_retain_or_sota_claim": True,
        "source_result_path": str(result_path),
        "smoke_stop_loss_passed": bool(result.get("stop_loss_passed")),
        "case_count": len(cases),
        "activated_case_count": len(activated),
        "diagnostic_inactive_case_count": sum(1 for row in cases if not row["policy_plan_activated"]),
        "activated_candidate_no_tool_count": len(no_tool_activated),
        "failure_source_distribution": dict(sorted(distribution.items())),
        "primary_failure_source": "model_ignored_soft_guidance_or_postcondition_gap_overestimated" if len(no_tool_activated) else "runtime_scope_mismatch_or_other",
        "recommended_next_action": "postcondition_satisfaction_audit_before_any_rerun" if not diagnosis_passed else "interpret_as_first_signal_only",
        "no_dev_rerun_until_postcondition_satisfaction_audit": not diagnosis_passed,
        "do_not_strengthen_to_exact_tool_choice": True,
        "do_not_create_arguments": True,
        "case_diagnoses": cases,
        "candidate_commands": [],
        "planned_commands": [],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Postcondition-Guided Dev Smoke Failure Diagnosis",
        "",
        f"- BFCL scorer run: `{report['bfcl_scorer_run']}`",
        f"- Stop-loss passed: `{report['smoke_stop_loss_passed']}`",
        f"- Activated cases: `{report['activated_case_count']}`",
        f"- Diagnostic inactive cases: `{report['diagnostic_inactive_case_count']}`",
        f"- Activated candidate no-tool count: `{report['activated_candidate_no_tool_count']}`",
        f"- Primary failure source: `{report['primary_failure_source']}`",
        f"- Recommended next action: `{report['recommended_next_action']}`",
        f"- Does not authorize retain/SOTA claim: `{report['does_not_authorize_retain_or_sota_claim']}`",
        "",
        "| Failure source | Count |",
        "| --- | ---: |",
    ]
    for source, count in report["failure_source_distribution"].items():
        lines.append(f"| {source} | {count} |")
    lines.extend(["", "No raw prompts, raw responses, scorer trees, or BFCL result trees are included in this compact artifact.", ""])
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], out: Path, md: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md.write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.result)
    write_outputs(report, args.output, args.markdown_output)
    if args.compact:
        keys = [
            "smoke_stop_loss_passed",
            "case_count",
            "activated_case_count",
            "diagnostic_inactive_case_count",
            "activated_candidate_no_tool_count",
            "failure_source_distribution",
            "primary_failure_source",
            "recommended_next_action",
            "candidate_commands",
            "planned_commands",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
