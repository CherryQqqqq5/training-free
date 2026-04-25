#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scripts.check_m27i_guard_preflight import DEFAULT_ARTIFACT_ROOT, evaluate_guard_preflight  # noqa: E402
from scripts.check_m27l_trace_completeness_preflight import evaluate_m27l_trace_completeness  # noqa: E402

DEFAULT_OUTPUT = DEFAULT_ARTIFACT_ROOT / "m27m_guidance_only_readiness.json"
DEFAULT_MARKDOWN_OUTPUT = DEFAULT_ARTIFACT_ROOT / "m27m_guidance_only_readiness.md"


def _tool_choice_matches_selected(tool_choice: Any, selected_tool: str | None) -> bool:
    if not selected_tool or not isinstance(tool_choice, dict):
        return False
    function = tool_choice.get("function") if isinstance(tool_choice.get("function"), dict) else {}
    return tool_choice.get("type") == "function" and function.get("name") == selected_tool


def _coverage(preflight: dict[str, Any]) -> dict[str, Any]:
    accepted_count = 0
    guidance_count = 0
    exact_count = 0
    trajectory_sensitive_exact_cases: list[str] = []
    trajectory_sensitive_tools = {str(item) for item in preflight.get("exact_tool_choice_trajectory_sensitive_tools") or []}
    if not trajectory_sensitive_tools:
        trajectory_sensitive_tools = {"cat", "touch", "mkdir"}
    for case in preflight.get("cases") or []:
        plan = case.get("after_guard_plan") if isinstance(case.get("after_guard_plan"), dict) else {}
        candidate = plan.get("selected_action_candidate") if isinstance(plan.get("selected_action_candidate"), dict) else None
        selected_tool = str(plan.get("selected_tool") or "")
        if not plan.get("activated") or not candidate:
            continue
        accepted_count += 1
        patches = [str(item) for item in plan.get("request_patches") or []]
        if any(item.startswith("prompt_injector:Policy selected next tool:") for item in patches):
            guidance_count += 1
        if _tool_choice_matches_selected(plan.get("patched_tool_choice"), selected_tool):
            exact_count += 1
            if selected_tool in trajectory_sensitive_tools:
                trajectory_sensitive_exact_cases.append(str(case.get("case_id") or ""))
    return {
        "accepted_activated_candidate_count": accepted_count,
        "action_specific_guidance_count": guidance_count,
        "exact_tool_choice_count": exact_count,
        "action_specific_guidance_coverage": guidance_count / accepted_count if accepted_count else 0.0,
        "exact_tool_choice_coverage": exact_count / accepted_count if accepted_count else 0.0,
        "trajectory_sensitive_exact_forcing_count": len(trajectory_sensitive_exact_cases),
        "trajectory_sensitive_exact_forcing_cases": sorted(case for case in trajectory_sensitive_exact_cases if case),
    }


def _regressed_exact_cases(preflight: dict[str, Any], trajectory_sensitive_cases: list[str]) -> list[str]:
    regressed = set((preflight.get("regressed_cases_guard_status") or {}).keys())
    return sorted(case for case in trajectory_sensitive_cases if case in regressed)


def _guidance_first_failed(report: dict[str, Any]) -> str | None:
    if report.get("exact_next_tool_choice_mode") != "guidance_only":
        return "exact_next_tool_choice_mode"
    if not report.get("m2_7i_guard_preflight_passed"):
        return "m2_7i_guard_preflight_passed"
    if report.get("action_specific_guidance_coverage") != 1.0:
        return "action_specific_guidance_coverage"
    if report.get("exact_tool_choice_coverage") != 0.0:
        return "exact_tool_choice_coverage"
    if int(report.get("trajectory_sensitive_exact_forcing_count") or 0) != 0:
        return "trajectory_sensitive_exact_forcing_count"
    after_count = int(report.get("plan_activated_count_after_guard") or 0)
    if after_count < 10:
        return "plan_activated_count_after_guard_min"
    if after_count > 20:
        return "plan_activated_count_after_guard_max"
    if float(report.get("dominant_selected_next_tool_rate_after_guard") or 0.0) > 0.8:
        return "dominant_selected_next_tool_rate_after_guard"
    return None


def summarize_guidance_only_readiness(
    *,
    guard_preflight: dict[str, Any],
    trace_preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trace_preflight = trace_preflight or {}
    coverage = _coverage(guard_preflight)
    regressed_exact = _regressed_exact_cases(guard_preflight, coverage["trajectory_sensitive_exact_forcing_cases"])
    report: dict[str, Any] = {
        "title": "M2.7m Guidance-Only Readiness",
        "selected_case_count": guard_preflight.get("selected_case_count"),
        "m2_7m_trace_completeness_passed": trace_preflight.get("m2_7l_trace_completeness_passed"),
        "case_level_gate_allowed": trace_preflight.get("case_level_gate_allowed"),
        "missing_trace_ids": trace_preflight.get("missing_trace_ids") or {},
        "m2_7i_guard_preflight_passed": guard_preflight.get("m2_7i_guard_preflight_passed"),
        "exact_next_tool_choice_mode": guard_preflight.get("exact_next_tool_choice_mode"),
        "exact_tool_choice_trajectory_sensitive_tools": guard_preflight.get("exact_tool_choice_trajectory_sensitive_tools") or [],
        "plan_activated_count_after_guard": guard_preflight.get("plan_activated_count_after_guard"),
        "dominant_selected_next_tool_rate_after_guard": guard_preflight.get("dominant_selected_next_tool_rate_after_guard"),
        "selected_next_tool_distribution_after_guard": guard_preflight.get("selected_next_tool_distribution_after_guard") or {},
        "regressed_exact_forcing_cases": regressed_exact,
        **coverage,
    }
    guidance_failed = _guidance_first_failed(report)
    trace_passed = bool(report.get("m2_7m_trace_completeness_passed"))
    report["m2_7m_guidance_only_readiness_passed"] = guidance_failed is None
    report["m2_7m_preflight_passed"] = trace_passed and guidance_failed is None
    report["diagnostic"] = {
        "checker_scope": "m2_7m_guidance_only_readiness_no_bfcl_no_model_call",
        "first_failed_criterion": None if report["m2_7m_preflight_passed"] else ("trace_completeness" if not trace_passed else guidance_failed),
        "guidance_only_first_failed_criterion": guidance_failed,
        "trace_first_failed_criterion": (trace_preflight.get("diagnostic") or {}).get("first_failed_criterion"),
        "do_not_rerun_m2_7f_until_passed": not report["m2_7m_preflight_passed"],
        "recommended_next_focus": "trace_completeness" if not trace_passed else ("guidance_only_runtime" if guidance_failed else "m2_7f_lite_rerun_candidate"),
    }
    return report


def evaluate_guidance_only_readiness(artifact_root: Path = DEFAULT_ARTIFACT_ROOT) -> dict[str, Any]:
    trace = evaluate_m27l_trace_completeness(artifact_root)
    guard = evaluate_guard_preflight(artifact_root=artifact_root)
    return summarize_guidance_only_readiness(guard_preflight=guard, trace_preflight=trace)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7m Guidance-Only Readiness",
        "",
        f"- Combined preflight passed: `{report.get('m2_7m_preflight_passed')}`",
        f"- Trace completeness passed: `{report.get('m2_7m_trace_completeness_passed')}`",
        f"- Guidance-only readiness passed: `{report.get('m2_7m_guidance_only_readiness_passed')}`",
        f"- Exact tool-choice mode: `{report.get('exact_next_tool_choice_mode')}`",
        f"- Action-specific guidance coverage: `{report.get('action_specific_guidance_coverage')}`",
        f"- Exact tool-choice coverage: `{report.get('exact_tool_choice_coverage')}`",
        f"- Trajectory-sensitive exact forcing count: `{report.get('trajectory_sensitive_exact_forcing_count')}`",
        f"- After-guard activations: `{report.get('plan_activated_count_after_guard')}`",
        f"- Dominant selected tool rate: `{report.get('dominant_selected_next_tool_rate_after_guard')}`",
        f"- Missing trace ids: `{report.get('missing_trace_ids')}`",
        f"- First failed criterion: `{(report.get('diagnostic') or {}).get('first_failed_criterion')}`",
        "",
        "This checker is offline only. It does not call BFCL or an upstream model.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check M2.7m guidance-only readiness without BFCL/model calls.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_guidance_only_readiness(args.artifact_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        payload = {k: report.get(k) for k in (
            "m2_7m_preflight_passed",
            "m2_7m_trace_completeness_passed",
            "m2_7m_guidance_only_readiness_passed",
            "action_specific_guidance_coverage",
            "exact_tool_choice_coverage",
            "exact_next_tool_choice_mode",
            "plan_activated_count_after_guard",
            "dominant_selected_next_tool_rate_after_guard",
            "trajectory_sensitive_exact_forcing_count",
            "regressed_exact_forcing_cases",
            "missing_trace_ids",
            "diagnostic",
        )}
    else:
        payload = report
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2))
    return 0 if report.get("m2_7m_preflight_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
