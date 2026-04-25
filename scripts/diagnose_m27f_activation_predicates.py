#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
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
    _build_plan_request,
    _compact_plan,
    _first_failed_criterion,
    _load_manifest,
    _load_runtime_policy,
    _selected_dataset_rows,
    _selected_schema_tools,
    _rule_tools_are_schema_local,
    _turn_prefix_messages,
)
from scripts.run_phase2_target_subset import candidate_policy_tool_distribution  # noqa: E402


DEFAULT_SOURCE_TRACES = DEFAULT_RULES_DIR / "source_selected_traces"
DATASET_PROMPT_PREFIX = "dataset_prompt_prefix"
SOURCE_TRACE_ORIGINAL = "source_trace_request_original"
SOURCE_TRACE_RUNTIME = "source_trace_runtime_request"
SOURCE_STATES = (SOURCE_TRACE_ORIGINAL, SOURCE_TRACE_RUNTIME)
TARGET_FAILURE_LABELS = {
    "(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)",
    "(POST_TOOL,POST_TOOL_PROSE_SUMMARY)",
}


@dataclass
class RequestEvaluation:
    request_state_source: str
    request_json: dict[str, Any]
    plan: dict[str, Any]
    source_trace_id: str | None = None
    trace_path: str | None = None
    target_failure_trace: bool = False
    turn_index: int | None = None

    @property
    def activated(self) -> bool:
        return bool(self.plan.get("activated"))

    @property
    def blocked_reason(self) -> str:
        return str(self.plan.get("blocked_reason") or "unknown")

    @property
    def selected_tool(self) -> str | None:
        tool = self.plan.get("selected_tool")
        return tool if isinstance(tool, str) and tool else None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _target_failure_trace(payload: dict[str, Any]) -> bool:
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    labels = validation.get("failure_labels") if isinstance(validation, dict) else []
    return bool(set(labels or []) & TARGET_FAILURE_LABELS)


def _case_id_from_trace_path(path: Path) -> str:
    return path.name.split("__", 1)[0]


def _source_trace_paths_by_case(trace_dir: Path, selected_ids: list[str]) -> dict[str, list[Path]]:
    selected = set(selected_ids)
    out: dict[str, list[Path]] = {case_id: [] for case_id in selected_ids}
    if not trace_dir.exists():
        return out
    for path in sorted(trace_dir.glob("*.json")):
        case_id = _case_id_from_trace_path(path)
        if case_id in selected:
            out[case_id].append(path)
    return out


def _apply_engine(engine: RuleEngine, request_json: dict[str, Any]) -> dict[str, Any]:
    _, patches = engine.apply_request(request_json)
    plan = getattr(patches, "next_tool_plan", {}) or {}
    return plan if isinstance(plan, dict) else {}


def _dataset_evaluations(
    engine: RuleEngine,
    row: dict[str, Any],
) -> list[RequestEvaluation]:
    evaluations: list[RequestEvaluation] = []
    for turn_index, messages in _turn_prefix_messages(row.get("question")):
        request = _build_plan_request(row, messages)
        evaluations.append(
            RequestEvaluation(
                request_state_source=DATASET_PROMPT_PREFIX,
                request_json=request,
                plan=_apply_engine(engine, request),
                turn_index=turn_index,
            )
        )
    return evaluations


def _source_trace_evaluations(
    engine: RuleEngine,
    paths: list[Path],
    state_source: str,
) -> list[RequestEvaluation]:
    request_key = "request_original" if state_source == SOURCE_TRACE_ORIGINAL else "request"
    evaluations: list[RequestEvaluation] = []
    for path in paths:
        payload = _read_json(path)
        request = payload.get(request_key) if isinstance(payload.get(request_key), dict) else {}
        target_failure = _target_failure_trace(payload)
        evaluations.append(
            RequestEvaluation(
                request_state_source=state_source,
                request_json=request,
                plan=_apply_engine(engine, request),
                source_trace_id=path.stem,
                trace_path=str(path),
                target_failure_trace=target_failure,
            )
        )
    return evaluations


def _choose_representative(evaluations: list[RequestEvaluation]) -> RequestEvaluation | None:
    if not evaluations:
        return None
    activated_target = [item for item in evaluations if item.activated and item.target_failure_trace]
    if activated_target:
        return activated_target[0]
    activated = [item for item in evaluations if item.activated]
    if activated:
        return activated[0]
    target = [item for item in evaluations if item.target_failure_trace]
    if target:
        return target[0]
    return evaluations[-1]


def _rule_diagnostic(engine: RuleEngine, rule: Any, request_json: dict[str, Any]) -> dict[str, Any]:
    available_tools = sorted(engine._tool_schema_map(request_json).keys())
    observed = sorted(engine._observable_request_predicates(request_json))
    patch_sites = set(rule.scope.patch_sites)
    policy = engine._rule_decision_policy(rule)
    if patch_sites and "policy_executor" not in patch_sites and "prompt_injector" not in patch_sites:
        return {
            "rule_id": rule.rule_id,
            "required_request_predicates": [],
            "required_activation_predicates": [],
            "observed_predicates": observed,
            "unmet_predicates": [],
            "blocked_reason": "rule_scope_not_policy_executor",
            "available_tools": available_tools,
            "candidate_recommended_tools": [],
            "matched_recommended_tools": [],
            "selected_next_tool": None,
            "selected_action_candidate_if_any": None,
        }
    if policy is None:
        return {
            "rule_id": rule.rule_id,
            "required_request_predicates": [],
            "required_activation_predicates": [],
            "observed_predicates": observed,
            "unmet_predicates": [],
            "blocked_reason": "no_decision_policy",
            "available_tools": available_tools,
            "candidate_recommended_tools": [],
            "matched_recommended_tools": [],
            "selected_next_tool": None,
            "selected_action_candidate_if_any": None,
        }

    request_predicates = list(engine._rule_request_predicates(rule))
    activation_predicates = list(engine._next_tool_activation_predicates(rule, policy))
    raw_recommended = list(engine._policy_recommended_tools(policy))
    observed_set = set(observed)
    unmet_request = [predicate for predicate in request_predicates if predicate not in observed_set]
    unmet_activation = [predicate for predicate in activation_predicates if predicate not in observed_set]
    matched = [tool for tool in raw_recommended if tool in set(available_tools)]
    selected_candidate = None
    selected_tool = None
    blocked_reason = "activated"
    unmet = unmet_request or unmet_activation

    if not available_tools:
        blocked_reason = "no_tools_available"
    elif unmet_request:
        blocked_reason = "request_predicates_unmet"
    elif unmet_activation:
        blocked_reason = "activation_predicates_unmet"
    elif not raw_recommended:
        blocked_reason = "recommended_tools_empty"
    elif not matched:
        blocked_reason = "recommended_tools_not_in_schema"
    else:
        next_tool_policy = getattr(policy, "next_tool_policy", None)
        confidence = float(getattr(next_tool_policy, "confidence", 0.0) or 0.0)
        ranked = engine._rank_action_candidates(
            engine._policy_action_candidates(policy),
            request_json=request_json,
            request_tool_name_set=set(available_tools),
            recommended=matched,
            confidence=confidence,
        )
        if ranked:
            selected_candidate = ranked[0][1]
            candidate_tool = selected_candidate.get("tool") if isinstance(selected_candidate, dict) else None
            selected_tool = candidate_tool if isinstance(candidate_tool, str) and candidate_tool else matched[0]
        else:
            selected_tool = matched[0]

    return {
        "rule_id": rule.rule_id,
        "required_request_predicates": request_predicates,
        "required_activation_predicates": activation_predicates,
        "observed_predicates": observed,
        "unmet_predicates": unmet,
        "blocked_reason": blocked_reason,
        "available_tools": available_tools,
        "candidate_recommended_tools": raw_recommended,
        "matched_recommended_tools": matched,
        "selected_next_tool": selected_tool,
        "selected_action_candidate_if_any": selected_candidate,
    }


def _case_state_record(engine: RuleEngine, case_id: str, evaluation: RequestEvaluation | None) -> dict[str, Any]:
    if evaluation is None:
        return {
            "case_id": case_id,
            "request_state_source": None,
            "source_trace_id": None,
            "target_failure_trace": False,
            "activated": False,
            "blocked_reason": "request_state_missing",
            "selected_next_tool": None,
            "turn_index": None,
            "plan": {"activated": False, "blocked_reason": "request_state_missing"},
            "rule_diagnostics": [],
        }
    return {
        "case_id": case_id,
        "request_state_source": evaluation.request_state_source,
        "source_trace_id": evaluation.source_trace_id,
        "target_failure_trace": evaluation.target_failure_trace,
        "activated": evaluation.activated,
        "blocked_reason": evaluation.blocked_reason,
        "selected_next_tool": evaluation.selected_tool,
        "turn_index": evaluation.turn_index,
        "plan": _compact_plan(evaluation.plan),
        "rule_diagnostics": [
            _rule_diagnostic(engine, rule, evaluation.request_json)
            for rule in engine.rules
        ],
    }


def _state_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    activated = [row for row in records if row.get("activated")]
    selected_tools = [str(row.get("selected_next_tool")) for row in activated if row.get("selected_next_tool")]
    distribution = Counter(selected_tools)
    blocked_distribution = Counter(str(row.get("blocked_reason") or "unknown") for row in records)
    dominant_tool, dominant_count = (None, 0)
    if distribution:
        dominant_tool, dominant_count = distribution.most_common(1)[0]
    activated_count = len(activated)
    return {
        "case_count": len(records),
        "activated_case_count": activated_count,
        "blocked_reason_distribution": dict(sorted(blocked_distribution.items(), key=lambda item: (-item[1], item[0]))),
        "selected_next_tool_distribution": dict(sorted(distribution.items(), key=lambda item: (-item[1], item[0]))),
        "dominant_selected_next_tool": dominant_tool,
        "dominant_selected_next_tool_rate": dominant_count / activated_count if activated_count else 0.0,
    }


def _primary_trace_state(per_state_summary: dict[str, dict[str, Any]]) -> str:
    original = per_state_summary.get(SOURCE_TRACE_ORIGINAL, {})
    runtime = per_state_summary.get(SOURCE_TRACE_RUNTIME, {})
    original_count = int(original.get("activated_case_count") or 0)
    runtime_count = int(runtime.get("activated_case_count") or 0)
    if runtime_count >= original_count:
        return SOURCE_TRACE_RUNTIME
    return SOURCE_TRACE_ORIGINAL


def _first_failed_gate(
    *,
    trace_summary: dict[str, Any],
    selected_case_count: int,
    schema_local: bool,
    min_trace_activation_count: int,
    dominant_threshold: float,
) -> str | None:
    activated_count = int(trace_summary.get("activated_case_count") or 0)
    distribution = Counter(trace_summary.get("selected_next_tool_distribution") or {})
    dominant_rate = float(trace_summary.get("dominant_selected_next_tool_rate") or 0.0)
    blocked = trace_summary.get("blocked_reason_distribution") or {}
    no_activation_like = int(blocked.get("no_activation") or 0) + int(blocked.get("activation_predicates_unmet") or 0)
    if not schema_local:
        return "candidate_rules_schema_local"
    if selected_case_count and no_activation_like / selected_case_count > 0.5:
        return "trace_state_no_activation_dominant"
    if activated_count < min_trace_activation_count:
        return "trace_state_plan_activated_count"
    return _first_failed_criterion(
        activated_count=activated_count,
        distribution=distribution,
        dominant_rate=dominant_rate,
        dominant_threshold=dominant_threshold,
        schema_local=schema_local,
    )


def _diagnostic_branch(
    *,
    dataset_summary: dict[str, Any],
    trace_summary: dict[str, Any],
    first_failed: str | None,
) -> str:
    dataset_activated = int(dataset_summary.get("activated_case_count") or 0)
    trace_activated = int(trace_summary.get("activated_case_count") or 0)
    if first_failed in {"selected_next_tool_single_mkdir_collapse", "selected_next_tool_single_tool_collapse", "dominant_selected_next_tool_rate"}:
        return "fix_request_local_action_ranking"
    if dataset_activated == 0 and trace_activated > 0:
        return "plan_only_state_too_shallow"
    if first_failed == "candidate_rules_schema_local":
        return "fix_rule_generation_schema_pruning"
    blocked = trace_summary.get("blocked_reason_distribution") or {}
    if blocked.get("recommended_tools_not_in_schema"):
        return "fix_rule_generation_schema_pruning"
    if blocked.get("no_policy_candidate"):
        return "fix_rulescope_or_request_predicate_extraction"
    if blocked.get("activation_predicates_unmet"):
        return "fix_trace_to_policy_predicate_generation"
    if first_failed in {"selected_next_tool_single_mkdir_collapse", "selected_next_tool_single_tool_collapse", "dominant_selected_next_tool_rate"}:
        return "fix_request_local_action_ranking"
    if first_failed is None:
        return "m2_7g_passed_ready_for_m2_7f_rerun_preflight"
    return "inspect_activation_audit"


def evaluate_activation_predicate_audit(
    manifest_path: Path = DEFAULT_ARTIFACT_ROOT / "paired_subset_manifest.json",
    *,
    rules_dir: Path = DEFAULT_RULES_DIR,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
    source_traces: Path = DEFAULT_SOURCE_TRACES,
    dominant_threshold: float = 0.8,
    min_trace_activation_count: int = 20,
    dataset_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    selected_ids = [str(case_id) for case_id in manifest.get("selected_case_ids") or []]
    category = str(manifest.get("category") or "multi_turn_miss_param")
    rows_by_id = _selected_dataset_rows(category, selected_ids, dataset_rows=dataset_rows)
    schema_tools = _selected_schema_tools(rows_by_id)
    rule_path = rules_dir / "rule.yaml"
    schema_local = _rule_tools_are_schema_local(rule_path, schema_tools)
    engine = RuleEngine(str(rules_dir), runtime_policy=_load_runtime_policy(runtime_config))
    traces_by_case = _source_trace_paths_by_case(source_traces, selected_ids)

    records_by_state: dict[str, list[dict[str, Any]]] = {
        DATASET_PROMPT_PREFIX: [],
        SOURCE_TRACE_ORIGINAL: [],
        SOURCE_TRACE_RUNTIME: [],
    }

    for case_id in selected_ids:
        row = rows_by_id.get(case_id)
        dataset_eval = _choose_representative(_dataset_evaluations(engine, row)) if row is not None else None
        records_by_state[DATASET_PROMPT_PREFIX].append(_case_state_record(engine, case_id, dataset_eval))
        for state_source in SOURCE_STATES:
            source_eval = _choose_representative(
                _source_trace_evaluations(engine, traces_by_case.get(case_id, []), state_source)
            )
            records_by_state[state_source].append(_case_state_record(engine, case_id, source_eval))

    per_state_summary = {state: _state_summary(records) for state, records in records_by_state.items()}
    primary_source = _primary_trace_state(per_state_summary)
    primary_summary = per_state_summary[primary_source]
    first_failed = _first_failed_gate(
        trace_summary=primary_summary,
        selected_case_count=len(selected_ids),
        schema_local=schema_local,
        min_trace_activation_count=min_trace_activation_count,
        dominant_threshold=dominant_threshold,
    )
    gate_passed = first_failed is None
    return {
        "manifest_path": str(manifest_path),
        "rules_dir": str(rules_dir),
        "rule_path": str(rule_path),
        "runtime_config": str(runtime_config),
        "source_traces": str(source_traces),
        "category": category,
        "selected_case_count": len(selected_ids),
        "candidate_rules_schema_local": schema_local,
        "candidate_policy_tool_distribution": candidate_policy_tool_distribution(rule_path),
        "selected_schema_tool_count": len(schema_tools),
        "request_state_sources": [DATASET_PROMPT_PREFIX, SOURCE_TRACE_ORIGINAL, SOURCE_TRACE_RUNTIME],
        "per_state_summary": per_state_summary,
        "trace_state_primary_source": primary_source,
        "trace_state_plan_activated_count": int(primary_summary.get("activated_case_count") or 0),
        "dominant_selected_next_tool_rate": float(primary_summary.get("dominant_selected_next_tool_rate") or 0.0),
        "dominant_threshold": dominant_threshold,
        "min_trace_activation_count": min_trace_activation_count,
        "m2_7g_activation_audit_passed": gate_passed,
        "cases_by_state": records_by_state,
        "diagnostic": {
            "checker_scope": "activation_predicate_audit_no_upstream_model_call",
            "do_not_rerun_m2_7f_until_passed": not gate_passed,
            "first_failed_criterion": first_failed,
            "state_reconstruction_note": "dataset_prompt_prefix_too_shallow"
            if int(per_state_summary[DATASET_PROMPT_PREFIX].get("activated_case_count") or 0) == 0
            and int(primary_summary.get("activated_case_count") or 0) > 0
            else None,
            "branch": _diagnostic_branch(
                dataset_summary=per_state_summary[DATASET_PROMPT_PREFIX],
                trace_summary=primary_summary,
                first_failed=first_failed,
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit M2.7f activation predicates across dataset and source-trace request states.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_ARTIFACT_ROOT / "paired_subset_manifest.json")
    parser.add_argument("--rules-dir", type=Path, default=DEFAULT_RULES_DIR)
    parser.add_argument("--runtime-config", type=Path, default=DEFAULT_RUNTIME_CONFIG)
    parser.add_argument("--source-traces", type=Path, default=DEFAULT_SOURCE_TRACES)
    parser.add_argument("--dominant-threshold", type=float, default=0.8)
    parser.add_argument("--min-trace-activation-count", type=int, default=20)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_activation_predicate_audit(
        args.manifest,
        rules_dir=args.rules_dir,
        runtime_config=args.runtime_config,
        source_traces=args.source_traces,
        dominant_threshold=args.dominant_threshold,
        min_trace_activation_count=args.min_trace_activation_count,
    )
    text = json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["m2_7g_activation_audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
