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

from scripts.run_phase2_target_subset import _trace_paths_by_case_from_prompt_prefix  # noqa: E402


DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")


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


def _final_response_tool_names(trace: dict[str, Any]) -> list[str]:
    final_response = trace.get("final_response") if isinstance(trace.get("final_response"), dict) else {}
    names: list[str] = []
    for item in final_response.get("output") or []:
        if isinstance(item, dict) and item.get("type") == "function_call" and isinstance(item.get("name"), str):
            names.append(str(item["name"]))
    choices = final_response.get("choices") if isinstance(final_response.get("choices"), list) else []
    for choice in choices:
        message = choice.get("message") if isinstance(choice, dict) and isinstance(choice.get("message"), dict) else {}
        for call in message.get("tool_calls") or []:
            function = call.get("function") if isinstance(call, dict) and isinstance(call.get("function"), dict) else {}
            name = function.get("name")
            if isinstance(name, str):
                names.append(name)
    return names


def _first_activated_validation(traces: list[dict[str, Any]]) -> dict[str, Any]:
    for trace in traces:
        validation = trace.get("validation") if isinstance(trace.get("validation"), dict) else {}
        if validation.get("next_tool_plan_activated") is True:
            return validation
    return {}


def _collect_repair_kinds(traces: list[dict[str, Any]]) -> list[str]:
    kinds: set[str] = set()
    for trace in traces:
        validation = trace.get("validation") if isinstance(trace.get("validation"), dict) else {}
        for kind in validation.get("repair_kinds") or []:
            if isinstance(kind, str) and kind:
                kinds.add(kind)
    return sorted(kinds)


def _selected_candidate(validation: dict[str, Any]) -> dict[str, Any]:
    candidate = validation.get("selected_action_candidate")
    return candidate if isinstance(candidate, dict) else {}


def _binding_sources(candidate: dict[str, Any]) -> list[str]:
    sources: set[str] = set()
    source = candidate.get("binding_source")
    if isinstance(source, str) and source:
        sources.add(source)
    bindings = candidate.get("arg_bindings") if isinstance(candidate.get("arg_bindings"), dict) else {}
    for binding in bindings.values():
        if isinstance(binding, dict) and isinstance(binding.get("source"), str):
            sources.add(str(binding["source"]))
    return sorted(sources)


def _binding_risk(row: dict[str, Any], validation: dict[str, Any]) -> str | None:
    candidate = _selected_candidate(validation)
    sources = _binding_sources(candidate)
    if row.get("raw_normalized_arg_match") is True:
        return None
    if not candidate:
        return "no_selected_action_candidate"
    if any(source.startswith("prior_tool_output") for source in sources):
        return "prior_output_binding_not_realized"
    if "explicit_literal" in sources:
        return "explicit_literal_binding_not_realized"
    return "weak_or_unknown_binding_evidence"


def _failure_layers(row: dict[str, Any], validation: dict[str, Any]) -> list[str]:
    layers: list[str] = []
    if row.get("case_regressed") is True or row.get("candidate_success") is False:
        if row.get("policy_plan_activated") and row.get("baseline_success") is True:
            layers.append("over_actuation")
        if row.get("next_tool_emitted") is not True:
            layers.append("trajectory_continuation_or_final_answer")
        elif row.get("recommended_tool_match") is not True:
            layers.append("wrong_next_tool")
        elif row.get("raw_normalized_arg_match") is not True:
            layers.append("wrong_args")
        if row.get("repair_kinds"):
            layers.append("repair_interaction")
        if not layers:
            layers.append("trajectory_continuation_or_final_answer")
    return list(dict.fromkeys(layers))


def _success_conditions(row: dict[str, Any], validation: dict[str, Any]) -> list[str]:
    if row.get("case_fixed") is not True:
        return []
    conditions: list[str] = []
    if row.get("recommended_tool_match") is True:
        conditions.append("recommended_tool_match")
    if row.get("raw_normalized_arg_match") is True:
        conditions.append("raw_arg_binding_match")
    if row.get("final_normalized_arg_match") is True:
        conditions.append("final_arg_binding_match")
    candidate = _selected_candidate(validation)
    if "explicit_literal" in _binding_sources(candidate):
        conditions.append("explicit_literal_binding")
    if row.get("next_tool_emitted") is True:
        conditions.append("tool_emitted")
    return list(dict.fromkeys(conditions))


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


def _mechanism_summary(row: dict[str, Any], layers: list[str], success_conditions: list[str], risk: str | None) -> str:
    case_id = row.get("case_id")
    if row.get("case_regressed") is True:
        detail = ", ".join(layers or ["unclassified"])
        suffix = f"; binding risk={risk}" if risk else ""
        return f"{case_id} regressed after CTSPC intervention: {detail}{suffix}"
    if row.get("case_fixed") is True:
        detail = ", ".join(success_conditions or ["unclassified_success"])
        return f"{case_id} fixed with CTSPC intervention: {detail}"
    if risk:
        return f"{case_id} retained outcome but has binding risk={risk}"
    return f"{case_id} has no fixed/regressed outcome change"


def _first_failed_criterion(
    *,
    regressions_classified: bool,
    fixed_success_conditions_extracted: bool,
    binding_risk_recorded: bool,
) -> str | None:
    if not regressions_classified:
        return "regressions_unclassified"
    if not fixed_success_conditions_extracted:
        return "fixed_success_conditions_missing"
    if not binding_risk_recorded:
        return "binding_risk_not_recorded"
    return None


def evaluate_regression_audit(
    root: Path = DEFAULT_ROOT,
    *,
    category: str | None = None,
    case_report_path: Path | None = None,
) -> dict[str, Any]:
    manifest = _read_json(root / "paired_subset_manifest.json")
    selected_ids = [str(case_id) for case_id in manifest.get("selected_case_ids") or []]
    category = category or str(manifest.get("category") or "multi_turn_miss_param")
    rows = _read_jsonl(case_report_path or root / "subset_case_report.jsonl")
    rows_by_id = {str(row.get("case_id")): row for row in rows if row.get("case_id")}
    baseline_traces = _trace_groups(root, "baseline", category, selected_ids)
    candidate_traces = _trace_groups(root, "candidate", category, selected_ids)

    cases: list[dict[str, Any]] = []
    failure_layer_counts: Counter[str] = Counter()
    binding_risk_counts: Counter[str] = Counter()
    selected_tool_counts: Counter[str] = Counter()
    for case_id in selected_ids:
        row = rows_by_id.get(case_id, {"case_id": case_id})
        candidate_group = candidate_traces.get(case_id, [])
        baseline_group = baseline_traces.get(case_id, [])
        validation = _first_activated_validation(candidate_group)
        candidate = _selected_candidate(validation)
        layers = _failure_layers(row, validation)
        success_conditions = _success_conditions(row, validation)
        risk = _binding_risk(row, validation) if row.get("policy_plan_activated") else None
        failure_layer_counts.update(layers)
        if risk:
            binding_risk_counts[risk] += 1
        selected_tool = row.get("selected_next_tool")
        if selected_tool:
            selected_tool_counts[str(selected_tool)] += 1
        candidate_final_tools: list[str] = []
        for trace in candidate_group:
            candidate_final_tools.extend(_final_response_tool_names(trace))
        baseline_final_tools: list[str] = []
        for trace in baseline_group:
            baseline_final_tools.extend(_final_response_tool_names(trace))
        cases.append(
            {
                "case_id": case_id,
                "case_kind": _case_kind(row),
                "baseline_success": row.get("baseline_success"),
                "candidate_success": row.get("candidate_success"),
                "policy_plan_activated": row.get("policy_plan_activated"),
                "selected_next_tool": selected_tool,
                "next_tool_emitted": row.get("next_tool_emitted"),
                "recommended_tool_match": row.get("recommended_tool_match"),
                "raw_normalized_arg_match": row.get("raw_normalized_arg_match"),
                "final_normalized_arg_match": row.get("final_normalized_arg_match"),
                "repair_kinds": row.get("repair_kinds") or _collect_repair_kinds(candidate_group),
                "baseline_trace_count": len(baseline_group),
                "candidate_trace_count": len(candidate_group),
                "step_expansion": len(candidate_group) - len(baseline_group),
                "candidate_final_tools": candidate_final_tools[:10],
                "baseline_final_tools": baseline_final_tools[:10],
                "selected_action_candidate": candidate,
                "candidate_args": candidate.get("args") or {},
                "binding_sources": _binding_sources(candidate),
                "binding_risk": risk,
                "failure_layers": layers,
                "success_conditions": success_conditions,
                "mechanism_summary": _mechanism_summary(row, layers, success_conditions, risk),
            }
        )

    fixed = [case for case in cases if case["case_kind"] == "fixed"]
    regressed = [case for case in cases if case["case_kind"] == "regressed"]
    fixed_success_conditions_extracted = all(case.get("success_conditions") for case in fixed)
    regressions_classified = all(case.get("failure_layers") for case in regressed)
    binding_risk_recorded = bool(binding_risk_counts)
    passed = regressions_classified and fixed_success_conditions_extracted and binding_risk_recorded
    return {
        "artifact_root": str(root),
        "category": category,
        "selected_case_count": len(selected_ids),
        "case_kind_distribution": dict(Counter(case["case_kind"] for case in cases)),
        "selected_next_tool_distribution": dict(selected_tool_counts),
        "failure_layer_distribution": dict(failure_layer_counts),
        "binding_risk_distribution": dict(binding_risk_counts),
        "regressed_cases": [case["case_id"] for case in regressed],
        "fixed_cases": [case["case_id"] for case in fixed],
        "regressions_classified": regressions_classified,
        "fixed_success_conditions_extracted": fixed_success_conditions_extracted,
        "binding_risk_recorded": binding_risk_recorded,
        "m2_7i_regression_audit_passed": passed,
        "cases": cases,
        "diagnostic": {
            "checker_scope": "case_level_regression_audit_no_upstream_model_call",
            "first_failed_criterion": _first_failed_criterion(
                regressions_classified=regressions_classified,
                fixed_success_conditions_extracted=fixed_success_conditions_extracted,
                binding_risk_recorded=binding_risk_recorded,
            ),
            "do_not_rerun_m2_7f_until_guard_tests_pass": True,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7i Regression Audit",
        "",
        f"- Passed: `{report.get('m2_7i_regression_audit_passed')}`",
        f"- Selected cases: `{report.get('selected_case_count')}`",
        f"- Case kinds: `{report.get('case_kind_distribution')}`",
        f"- Failure layers: `{report.get('failure_layer_distribution')}`",
        f"- Binding risks: `{report.get('binding_risk_distribution')}`",
        f"- Regressed cases: `{report.get('regressed_cases')}`",
        f"- Fixed cases: `{report.get('fixed_cases')}`",
        "",
        "## Changed Cases",
        "",
        "| Case | Kind | Selected Tool | Arg Match | Repairs | Layers / Conditions |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in report.get("cases") or []:
        if case.get("case_kind") not in {"fixed", "regressed"}:
            continue
        labels = case.get("failure_layers") or case.get("success_conditions") or []
        lines.append(
            "| {case_id} | {kind} | {tool} | {arg} | {repairs} | {labels} |".format(
                case_id=case.get("case_id"),
                kind=case.get("case_kind"),
                tool=case.get("selected_next_tool"),
                arg=case.get("raw_normalized_arg_match"),
                repairs=", ".join(case.get("repair_kinds") or []) or "-",
                labels=", ".join(labels) or "-",
            )
        )
    lines.extend(["", "## Interpretation", ""])
    lines.append(
        "M2.7i treats the M2.7f rerun as durable evidence and focuses on over-actuation, "
        "wrong tool selection, and weak argument binding rather than activation coverage."
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose M2.7i case-level regressions without running BFCL.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--category", default=None)
    parser.add_argument("--case-report", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_regression_audit(args.root, category=args.category, case_report_path=args.case_report)
    text = json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(text, end="")
    return 0 if report["m2_7i_regression_audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
