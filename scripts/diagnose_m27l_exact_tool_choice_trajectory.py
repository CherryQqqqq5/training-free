#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scripts.check_m27l_trace_completeness_preflight import evaluate_m27l_trace_completeness  # noqa: E402
from scripts.run_phase2_target_subset import _trace_paths_by_case_from_prompt_prefix  # noqa: E402

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_OUTPUT = DEFAULT_ROOT / "m27l_exact_tool_choice_trajectory.json"
DEFAULT_MARKDOWN_OUTPUT = DEFAULT_ROOT / "m27l_exact_tool_choice_trajectory.md"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _trace_paths(root: Path, run_name: str, category: str, selected_ids: list[str]) -> dict[str, list[Path]]:
    run_root = root / run_name
    groups = _trace_paths_by_case_from_prompt_prefix(
        source_run_root=run_root,
        category=category,
        selected_ids=selected_ids,
    )
    if groups and any(groups.get(case_id) for case_id in selected_ids):
        return {case_id: list(groups.get(case_id) or []) for case_id in selected_ids}
    return {case_id: sorted((run_root / "traces").glob(f"{case_id}*.json")) for case_id in selected_ids}


def _load_trace_payloads(paths: list[Path]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in paths:
        payload = _read_json(path)
        if payload:
            payloads.append(payload)
    return payloads


def _loads_args(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return raw
    return raw


def _tool_calls_from_trace(trace: dict[str, Any]) -> list[dict[str, Any]]:
    response = trace.get("final_response") if isinstance(trace.get("final_response"), dict) else {}
    calls: list[dict[str, Any]] = []
    for item in response.get("output") or []:
        if isinstance(item, dict) and item.get("type") in {"function_call", "tool_call"}:
            function = item.get("function") if isinstance(item.get("function"), dict) else {}
            name = item.get("name") or function.get("name")
            calls.append({"name": name, "arguments": _loads_args(item.get("arguments") or function.get("arguments"))})
    for choice in response.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            function = call.get("function") if isinstance(call.get("function"), dict) else {}
            calls.append({"name": function.get("name"), "arguments": _loads_args(function.get("arguments"))})
    return [call for call in calls if call.get("name")]


def _final_tools(traces: list[dict[str, Any]]) -> list[str]:
    tools: list[str] = []
    for trace in traces:
        calls = _tool_calls_from_trace(trace)
        tools.append(str(calls[0].get("name")) if calls else "<no_tool>")
    return tools


def _first_divergent_step(baseline_tools: list[str], candidate_tools: list[str]) -> dict[str, Any] | None:
    limit = max(len(baseline_tools), len(candidate_tools))
    for index in range(limit):
        baseline = baseline_tools[index] if index < len(baseline_tools) else "<missing>"
        candidate = candidate_tools[index] if index < len(candidate_tools) else "<missing>"
        if baseline != candidate:
            return {"step_index": index, "baseline_tool": baseline, "candidate_tool": candidate}
    return None


def _first_activated_validation(traces: list[dict[str, Any]]) -> dict[str, Any]:
    for trace in traces:
        validation = trace.get("validation") if isinstance(trace.get("validation"), dict) else {}
        if validation.get("next_tool_plan_activated") is True:
            return validation
    return {}


def _request_patches(validation: dict[str, Any]) -> list[str]:
    return [str(item) for item in validation.get("request_patches") or []]


def _trace_has_exact_tool_choice(trace: dict[str, Any], selected_tool: str | None) -> bool:
    if not selected_tool:
        return False
    for key in ("request", "request_original"):
        request = trace.get(key) if isinstance(trace.get(key), dict) else {}
        tool_choice = request.get("tool_choice")
        if isinstance(tool_choice, dict):
            function = tool_choice.get("function") if isinstance(tool_choice.get("function"), dict) else {}
            if tool_choice.get("type") == "function" and function.get("name") == selected_tool:
                return True
    return False


def _exact_tool_choice_applied(traces: list[dict[str, Any]], validation: dict[str, Any], selected_tool: str | None) -> bool:
    if any(item.startswith("tool_choice:function(policy_next_tool)=") for item in _request_patches(validation)):
        return True
    return any(_trace_has_exact_tool_choice(trace, selected_tool) for trace in traces)


def _action_guidance_applied(traces: list[dict[str, Any]], validation: dict[str, Any]) -> bool:
    if any(item.startswith("prompt_injector:Policy selected next tool:") for item in _request_patches(validation)):
        return True
    for trace in traces:
        request = trace.get("request") if isinstance(trace.get("request"), dict) else {}
        messages = request.get("messages") or request.get("input") or []
        if isinstance(messages, list):
            for message in messages:
                if isinstance(message, dict) and "Policy selected next tool:" in str(message.get("content") or ""):
                    return True
    return False


def _candidate_args(validation: dict[str, Any]) -> dict[str, Any]:
    candidate = validation.get("selected_action_candidate") if isinstance(validation.get("selected_action_candidate"), dict) else {}
    args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
    return dict(args)


def _emitted_tool_and_args(traces: list[dict[str, Any]]) -> tuple[str | None, Any]:
    for trace in traces:
        calls = _tool_calls_from_trace(trace)
        if calls:
            call = calls[0]
            return str(call.get("name")), call.get("arguments")
    return None, None


def _failure_layer(
    *,
    missing_candidate_trace: bool,
    exact_applied: bool,
    baseline_success: bool | None,
    candidate_success: bool | None,
    recommended_tool_match: bool | None,
    raw_arg_match: bool | None,
    final_arg_match: bool | None,
) -> str:
    if missing_candidate_trace:
        return "trace_mapping_incomplete"
    if exact_applied and baseline_success is True and candidate_success is False:
        return "exact_tool_choice_overconstraint"
    if recommended_tool_match is True and (raw_arg_match is True or final_arg_match is True) and candidate_success is False:
        return "local_tool_arg_match_but_trajectory_fail"
    if recommended_tool_match is False:
        return "selected_action_not_expected_trajectory"
    if raw_arg_match is False and final_arg_match is False:
        return "tool_arg_mismatch"
    if candidate_success is False:
        return "continuation_or_final_answer"
    return "aligned_or_success"


def evaluate_exact_tool_choice_trajectory(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    manifest = _read_json(root / "paired_subset_manifest.json")
    selected_ids = [str(case_id) for case_id in manifest.get("selected_case_ids") or []]
    category = str(manifest.get("category") or "multi_turn_miss_param")
    rows = _read_jsonl(root / "subset_case_report.jsonl")
    rows_by_id = {str(row.get("case_id")): row for row in rows if row.get("case_id")}
    trace_preflight = evaluate_m27l_trace_completeness(root)
    missing_trace_ids = trace_preflight.get("missing_trace_ids") if isinstance(trace_preflight.get("missing_trace_ids"), dict) else {}
    missing_candidate_trace_ids = set(str(item) for item in missing_trace_ids.get("candidate") or [])

    baseline_paths = _trace_paths(root, "baseline", category, selected_ids)
    candidate_paths = _trace_paths(root, "candidate", category, selected_ids)
    cases: list[dict[str, Any]] = []
    failure_layers: Counter[str] = Counter()
    exact_overconstraint_cases: list[str] = []
    local_match_failure_cases: list[str] = []
    exact_applied_count = 0
    guidance_applied_count = 0
    activated_count = 0

    for case_id in selected_ids:
        row = rows_by_id.get(case_id, {"case_id": case_id})
        baseline_traces = _load_trace_payloads(baseline_paths.get(case_id, []))
        candidate_traces = _load_trace_payloads(candidate_paths.get(case_id, []))
        validation = _first_activated_validation(candidate_traces)
        selected_tool = row.get("selected_next_tool") or validation.get("selected_next_tool")
        if selected_tool is not None:
            selected_tool = str(selected_tool)
        emitted_tool, emitted_args = _emitted_tool_and_args(candidate_traces)
        baseline_tools = _final_tools(baseline_traces)
        candidate_tools = _final_tools(candidate_traces)
        exact_applied = _exact_tool_choice_applied(candidate_traces, validation, selected_tool)
        guidance_applied = _action_guidance_applied(candidate_traces, validation)
        if row.get("policy_plan_activated") is True or validation:
            activated_count += 1
        if exact_applied:
            exact_applied_count += 1
        if guidance_applied:
            guidance_applied_count += 1
        layer = _failure_layer(
            missing_candidate_trace=case_id in missing_candidate_trace_ids,
            exact_applied=exact_applied,
            baseline_success=row.get("baseline_success"),
            candidate_success=row.get("candidate_success"),
            recommended_tool_match=row.get("recommended_tool_match"),
            raw_arg_match=row.get("raw_normalized_arg_match"),
            final_arg_match=row.get("final_normalized_arg_match"),
        )
        failure_layers[layer] += 1
        if layer == "exact_tool_choice_overconstraint":
            exact_overconstraint_cases.append(case_id)
        if layer == "local_tool_arg_match_but_trajectory_fail":
            local_match_failure_cases.append(case_id)
        cases.append(
            {
                "case_id": case_id,
                "baseline_success": row.get("baseline_success"),
                "candidate_success": row.get("candidate_success"),
                "case_fixed": row.get("case_fixed"),
                "case_regressed": row.get("case_regressed"),
                "selected_next_tool": selected_tool,
                "selected_action_args": _candidate_args(validation),
                "emitted_tool": emitted_tool,
                "emitted_args": emitted_args,
                "tool_arg_match": bool(row.get("recommended_tool_match") is True and (row.get("raw_normalized_arg_match") is True or row.get("final_normalized_arg_match") is True)),
                "recommended_tool_match": row.get("recommended_tool_match"),
                "raw_normalized_arg_match": row.get("raw_normalized_arg_match"),
                "final_normalized_arg_match": row.get("final_normalized_arg_match"),
                "candidate_trace_count": len(candidate_traces),
                "baseline_trace_count": len(baseline_traces),
                "candidate_final_tools": candidate_tools,
                "baseline_final_tools": baseline_tools,
                "first_divergent_step": _first_divergent_step(baseline_tools, candidate_tools),
                "whether_exact_tool_choice_was_applied": exact_applied,
                "whether_action_specific_guidance_was_applied": guidance_applied,
                "failure_layer": layer,
            }
        )

    first_failed = None
    if not trace_preflight.get("m2_7l_trace_completeness_passed"):
        first_failed = "trace_mapping_incomplete"
    elif exact_overconstraint_cases:
        first_failed = "exact_tool_choice_overconstraint"
    elif local_match_failure_cases:
        first_failed = "local_tool_arg_match_but_trajectory_fail"
    return {
        "title": "M2.7l Exact Tool-Choice Trajectory Diagnostic",
        "artifact_root": str(root),
        "selected_case_count": len(selected_ids),
        "activated_case_count": activated_count,
        "exact_tool_choice_applied_count": exact_applied_count,
        "action_specific_guidance_applied_count": guidance_applied_count,
        "failure_layer_distribution": dict(sorted(failure_layers.items(), key=lambda item: (-item[1], item[0]))),
        "exact_tool_choice_overconstraint_cases": exact_overconstraint_cases,
        "local_tool_arg_match_but_trajectory_fail_cases": local_match_failure_cases,
        "missing_candidate_prompt_prefix_trace_ids": sorted(missing_candidate_trace_ids),
        "trace_completeness": trace_preflight,
        "cases": cases,
        "m2_7l_exact_tool_choice_trajectory_diagnostic_completed": True,
        "case_level_evidence": "durable" if trace_preflight.get("m2_7l_trace_completeness_passed") else "diagnostic_only",
        "diagnostic": {
            "checker_scope": "m2_7l_offline_exact_tool_choice_trajectory_audit_no_bfcl_no_model_call",
            "first_failed_criterion": first_failed,
            "do_not_rerun_m2_7f_until_trace_and_exact_forcing_are_diagnosed": first_failed is not None,
            "recommended_next_focus": "trace_completeness" if first_failed == "trace_mapping_incomplete" else "conditional_exact_tool_choice_policy",
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7l Exact Tool-Choice Trajectory Diagnostic",
        "",
        f"- Case-level evidence: `{report.get('case_level_evidence')}`",
        f"- Activated cases: `{report.get('activated_case_count')}`",
        f"- Exact tool-choice applied: `{report.get('exact_tool_choice_applied_count')}`",
        f"- Action-specific guidance applied: `{report.get('action_specific_guidance_applied_count')}`",
        f"- Failure layers: `{report.get('failure_layer_distribution')}`",
        f"- Missing candidate prompt-prefix traces: `{report.get('missing_candidate_prompt_prefix_trace_ids')}`",
        f"- First failed criterion: `{(report.get('diagnostic') or {}).get('first_failed_criterion')}`",
        "",
        "| Case | Baseline | Candidate | Selected | Emitted | Exact | Tool+Arg | Layer |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case in report.get("cases") or []:
        if case.get("failure_layer") == "aligned_or_success" and not case.get("case_regressed"):
            continue
        lines.append(
            "| {case_id} | {base} | {cand} | {selected} | {emitted} | {exact} | {match} | {layer} |".format(
                case_id=case.get("case_id"),
                base=case.get("baseline_success"),
                cand=case.get("candidate_success"),
                selected=case.get("selected_next_tool"),
                emitted=case.get("emitted_tool"),
                exact=case.get("whether_exact_tool_choice_was_applied"),
                match=case.get("tool_arg_match"),
                layer=case.get("failure_layer"),
            )
        )
    lines.extend(["", "This is an offline diagnostic. It is not BFCL performance evidence.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose M2.7l exact tool-choice trajectory failures offline.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_exact_tool_choice_trajectory(args.artifact_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        payload = {k: report.get(k) for k in (
            "case_level_evidence",
            "activated_case_count",
            "exact_tool_choice_applied_count",
            "action_specific_guidance_applied_count",
            "failure_layer_distribution",
            "exact_tool_choice_overconstraint_cases",
            "local_tool_arg_match_but_trajectory_fail_cases",
            "missing_candidate_prompt_prefix_trace_ids",
            "diagnostic",
        )}
    else:
        payload = report
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
