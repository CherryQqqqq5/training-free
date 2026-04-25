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

from scripts.check_m27i_guard_preflight import evaluate_guard_preflight  # noqa: E402
from scripts.run_phase2_target_subset import _trace_paths_by_case_from_prompt_prefix  # noqa: E402


DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_OUTPUT = DEFAULT_ROOT / "m27k_tool_arg_alignment.json"
DEFAULT_MARKDOWN_OUTPUT = DEFAULT_ROOT / "m27k_tool_arg_alignment.md"


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


def _trace_groups(root: Path, run_name: str, category: str, selected_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    run_root = root / run_name
    paths_by_case = _trace_paths_by_case_from_prompt_prefix(
        source_run_root=run_root,
        category=category,
        selected_ids=selected_ids,
    )
    if not paths_by_case or not any(paths_by_case.get(case_id) for case_id in selected_ids):
        paths_by_case = {case_id: sorted((run_root / "traces").glob(f"{case_id}*.json")) for case_id in selected_ids}
    groups: dict[str, list[dict[str, Any]]] = {case_id: [] for case_id in selected_ids}
    for case_id, paths in paths_by_case.items():
        for path in paths:
            payload = _read_json(path)
            if payload:
                groups.setdefault(case_id, []).append(payload)
    return groups


def _first_activated_validation(traces: list[dict[str, Any]]) -> dict[str, Any]:
    for trace in traces:
        validation = trace.get("validation") if isinstance(trace.get("validation"), dict) else {}
        if validation.get("next_tool_plan_activated") is True:
            return validation
    return {}


def _selected_candidate(validation: dict[str, Any]) -> dict[str, Any]:
    candidate = validation.get("selected_action_candidate")
    return candidate if isinstance(candidate, dict) else {}


def _candidate_binding_sources(candidate: dict[str, Any]) -> list[str]:
    sources: set[str] = set()
    source = candidate.get("binding_source")
    if isinstance(source, str) and source:
        sources.add(source)
    bindings = candidate.get("arg_bindings") if isinstance(candidate.get("arg_bindings"), dict) else {}
    for binding in bindings.values():
        if isinstance(binding, dict) and isinstance(binding.get("source"), str):
            sources.add(str(binding["source"]))
    return sorted(sources)


def _classification(row: dict[str, Any]) -> str:
    if row.get("policy_plan_activated") is not True:
        return "not_activated_context"
    if row.get("recommended_tool_match") is not True:
        return "actuation_or_prompt_guidance"
    if row.get("raw_normalized_arg_match") is not True and row.get("final_normalized_arg_match") is not True:
        return "argument_realization"
    if row.get("candidate_success") is not True:
        return "trajectory_continuation_or_final_answer"
    return "aligned_or_fixed"


def _case_kind(row: dict[str, Any]) -> str:
    if row.get("case_fixed") is True:
        return "fixed"
    if row.get("case_regressed") is True:
        return "regressed"
    if row.get("baseline_success") is True and row.get("candidate_success") is True:
        return "stable_success"
    if row.get("baseline_success") is False and row.get("candidate_success") is False:
        return "stable_failure"
    return "unknown"


def _tool_choice_matches_selected(tool_choice: Any, selected_tool: str | None) -> bool:
    if not selected_tool or not isinstance(tool_choice, dict):
        return False
    function = tool_choice.get("function") if isinstance(tool_choice.get("function"), dict) else {}
    return tool_choice.get("type") == "function" and function.get("name") == selected_tool


def _preflight_coverage(preflight: dict[str, Any]) -> dict[str, Any]:
    accepted = []
    guidance_hits = 0
    exact_hits = 0
    serializable_hits = 0
    for case in preflight.get("cases") or []:
        plan = case.get("after_guard_plan") if isinstance(case.get("after_guard_plan"), dict) else {}
        candidate = plan.get("selected_action_candidate") if isinstance(plan.get("selected_action_candidate"), dict) else None
        if not plan.get("activated") or not candidate:
            continue
        accepted.append(case)
        patches = [str(item) for item in plan.get("request_patches") or []]
        if any(item.startswith("prompt_injector:Policy selected next tool:") for item in patches):
            guidance_hits += 1
        if _tool_choice_matches_selected(plan.get("patched_tool_choice"), str(plan.get("selected_tool") or "")):
            exact_hits += 1
        try:
            json.dumps(candidate.get("args") or {}, ensure_ascii=False, sort_keys=True)
        except TypeError:
            continue
        serializable_hits += 1
    denominator = len(accepted)
    return {
        "accepted_activated_candidate_count": denominator,
        "action_specific_guidance_count": guidance_hits,
        "exact_tool_choice_count": exact_hits,
        "candidate_args_serializable_count": serializable_hits,
        "action_specific_guidance_coverage": guidance_hits / denominator if denominator else 0.0,
        "exact_tool_choice_coverage": exact_hits / denominator if denominator else 0.0,
        "candidate_args_serializable_rate": serializable_hits / denominator if denominator else 0.0,
    }


def _first_failed_criterion(report: dict[str, Any]) -> str | None:
    if not report.get("all_activated_cases_classified"):
        return "all_activated_cases_classified"
    if report.get("action_specific_guidance_coverage") != 1.0:
        return "action_specific_guidance_coverage"
    if report.get("exact_tool_choice_coverage") != 1.0:
        return "exact_tool_choice_coverage"
    if report.get("candidate_args_serializable_rate") != 1.0:
        return "candidate_args_serializable_rate"
    if not report.get("candidate_rules_schema_local"):
        return "candidate_rules_schema_local"
    after_count = int(report.get("plan_activated_count_after_guard") or 0)
    if after_count < 10 or after_count > 20:
        return "plan_activated_count_after_guard"
    if float(report.get("dominant_selected_next_tool_rate_after_guard") or 0.0) > 0.8:
        return "dominant_selected_next_tool_rate_after_guard"
    fixed_status = report.get("fixed_cases_guard_status") or {}
    if any(status not in {"guard_kept", "guard_changed_tool"} for status in fixed_status.values()):
        return "fixed_cases_guard_status"
    return None


def evaluate_tool_arg_alignment(
    root: Path = DEFAULT_ROOT,
    *,
    category: str | None = None,
    case_report_path: Path | None = None,
    preflight_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = _read_json(root / "paired_subset_manifest.json")
    selected_ids = [str(case_id) for case_id in manifest.get("selected_case_ids") or []]
    category = category or str(manifest.get("category") or "multi_turn_miss_param")
    rows = _read_jsonl(case_report_path or root / "subset_case_report.jsonl")
    rows_by_id = {str(row.get("case_id")): row for row in rows if row.get("case_id")}
    candidate_traces = _trace_groups(root, "candidate", category, selected_ids)

    cases: list[dict[str, Any]] = []
    classification_counts: Counter[str] = Counter()
    activated_count = 0
    classified_activated_count = 0
    for case_id in selected_ids:
        row = rows_by_id.get(case_id, {"case_id": case_id})
        validation = _first_activated_validation(candidate_traces.get(case_id, []))
        candidate = _selected_candidate(validation)
        classification = _classification(row)
        classification_counts[classification] += 1
        if row.get("policy_plan_activated") is True:
            activated_count += 1
            if classification != "not_activated_context":
                classified_activated_count += 1
        cases.append(
            {
                "case_id": case_id,
                "case_kind": _case_kind(row),
                "classification": classification,
                "baseline_success": row.get("baseline_success"),
                "candidate_success": row.get("candidate_success"),
                "policy_plan_activated": row.get("policy_plan_activated"),
                "selected_next_tool": row.get("selected_next_tool"),
                "next_tool_emitted": row.get("next_tool_emitted"),
                "recommended_tool_match": row.get("recommended_tool_match"),
                "raw_normalized_arg_match": row.get("raw_normalized_arg_match"),
                "final_normalized_arg_match": row.get("final_normalized_arg_match"),
                "selected_action_candidate": candidate,
                "binding_sources": _candidate_binding_sources(candidate),
                "repair_kinds": row.get("repair_kinds") or validation.get("repair_kinds") or [],
            }
        )

    if preflight_report is None:
        preflight_report = evaluate_guard_preflight(artifact_root=root)
    coverage = _preflight_coverage(preflight_report)
    report: dict[str, Any] = {
        "title": "M2.7k Tool/Arg Alignment Diagnostic",
        "selected_case_count": len(selected_ids),
        "activated_case_count": activated_count,
        "classified_activated_case_count": classified_activated_count,
        "all_activated_cases_classified": activated_count == classified_activated_count,
        "classification_counts": dict(sorted(classification_counts.items(), key=lambda item: (-item[1], item[0]))),
        "cases": cases,
        "candidate_rules_schema_local": preflight_report.get("candidate_rules_schema_local"),
        "plan_activated_count_after_guard": preflight_report.get("plan_activated_count_after_guard"),
        "dominant_selected_next_tool_rate_after_guard": preflight_report.get("dominant_selected_next_tool_rate_after_guard"),
        "fixed_cases_guard_status": preflight_report.get("fixed_cases_guard_status") or {},
        "regressed_cases_guard_status": preflight_report.get("regressed_cases_guard_status") or {},
        **coverage,
    }
    first_failed = _first_failed_criterion(report)
    report["m2_7k_tool_arg_alignment_passed"] = first_failed is None
    report["diagnostic"] = {
        "checker_scope": "m2_7k_offline_tool_arg_alignment_no_upstream_model_call",
        "first_failed_criterion": first_failed,
        "do_not_rerun_m2_7f_until_passed": first_failed is not None,
        "recommended_next_focus": "actuation_or_prompt_guidance" if first_failed else "m2_7f_lite_rerun_candidate",
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7k Tool/Arg Alignment Diagnostic",
        "",
        "- Passed: `{}`".format(report.get("m2_7k_tool_arg_alignment_passed")),
        "- Activated cases: `{}`".format(report.get("activated_case_count")),
        "- Classification counts: `{}`".format(report.get("classification_counts")),
        "- Action-specific guidance coverage: `{}`".format(report.get("action_specific_guidance_coverage")),
        "- Exact tool-choice coverage: `{}`".format(report.get("exact_tool_choice_coverage")),
        "- First failed criterion: `{}`".format((report.get("diagnostic") or {}).get("first_failed_criterion")),
        "",
        "| Case | Kind | Classification | Selected Tool | Tool Match | Raw Arg Match |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in report.get("cases") or []:
        if case.get("policy_plan_activated") is not True:
            continue
        lines.append(
            "| {case_id} | {kind} | {classification} | {tool} | {tool_match} | {arg_match} |".format(
                case_id=case.get("case_id"),
                kind=case.get("case_kind"),
                classification=case.get("classification"),
                tool=case.get("selected_next_tool"),
                tool_match=case.get("recommended_tool_match"),
                arg_match=case.get("raw_normalized_arg_match"),
            )
        )
    lines.extend(["", "This is an offline diagnostic and preflight. It is not BFCL performance evidence.", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose M2.7k tool and argument alignment offline.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    report = evaluate_tool_arg_alignment(args.artifact_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        payload = {k: report.get(k) for k in (
            "m2_7k_tool_arg_alignment_passed",
            "activated_case_count",
            "classification_counts",
            "action_specific_guidance_coverage",
            "exact_tool_choice_coverage",
            "candidate_args_serializable_rate",
            "plan_activated_count_after_guard",
            "dominant_selected_next_tool_rate_after_guard",
            "diagnostic",
        )}
    else:
        payload = report
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report.get("m2_7k_tool_arg_alignment_passed") else 1)


if __name__ == "__main__":
    main()
