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

from grc.runtime.engine import RuleEngine  # noqa: E402
from scripts.check_m27f_candidate_plan_diversity import (  # noqa: E402
    DEFAULT_ARTIFACT_ROOT,
    DEFAULT_RULES_DIR,
    DEFAULT_RUNTIME_CONFIG,
    _load_manifest,
    _load_runtime_policy,
    _rule_tools_are_schema_local,
    _selected_dataset_rows,
    _selected_schema_tools,
)
from scripts.diagnose_m27f_activation_predicates import (  # noqa: E402
    SOURCE_TRACE_ORIGINAL,
    SOURCE_TRACE_RUNTIME,
    _case_state_record,
    _choose_representative,
    _primary_trace_state,
    _source_trace_evaluations,
    _source_trace_paths_by_case,
    _state_summary,
)
from scripts.diagnose_m27i_regression_audit import evaluate_regression_audit  # noqa: E402
from scripts.diagnose_m27f_activation_predicates import DEFAULT_SOURCE_TRACES  # noqa: E402


DEFAULT_REGRESSION_AUDIT = DEFAULT_ARTIFACT_ROOT / "m27i_regression_audit.json"
DEFAULT_OUTPUT = DEFAULT_ARTIFACT_ROOT / "m27i_guard_preflight.json"
DEFAULT_MARKDOWN_OUTPUT = DEFAULT_ARTIFACT_ROOT / "m27i_guard_preflight.md"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_regression_audit(path: Path, artifact_root: Path) -> dict[str, Any]:
    payload = _read_json(path)
    if payload:
        return payload
    return evaluate_regression_audit(artifact_root)


def _tool_distribution(plans: list[dict[str, Any]]) -> Counter[str]:
    tools: list[str] = []
    for plan in plans:
        if not plan.get("activated"):
            continue
        tool = plan.get("selected_tool")
        if isinstance(tool, str) and tool:
            tools.append(tool)
    return Counter(tools)


def _dominant_tool_rate(distribution: Counter[str], activated_count: int) -> tuple[str | None, float]:
    if not distribution or activated_count <= 0:
        return None, 0.0
    tool, count = distribution.most_common(1)[0]
    return tool, count / activated_count


def _candidate_guard_reasons(plan: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for rejected in plan.get("rejected_action_candidates") or []:
        if not isinstance(rejected, dict):
            continue
        guard = rejected.get("guard") if isinstance(rejected.get("guard"), dict) else {}
        reason = guard.get("reason")
        reasons.append(str(reason or "unknown"))
    return reasons


def _accepted_guard_reason(plan: dict[str, Any]) -> str | None:
    guard = plan.get("action_candidate_guard") if isinstance(plan.get("action_candidate_guard"), dict) else {}
    reason = guard.get("reason")
    return str(reason) if reason else None


def _top_candidate_rejection_reason(plan: dict[str, Any]) -> str | None:
    rejected = plan.get("rejected_action_candidates") or []
    if not rejected or not isinstance(rejected[0], dict):
        return None
    guard = rejected[0].get("guard") if isinstance(rejected[0].get("guard"), dict) else {}
    reason = guard.get("reason")
    return str(reason) if reason else None


def _case_final_guard_reason(after_plan: dict[str, Any]) -> str | None:
    if after_plan.get("activated"):
        return _accepted_guard_reason(after_plan)
    return _top_candidate_rejection_reason(after_plan) or str(after_plan.get("blocked_reason") or "unknown")


def _case_status(before_plan: dict[str, Any], after_plan: dict[str, Any]) -> str:
    before_candidate = before_plan.get("selected_action_candidate") if isinstance(before_plan.get("selected_action_candidate"), dict) else None
    after_candidate = after_plan.get("selected_action_candidate") if isinstance(after_plan.get("selected_action_candidate"), dict) else None
    after_kept = bool(after_plan.get("activated") and after_candidate)
    if not before_candidate:
        return "no_candidate_before_guard"
    if after_kept:
        before_tool = before_plan.get("selected_tool")
        after_tool = after_plan.get("selected_tool")
        if before_tool and after_tool and before_tool != after_tool:
            return "guard_changed_tool"
        return "guard_kept"
    if after_plan.get("blocked_reason") == "action_candidate_guard_rejected":
        return "guard_rejected"
    return "guard_blocked_other"


def _first_failed_criterion(
    *,
    schema_local: bool,
    guard_rejects_regressed_cases: int,
    min_regressed_rejects: int,
    guard_keeps_fixed_cases: int,
    min_fixed_keeps: int,
    activated_after: int,
    min_after_activation: int,
    max_after_activation: int,
    dominant_rate: float,
    dominant_threshold: float,
) -> str | None:
    if not schema_local:
        return "candidate_rules_schema_local"
    if guard_rejects_regressed_cases < min_regressed_rejects:
        return "guard_rejects_regressed_cases"
    if guard_keeps_fixed_cases < min_fixed_keeps:
        return "guard_keeps_fixed_cases"
    if activated_after < min_after_activation:
        return "plan_activated_count_after_guard_min"
    if activated_after > max_after_activation:
        return "plan_activated_count_after_guard_max"
    if dominant_rate > dominant_threshold:
        return "dominant_selected_next_tool_rate_after_guard"
    return None


def summarize_guard_preflight(
    case_records: list[dict[str, Any]],
    *,
    selected_case_count: int,
    regressed_cases: list[str],
    fixed_cases: list[str],
    schema_local: bool,
    min_regressed_rejects: int = 2,
    min_fixed_keeps: int = 1,
    min_after_activation: int = 10,
    max_after_activation: int = 25,
    dominant_threshold: float = 0.8,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    before_plans = [row.get("before_guard_plan") or {} for row in case_records]
    after_plans = [row.get("after_guard_plan") or {} for row in case_records]
    activated_before = sum(1 for plan in before_plans if plan.get("activated"))
    activated_after = sum(1 for plan in after_plans if plan.get("activated"))
    distribution = _tool_distribution(after_plans)
    dominant_tool, dominant_rate = _dominant_tool_rate(distribution, activated_after)
    guard_reason_distribution: Counter[str] = Counter()
    top_candidate_reason_distribution: Counter[str] = Counter()
    case_final_reason_distribution: Counter[str] = Counter()
    guard_rejected_count = 0
    status_by_case: dict[str, str] = {}
    enriched_cases: list[dict[str, Any]] = []
    for row in case_records:
        before_plan = row.get("before_guard_plan") or {}
        after_plan = row.get("after_guard_plan") or {}
        status = _case_status(before_plan, after_plan)
        case_id = str(row.get("case_id") or "")
        status_by_case[case_id] = status
        if status == "guard_rejected":
            guard_rejected_count += 1
        reasons = _candidate_guard_reasons(after_plan)
        top_reason = _top_candidate_rejection_reason(after_plan)
        final_reason = _case_final_guard_reason(after_plan)
        guard_reason_distribution.update(reasons)
        if top_reason:
            top_candidate_reason_distribution[top_reason] += 1
        if final_reason:
            case_final_reason_distribution[final_reason] += 1
        enriched = dict(row)
        enriched["guard_status"] = status
        enriched["guard_rejection_reasons"] = reasons
        enriched["all_candidate_rejection_reasons"] = reasons
        enriched["top_candidate_rejection_reason"] = top_reason
        enriched["case_final_guard_reason"] = final_reason
        enriched_cases.append(enriched)

    regressed_status = {case_id: status_by_case.get(case_id, "missing") for case_id in regressed_cases}
    fixed_status = {case_id: status_by_case.get(case_id, "missing") for case_id in fixed_cases}
    guard_rejects_regressed_cases = sum(1 for status in regressed_status.values() if status == "guard_rejected")
    guard_keeps_fixed_cases = sum(1 for status in fixed_status.values() if status in {"guard_kept", "guard_changed_tool"})
    first_failed = _first_failed_criterion(
        schema_local=schema_local,
        guard_rejects_regressed_cases=guard_rejects_regressed_cases,
        min_regressed_rejects=min_regressed_rejects,
        guard_keeps_fixed_cases=guard_keeps_fixed_cases,
        min_fixed_keeps=min_fixed_keeps,
        activated_after=activated_after,
        min_after_activation=min_after_activation,
        max_after_activation=max_after_activation,
        dominant_rate=dominant_rate,
        dominant_threshold=dominant_threshold,
    )
    report: dict[str, Any] = {
        "selected_case_count": selected_case_count,
        "plan_activated_count_before_guard": activated_before,
        "plan_activated_count_after_guard": activated_after,
        "guard_rejected_count": guard_rejected_count,
        "guard_reason_distribution": dict(sorted(guard_reason_distribution.items(), key=lambda item: (-item[1], item[0]))),
        "all_candidate_rejection_reason_distribution": dict(sorted(guard_reason_distribution.items(), key=lambda item: (-item[1], item[0]))),
        "top_candidate_rejection_reason_distribution": dict(sorted(top_candidate_reason_distribution.items(), key=lambda item: (-item[1], item[0]))),
        "case_final_guard_reason_distribution": dict(sorted(case_final_reason_distribution.items(), key=lambda item: (-item[1], item[0]))),
        "selected_next_tool_distribution_after_guard": dict(sorted(distribution.items(), key=lambda item: (-item[1], item[0]))),
        "selected_next_tool_count_after_guard": len(distribution),
        "dominant_selected_next_tool_after_guard": dominant_tool,
        "dominant_selected_next_tool_rate_after_guard": dominant_rate,
        "candidate_rules_schema_local": schema_local,
        "regressed_cases_guard_status": regressed_status,
        "fixed_cases_guard_status": fixed_status,
        "guard_rejects_regressed_cases": guard_rejects_regressed_cases,
        "guard_keeps_fixed_cases": guard_keeps_fixed_cases,
        "min_regressed_rejects": min_regressed_rejects,
        "min_fixed_keeps": min_fixed_keeps,
        "min_after_activation": min_after_activation,
        "max_after_activation": max_after_activation,
        "dominant_threshold": dominant_threshold,
        "m2_7i_guard_preflight_passed": first_failed is None,
        "cases": enriched_cases,
        "diagnostic": {
            "checker_scope": "m2_7i_guard_preflight_no_upstream_model_call",
            "first_failed_criterion": first_failed,
            "do_not_rerun_m2_7f_until_passed": first_failed is not None,
        },
    }
    if metadata:
        report.update(metadata)
    return report


def _before_guard_plan(engine: RuleEngine, request_json: dict[str, Any]) -> dict[str, Any]:
    request_tools = sorted(engine._tool_schema_map(request_json).keys())
    request_tool_set = set(request_tools)
    observed = engine._observable_request_predicates(request_json)
    plan: dict[str, Any] = {
        "attempted": True,
        "activated": False,
        "blocked_reason": "no_policy_candidate",
        "available_tools": request_tools,
        "selected_tool": None,
        "selected_action_candidate": None,
        "policy_hits": [],
        "candidate_recommended_tools": [],
        "matched_recommended_tools": [],
        "recommended_tools": [],
        "action_candidates": [],
        "selected_candidate_rank_scores": None,
    }
    if not request_tools:
        plan["blocked_reason"] = "no_tools_available"
        return plan

    best_selection: tuple[tuple[int, int, int, int, float, int, int], dict[str, Any], dict[str, Any]] | None = None
    fallback_selected_tool: str | None = None
    blocked_reason = "no_policy_candidate"
    blocked_priority = {
        "no_policy_candidate": 1,
        "request_predicates_unmet": 2,
        "activation_predicates_unmet": 3,
        "recommended_tools_empty": 4,
        "recommended_tools_not_in_schema": 5,
        "activated": 99,
    }
    blocked_rank = blocked_priority[blocked_reason]

    def mark_blocked(reason: str) -> None:
        nonlocal blocked_reason, blocked_rank
        rank = blocked_priority.get(reason, 0)
        if rank >= blocked_rank:
            blocked_reason = reason
            blocked_rank = rank

    def add_unique(field: str, values: list[str]) -> None:
        for value in values:
            if value and value not in plan[field]:
                plan[field].append(value)

    for rule in engine.rules:
        patch_sites = set(rule.scope.patch_sites)
        if patch_sites and "policy_executor" not in patch_sites and "prompt_injector" not in patch_sites:
            continue
        policy = engine._rule_decision_policy(rule)
        if policy is None:
            continue
        raw_recommended = engine._policy_recommended_tools(policy)
        add_unique("candidate_recommended_tools", raw_recommended)
        if not set(engine._rule_request_predicates(rule)).issubset(observed):
            mark_blocked("request_predicates_unmet")
            continue
        activation_predicates = engine._next_tool_activation_predicates(rule, policy)
        if not set(activation_predicates).issubset(observed):
            mark_blocked("activation_predicates_unmet")
            continue
        if not raw_recommended:
            mark_blocked("recommended_tools_empty")
            continue
        recommended = [tool for tool in raw_recommended if tool in request_tool_set]
        if not recommended:
            mark_blocked("recommended_tools_not_in_schema")
            continue
        confidence = float(getattr(getattr(policy, "next_tool_policy", None), "confidence", 0.0) or 0.0)
        ranked = engine._rank_action_candidates(
            engine._policy_action_candidates(policy),
            request_json=request_json,
            request_tool_name_set=request_tool_set,
            recommended=recommended,
            confidence=confidence,
        )
        for _, candidate in ranked:
            if candidate not in plan["action_candidates"]:
                plan["action_candidates"].append(candidate)
        plan["activated"] = True
        plan["blocked_reason"] = "activated"
        plan["policy_hits"].append(rule.rule_id)
        add_unique("matched_recommended_tools", recommended)
        add_unique("recommended_tools", recommended)
        fallback_selected_tool = fallback_selected_tool or recommended[0]
        if ranked:
            rank, candidate = ranked[0]
            components = engine._action_candidate_score_components(
                candidate,
                request_json=request_json,
                request_tool_name_set=request_tool_set,
                recommended=recommended,
                confidence=confidence,
                index=0,
            )
            if best_selection is None or rank > best_selection[0]:
                best_selection = (rank, candidate, components)
        mark_blocked("activated")

    if best_selection is not None:
        plan["selected_action_candidate"] = best_selection[1]
        plan["selected_tool"] = str(best_selection[1].get("tool") or "") or fallback_selected_tool
        plan["selected_candidate_rank_scores"] = best_selection[2]
    elif fallback_selected_tool:
        plan["selected_tool"] = fallback_selected_tool
    if not plan["activated"]:
        plan["blocked_reason"] = blocked_reason
    plan["candidate_recommended_tools"] = plan["candidate_recommended_tools"][:5]
    plan["matched_recommended_tools"] = plan["matched_recommended_tools"][:3]
    plan["recommended_tools"] = plan["recommended_tools"][:3]
    plan["action_candidates"] = plan["action_candidates"][:5]
    return plan


def _apply_after_guard(engine: RuleEngine, request_json: dict[str, Any]) -> dict[str, Any]:
    patched, patches = engine.apply_request(request_json)
    plan = getattr(patches, "next_tool_plan", {}) or {}
    if not isinstance(plan, dict):
        return {}
    plan = dict(plan)
    plan["request_patches"] = list(patches or [])
    plan["patched_tool_choice"] = patched.get("tool_choice")
    return plan


def _compact_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "activated": bool(plan.get("activated")),
        "blocked_reason": plan.get("blocked_reason"),
        "selected_tool": plan.get("selected_tool"),
        "selected_action_candidate": plan.get("selected_action_candidate"),
        "action_candidate_guard": plan.get("action_candidate_guard"),
        "rejected_action_candidates": list(plan.get("rejected_action_candidates") or []),
        "selected_candidate_rank_scores": plan.get("selected_candidate_rank_scores"),
        "recommended_tools": list(plan.get("recommended_tools") or []),
        "matched_recommended_tools": list(plan.get("matched_recommended_tools") or []),
        "policy_hits": list(plan.get("policy_hits") or []),
        "request_patches": list(plan.get("request_patches") or []),
        "patched_tool_choice": plan.get("patched_tool_choice"),
    }


def evaluate_guard_preflight(
    manifest_path: Path = DEFAULT_ARTIFACT_ROOT / "paired_subset_manifest.json",
    *,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    rules_dir: Path = DEFAULT_RULES_DIR,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
    source_traces: Path = DEFAULT_SOURCE_TRACES,
    regression_audit_path: Path = DEFAULT_REGRESSION_AUDIT,
    min_regressed_rejects: int = 2,
    min_fixed_keeps: int = 1,
    min_after_activation: int = 10,
    max_after_activation: int = 25,
    dominant_threshold: float = 0.8,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    selected_ids = [str(case_id) for case_id in manifest.get("selected_case_ids") or []]
    category = str(manifest.get("category") or "multi_turn_miss_param")
    rows_by_id = _selected_dataset_rows(category, selected_ids)
    schema_tools = _selected_schema_tools(rows_by_id)
    rule_path = rules_dir / "rule.yaml"
    schema_local = _rule_tools_are_schema_local(rule_path, schema_tools)
    engine = RuleEngine(str(rules_dir), runtime_policy=_load_runtime_policy(runtime_config))
    traces_by_case = _source_trace_paths_by_case(source_traces, selected_ids)

    evaluations_by_state: dict[str, dict[str, Any]] = {SOURCE_TRACE_ORIGINAL: {}, SOURCE_TRACE_RUNTIME: {}}
    records_by_state: dict[str, list[dict[str, Any]]] = {SOURCE_TRACE_ORIGINAL: [], SOURCE_TRACE_RUNTIME: []}
    for case_id in selected_ids:
        for state_source in (SOURCE_TRACE_ORIGINAL, SOURCE_TRACE_RUNTIME):
            evaluation = _choose_representative(_source_trace_evaluations(engine, traces_by_case.get(case_id, []), state_source))
            evaluations_by_state[state_source][case_id] = evaluation
            records_by_state[state_source].append(_case_state_record(engine, case_id, evaluation))

    per_state_summary = {state: _state_summary(records) for state, records in records_by_state.items()}
    primary_source = _primary_trace_state(per_state_summary)
    regression_audit = _load_regression_audit(regression_audit_path, artifact_root)
    regressed_cases = [str(case_id) for case_id in regression_audit.get("regressed_cases") or []]
    fixed_cases = [str(case_id) for case_id in regression_audit.get("fixed_cases") or []]

    case_records: list[dict[str, Any]] = []
    for case_id in selected_ids:
        evaluation = evaluations_by_state.get(primary_source, {}).get(case_id)
        request_json = getattr(evaluation, "request_json", {}) or {}
        before = _before_guard_plan(engine, request_json)
        after = _apply_after_guard(engine, request_json)
        case_records.append(
            {
                "case_id": case_id,
                "request_state_source": primary_source,
                "source_trace_id": getattr(evaluation, "source_trace_id", None),
                "target_failure_trace": bool(getattr(evaluation, "target_failure_trace", False)),
                "before_guard_plan": _compact_plan(before),
                "after_guard_plan": _compact_plan(after),
            }
        )

    return summarize_guard_preflight(
        case_records,
        selected_case_count=len(selected_ids),
        regressed_cases=regressed_cases,
        fixed_cases=fixed_cases,
        schema_local=schema_local,
        min_regressed_rejects=min_regressed_rejects,
        min_fixed_keeps=min_fixed_keeps,
        min_after_activation=min_after_activation,
        max_after_activation=max_after_activation,
        dominant_threshold=dominant_threshold,
        metadata={
            "manifest_path": str(manifest_path),
            "artifact_root": str(artifact_root),
            "rules_dir": str(rules_dir),
            "rule_path": str(rule_path),
            "runtime_config": str(runtime_config),
            "source_traces": str(source_traces),
            "regression_audit_path": str(regression_audit_path),
            "category": category,
            "exact_next_tool_choice_mode": engine.exact_next_tool_choice_mode,
            "exact_tool_choice_trajectory_sensitive_tools": sorted(engine.exact_tool_choice_trajectory_sensitive_tools),
            "request_state_source": primary_source,
            "per_state_summary_after_guard": per_state_summary,
        },
    )


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.7i Guard Preflight",
        "",
        f"- Passed: `{report.get('m2_7i_guard_preflight_passed')}`",
        f"- Selected cases: `{report.get('selected_case_count')}`",
        f"- Before guard activations: `{report.get('plan_activated_count_before_guard')}`",
        f"- After guard activations: `{report.get('plan_activated_count_after_guard')}`",
        f"- Guard rejected cases: `{report.get('guard_rejected_count')}`",
        f"- Guard reasons: `{report.get('guard_reason_distribution')}`",
        f"- After guard tool distribution: `{report.get('selected_next_tool_distribution_after_guard')}`",
        f"- Dominant after guard rate: `{report.get('dominant_selected_next_tool_rate_after_guard')}`",
        f"- Regressed status: `{report.get('regressed_cases_guard_status')}`",
        f"- Fixed status: `{report.get('fixed_cases_guard_status')}`",
        f"- First failed criterion: `{(report.get('diagnostic') or {}).get('first_failed_criterion')}`",
        "",
        "## Changed Cases",
        "",
        "| Case | Status | Before Tool | After Tool | Guard Reasons |",
        "| --- | --- | --- | --- | --- |",
    ]
    changed = set((report.get("regressed_cases_guard_status") or {}).keys()) | set((report.get("fixed_cases_guard_status") or {}).keys())
    for case in report.get("cases") or []:
        if case.get("case_id") not in changed:
            continue
        before = case.get("before_guard_plan") or {}
        after = case.get("after_guard_plan") or {}
        lines.append(
            "| {case_id} | {status} | {before_tool} | {after_tool} | {reasons} |".format(
                case_id=case.get("case_id"),
                status=case.get("guard_status"),
                before_tool=before.get("selected_tool"),
                after_tool=after.get("selected_tool"),
                reasons=", ".join(case.get("guard_rejection_reasons") or []) or "-",
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This checker is an offline source-trace replay. It gates whether the conservative action guard is precise enough to justify a later M2.7f-lite rerun; it is not BFCL performance evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check M2.7i conservative guard behavior on source-trace state without BFCL/model calls.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_ARTIFACT_ROOT / "paired_subset_manifest.json")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--rules-dir", type=Path, default=DEFAULT_RULES_DIR)
    parser.add_argument("--runtime-config", type=Path, default=DEFAULT_RUNTIME_CONFIG)
    parser.add_argument("--source-traces", type=Path, default=DEFAULT_SOURCE_TRACES)
    parser.add_argument("--regression-audit", type=Path, default=DEFAULT_REGRESSION_AUDIT)
    parser.add_argument("--min-regressed-rejects", type=int, default=2)
    parser.add_argument("--min-fixed-keeps", type=int, default=1)
    parser.add_argument("--min-after-activation", type=int, default=10)
    parser.add_argument("--max-after-activation", type=int, default=25)
    parser.add_argument("--dominant-threshold", type=float, default=0.8)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_guard_preflight(
        args.manifest,
        artifact_root=args.artifact_root,
        rules_dir=args.rules_dir,
        runtime_config=args.runtime_config,
        source_traces=args.source_traces,
        regression_audit_path=args.regression_audit,
        min_regressed_rejects=args.min_regressed_rejects,
        min_fixed_keeps=args.min_fixed_keeps,
        min_after_activation=args.min_after_activation,
        max_after_activation=args.max_after_activation,
        dominant_threshold=args.dominant_threshold,
    )
    text = json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(text, end="")
    return 0 if report["m2_7i_guard_preflight_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
