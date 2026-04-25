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
    _load_runtime_policy,
    _rule_tools_are_schema_local,
    _selected_dataset_rows,
    _selected_schema_tools,
)
from scripts.diagnose_m27f_activation_predicates import (  # noqa: E402
    DEFAULT_SOURCE_TRACES,
    SOURCE_TRACE_RUNTIME,
    _read_json,
    _source_trace_paths_by_case,
)
from scripts.run_phase2_target_subset import candidate_policy_tool_distribution  # noqa: E402


DEFAULT_ACTIVATION_AUDIT = DEFAULT_ARTIFACT_ROOT / "m27g_activation_audit.json"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _request_excerpt(request_json: dict[str, Any], *, limit: int = 600) -> str:
    text = json.dumps(request_json.get("messages") or request_json.get("input") or [], ensure_ascii=False)
    return text[:limit]


def _final_response_tool(payload: dict[str, Any]) -> str | None:
    final_response = payload.get("final_response") if isinstance(payload.get("final_response"), dict) else {}
    for item in final_response.get("output") or []:
        if isinstance(item, dict) and item.get("type") == "function_call":
            name = item.get("name")
            if isinstance(name, str) and name:
                return name
    return None


def _trace_index(paths: list[Path], source_trace_id: str | None) -> int | None:
    if not source_trace_id:
        return None
    for index, path in enumerate(paths):
        if path.stem == source_trace_id:
            return index
    return None


def _expected_next_tool_proxy(
    *,
    engine: RuleEngine,
    request_json: dict[str, Any],
    trace_paths: list[Path],
    source_trace_id: str | None,
    available_tools: list[str],
    candidate_tools: set[str],
) -> dict[str, Any]:
    start = _trace_index(trace_paths, source_trace_id)
    if start is not None:
        for path in trace_paths[start:]:
            tool = _final_response_tool(_read_json(path))
            if tool and tool in candidate_tools:
                return {"tool": tool, "source": "source_trace_next_emitted_tool", "trace_id": path.stem, "evaluable": True}
    request_text = engine._request_text_for_ranking(request_json)
    hits = engine._request_intent_hits(request_text)
    available = [tool for tool in available_tools if tool in candidate_tools and hits.get(tool, 0) > 0]
    if available:
        tool = max(available, key=lambda item: (hits.get(item, 0), item))
        return {"tool": tool, "source": "request_intent_heuristic", "trace_id": None, "evaluable": True}
    return {"tool": None, "source": "unavailable", "trace_id": None, "evaluable": False}


def _ranked_candidates(
    engine: RuleEngine,
    request_json: dict[str, Any],
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    request_tools = sorted(engine._tool_schema_map(request_json).keys())
    request_tool_set = set(request_tools)
    rows: list[dict[str, Any]] = []
    for rule in engine.rules:
        patch_sites = set(rule.scope.patch_sites)
        if patch_sites and "policy_executor" not in patch_sites and "prompt_injector" not in patch_sites:
            continue
        policy = engine._rule_decision_policy(rule)
        if policy is None:
            continue
        raw_recommended = engine._policy_recommended_tools(policy)
        recommended = [tool for tool in raw_recommended if tool in request_tool_set]
        if not recommended:
            continue
        next_tool_policy = getattr(policy, "next_tool_policy", None)
        confidence = float(getattr(next_tool_policy, "confidence", 0.0) or 0.0)
        for index, candidate in enumerate(engine._policy_action_candidates(policy)):
            components = engine._action_candidate_score_components(
                candidate,
                request_json=request_json,
                request_tool_name_set=request_tool_set,
                recommended=recommended,
                confidence=confidence,
                index=index,
            )
            rows.append(
                {
                    "rule_id": rule.rule_id,
                    "tool": candidate.get("tool"),
                    "candidate_args": candidate.get("args") or {},
                    "candidate_reason": candidate.get("reason"),
                    "candidate_binding_source": candidate.get("binding_source"),
                    "candidate_rank_scores": components,
                    "rank_tuple": list(engine._rank_tuple_from_components(components)),
                }
            )
    return sorted(rows, key=lambda item: tuple(item["rank_tuple"]), reverse=True)[:top_k]


def _why_cat_won(selected_tool: str | None, top_k: list[dict[str, Any]]) -> str | None:
    if selected_tool != "cat":
        return None
    if not top_k:
        return "cat_selected_without_ranked_candidates"
    top = top_k[0]
    scores = top.get("candidate_rank_scores") or {}
    if scores.get("state_compatibility_score", 0) > 0:
        return "cat_prior_output_state_compatible"
    if scores.get("literal_score", 0) > scores.get("intent_score", 0):
        return "cat_literal_or_arg_binding_score_won"
    if scores.get("intent_score", 0) > 0:
        return "cat_generic_intent_score_won"
    return "cat_won_by_tiebreak"


def evaluate_action_ranking_audit(
    activation_audit: Path = DEFAULT_ACTIVATION_AUDIT,
    *,
    rules_dir: Path = DEFAULT_RULES_DIR,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
    source_traces: Path = DEFAULT_SOURCE_TRACES,
    dominant_threshold: float = 0.8,
    min_trace_activation_count: int = 20,
    min_tool_count: int = 3,
    min_proxy_match_rate: float = 0.5,
    top_k: int = 5,
    dataset_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    audit = _load_json(activation_audit)
    category = str(audit.get("category") or "multi_turn_miss_param")
    selected_ids = [str(row.get("case_id")) for row in audit.get("cases_by_state", {}).get(audit.get("trace_state_primary_source") or SOURCE_TRACE_RUNTIME, []) if row.get("case_id")]
    primary_source = str(audit.get("trace_state_primary_source") or SOURCE_TRACE_RUNTIME)
    cases = {row.get("case_id"): row for row in audit.get("cases_by_state", {}).get(primary_source, []) if isinstance(row, dict)}
    rows_by_id = _selected_dataset_rows(category, selected_ids, dataset_rows=dataset_rows)
    schema_tools = _selected_schema_tools(rows_by_id)
    rule_path = rules_dir / "rule.yaml"
    schema_local = _rule_tools_are_schema_local(rule_path, schema_tools)
    engine = RuleEngine(str(rules_dir), runtime_policy=_load_runtime_policy(runtime_config))
    trace_paths_by_case = _source_trace_paths_by_case(source_traces, selected_ids)

    per_case: list[dict[str, Any]] = []
    selected_tools: list[str] = []
    proxy_matches = 0
    proxy_evaluable_count = 0
    activated_count = 0
    for case_id in selected_ids:
        case = cases.get(case_id) or {}
        source_trace_id = case.get("source_trace_id") if isinstance(case.get("source_trace_id"), str) else None
        paths = trace_paths_by_case.get(case_id, [])
        selected_path = next((path for path in paths if path.stem == source_trace_id), None)
        payload = _read_json(selected_path) if selected_path else {}
        request_key = "request_original" if primary_source.endswith("request_original") else "request"
        request_json = payload.get(request_key) if isinstance(payload.get(request_key), dict) else {}
        _, patches = engine.apply_request(request_json)
        plan = getattr(patches, "next_tool_plan", {}) or {}
        selected_tool = plan.get("selected_tool") if plan.get("activated") else None
        if isinstance(selected_tool, str) and selected_tool:
            selected_tools.append(selected_tool)
        if plan.get("activated"):
            activated_count += 1
        available_tools = sorted(engine._tool_schema_map(request_json).keys())
        top = _ranked_candidates(engine, request_json, top_k=top_k)
        candidate_tools = {str(row.get("tool")) for row in top if row.get("tool")}
        expected = _expected_next_tool_proxy(
            engine=engine,
            request_json=request_json,
            trace_paths=paths,
            source_trace_id=source_trace_id,
            available_tools=available_tools,
            candidate_tools=candidate_tools,
        )
        proxy_evaluable = bool(expected.get("evaluable"))
        proxy_match = bool(proxy_evaluable and selected_tool and expected.get("tool") == selected_tool)
        proxy_matches += int(proxy_match)
        proxy_evaluable_count += int(proxy_evaluable)
        per_case.append(
            {
                "case_id": case_id,
                "source_trace_id": source_trace_id,
                "selected_tool": selected_tool,
                "top_k_candidates": top,
                "request_text_excerpt": _request_excerpt(request_json),
                "available_tools": available_tools,
                "prior_tool_name": engine._last_prior_tool_name(request_json),
                "prior_tool_output_keys": sorted(engine._prior_tool_output_keys(request_json)),
                "explicit_literals": engine._collect_context_literals(request_json),
                "candidate_args": top[0].get("candidate_args") if top else {},
                "literal_score": (top[0].get("candidate_rank_scores") or {}).get("literal_score") if top else None,
                "intent_score": (top[0].get("candidate_rank_scores") or {}).get("intent_score") if top else None,
                "recommended_rank": (top[0].get("candidate_rank_scores") or {}).get("recommended_rank") if top else None,
                "why_cat_won": _why_cat_won(selected_tool, top),
                "expected_next_tool_proxy": expected,
                "proxy_evaluable": proxy_evaluable,
                "proxy_match": proxy_match,
            }
        )

    distribution = Counter(selected_tools)
    dominant_tool, dominant_count = (None, 0)
    if distribution:
        dominant_tool, dominant_count = distribution.most_common(1)[0]
    dominant_rate = dominant_count / activated_count if activated_count else 0.0
    proxy_match_rate = proxy_matches / proxy_evaluable_count if proxy_evaluable_count else 0.0
    gate_passed = (
        activated_count >= min_trace_activation_count
        and schema_local
        and dominant_rate <= dominant_threshold
        and len(distribution) >= min_tool_count
        and proxy_match_rate >= min_proxy_match_rate
    )
    first_failed = None
    if activated_count < min_trace_activation_count:
        first_failed = "trace_state_plan_activated_count"
    elif not schema_local:
        first_failed = "candidate_rules_schema_local"
    elif dominant_rate > dominant_threshold:
        first_failed = "dominant_selected_next_tool_rate"
    elif len(distribution) < min_tool_count:
        first_failed = "selected_next_tool_distribution_tool_count"
    elif proxy_match_rate < min_proxy_match_rate:
        first_failed = "recommended_tool_match_proxy"

    return {
        "activation_audit_path": str(activation_audit),
        "rules_dir": str(rules_dir),
        "runtime_config": str(runtime_config),
        "source_traces": str(source_traces),
        "category": category,
        "request_state_source": primary_source,
        "selected_case_count": len(selected_ids),
        "trace_state_plan_activated_count": activated_count,
        "candidate_rules_schema_local": schema_local,
        "candidate_policy_tool_distribution": candidate_policy_tool_distribution(rule_path),
        "selected_next_tool_distribution": dict(sorted(distribution.items(), key=lambda item: (-item[1], item[0]))),
        "dominant_selected_next_tool": dominant_tool,
        "dominant_selected_next_tool_rate": dominant_rate,
        "selected_next_tool_count": len(distribution),
        "recommended_tool_match_proxy": proxy_match_rate,
        "recommended_tool_match_proxy_evaluable_count": proxy_evaluable_count,
        "dominant_threshold": dominant_threshold,
        "min_trace_activation_count": min_trace_activation_count,
        "min_tool_count": min_tool_count,
        "min_proxy_match_rate": min_proxy_match_rate,
        "m2_7h_action_ranking_passed": gate_passed,
        "cases": per_case,
        "diagnostic": {
            "checker_scope": "action_ranking_audit_no_upstream_model_call",
            "do_not_rerun_m2_7f_until_passed": not gate_passed,
            "first_failed_criterion": first_failed,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose M2.7h action candidate ranking on source-trace state.")
    parser.add_argument("--activation-audit", type=Path, default=DEFAULT_ACTIVATION_AUDIT)
    parser.add_argument("--rules-dir", type=Path, default=DEFAULT_RULES_DIR)
    parser.add_argument("--runtime-config", type=Path, default=DEFAULT_RUNTIME_CONFIG)
    parser.add_argument("--source-traces", type=Path, default=DEFAULT_SOURCE_TRACES)
    parser.add_argument("--dominant-threshold", type=float, default=0.8)
    parser.add_argument("--min-trace-activation-count", type=int, default=20)
    parser.add_argument("--min-tool-count", type=int, default=3)
    parser.add_argument("--min-proxy-match-rate", type=float, default=0.5)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_action_ranking_audit(
        args.activation_audit,
        rules_dir=args.rules_dir,
        runtime_config=args.runtime_config,
        source_traces=args.source_traces,
        dominant_threshold=args.dominant_threshold,
        min_trace_activation_count=args.min_trace_activation_count,
        min_tool_count=args.min_tool_count,
        min_proxy_match_rate=args.min_proxy_match_rate,
        top_k=args.top_k,
    )
    text = json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["m2_7h_action_ranking_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
