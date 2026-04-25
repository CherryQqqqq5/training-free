#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from grc.runtime.engine import RuleEngine  # noqa: E402
from grc.utils.bfcl_request_policy import (  # noqa: E402
    apply_bfcl_fc_request_policy,
    apply_bfcl_memory_request_policy,
)
from scripts.run_phase2_target_subset import candidate_policy_tool_distribution  # noqa: E402


DEFAULT_ARTIFACT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_RULES_DIR = Path("outputs/phase2_subset/bfcl_ctspc_subset30_v1/candidate_rules")
DEFAULT_RUNTIME_CONFIG = Path("configs/runtime_bfcl_structured.yaml")


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _load_runtime_policy(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    runtime_policy = payload.get("runtime_policy") if isinstance(payload, dict) else {}
    return runtime_policy if isinstance(runtime_policy, dict) else {}


def _load_dataset_rows(category: str) -> list[dict[str, Any]]:
    try:
        from bfcl_eval.utils import load_dataset_entry
    except Exception as exc:  # pragma: no cover - exercised only when BFCL is unavailable.
        raise RuntimeError(f"BFCL dataset loader is unavailable: {exc}") from exc
    rows = load_dataset_entry(category)
    if not isinstance(rows, list):
        raise RuntimeError(f"BFCL dataset loader returned {type(rows).__name__}, expected list")
    return [row for row in rows if isinstance(row, dict)]


def _selected_dataset_rows(
    category: str,
    selected_ids: list[str],
    dataset_rows: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    rows = dataset_rows if dataset_rows is not None else _load_dataset_rows(category)
    selected = set(selected_ids)
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = row.get("id")
        if isinstance(case_id, str) and case_id in selected:
            by_id[case_id] = row
    return by_id


def _normalize_bfcl_tool(tool: Any) -> dict[str, Any] | None:
    if not isinstance(tool, dict):
        return None
    name = tool.get("name")
    if not isinstance(name, str) or not name:
        return None
    normalized = dict(tool)
    normalized.setdefault("type", "function")
    return normalized


def _tools_from_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    tools = row.get("function") or []
    if not isinstance(tools, list):
        return []
    normalized = [_normalize_bfcl_tool(tool) for tool in tools]
    return [tool for tool in normalized if tool is not None]


def _selected_schema_tools(rows_by_id: dict[str, dict[str, Any]]) -> set[str]:
    tools: set[str] = set()
    for row in rows_by_id.values():
        for tool in _tools_from_row(row):
            name = tool.get("name")
            if isinstance(name, str) and name:
                tools.add(name)
            function = tool.get("function")
            if isinstance(function, dict):
                fn_name = function.get("name")
                if isinstance(fn_name, str) and fn_name:
                    tools.add(fn_name)
    return tools


def _message_from_item(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    role = item.get("role")
    content = item.get("content")
    if not isinstance(role, str) or not role:
        return None
    message = dict(item)
    if content is not None and not isinstance(content, str):
        message["content"] = json.dumps(content, ensure_ascii=False)
    return message


def _turn_prefix_messages(question: Any) -> Iterable[tuple[int, list[dict[str, Any]]]]:
    if not isinstance(question, list):
        return
    flattened: list[dict[str, Any]] = []
    for turn_index, turn in enumerate(question):
        turn_items = turn if isinstance(turn, list) else [turn]
        for item in turn_items:
            message = _message_from_item(item)
            if message is not None:
                flattened.append(message)
        if flattened:
            yield turn_index, list(flattened)


def _build_plan_request(row: dict[str, Any], messages: list[dict[str, Any]]) -> dict[str, Any]:
    request: dict[str, Any] = {
        "model": "m27f-plan-only",
        "input": messages,
        "tools": _tools_from_row(row),
    }
    request = apply_bfcl_fc_request_policy(request)
    request = apply_bfcl_memory_request_policy(request)
    return request


def _rule_tools_are_schema_local(rule_path: Path, schema_tools: set[str]) -> bool:
    distribution = candidate_policy_tool_distribution(rule_path)
    return bool(distribution) and set(distribution).issubset(schema_tools)


def _compact_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "activated": bool(plan.get("activated")),
        "blocked_reason": plan.get("blocked_reason"),
        "selected_tool": plan.get("selected_tool"),
        "recommended_tools": list(plan.get("recommended_tools") or []),
        "matched_recommended_tools": list(plan.get("matched_recommended_tools") or []),
        "candidate_recommended_tools": list(plan.get("candidate_recommended_tools") or []),
        "policy_hits": list(plan.get("policy_hits") or []),
        "selected_action_candidate": plan.get("selected_action_candidate"),
    }


def _first_failed_criterion(
    *,
    activated_count: int,
    distribution: Counter[str],
    dominant_rate: float,
    dominant_threshold: float,
    schema_local: bool,
) -> str | None:
    if activated_count <= 0:
        return "no_activation"
    if not distribution:
        return "selected_next_tool_missing"
    if not schema_local:
        return "candidate_rules_schema_local"
    if len(distribution) == 1:
        tool = next(iter(distribution))
        return "selected_next_tool_single_mkdir_collapse" if tool == "mkdir" else "selected_next_tool_single_tool_collapse"
    if dominant_rate > dominant_threshold:
        return "dominant_selected_next_tool_rate"
    return None


def evaluate_candidate_plan_diversity(
    manifest_path: Path = DEFAULT_ARTIFACT_ROOT / "paired_subset_manifest.json",
    *,
    rules_dir: Path = DEFAULT_RULES_DIR,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
    dominant_threshold: float = 0.8,
    dataset_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    selected_ids = [str(case_id) for case_id in manifest.get("selected_case_ids") or []]
    category = str(manifest.get("category") or "multi_turn_miss_param")
    rows_by_id = _selected_dataset_rows(category, selected_ids, dataset_rows=dataset_rows)
    missing_dataset_ids = [case_id for case_id in selected_ids if case_id not in rows_by_id]
    schema_tools = _selected_schema_tools(rows_by_id)
    rule_path = rules_dir / "rule.yaml"
    schema_local = _rule_tools_are_schema_local(rule_path, schema_tools)
    engine = RuleEngine(str(rules_dir), runtime_policy=_load_runtime_policy(runtime_config))

    per_case_selected_tool: dict[str, str | None] = {}
    per_case_blocked_reason: dict[str, str | None] = {}
    per_case_plan: dict[str, dict[str, Any]] = {}
    selected_tools: list[str] = []

    for case_id in selected_ids:
        row = rows_by_id.get(case_id)
        if row is None:
            per_case_selected_tool[case_id] = None
            per_case_blocked_reason[case_id] = "dataset_row_missing"
            per_case_plan[case_id] = {"activated": False, "blocked_reason": "dataset_row_missing"}
            continue

        fallback_plan: dict[str, Any] | None = None
        fallback_turn_index: int | None = None
        activated_plan: dict[str, Any] | None = None
        activated_turn_index: int | None = None
        for turn_index, messages in _turn_prefix_messages(row.get("question")):
            request = _build_plan_request(row, messages)
            _, patches = engine.apply_request(request)
            plan = getattr(patches, "next_tool_plan", {}) or {}
            if fallback_plan is None:
                fallback_plan = plan
                fallback_turn_index = turn_index
            if plan.get("activated"):
                activated_plan = plan
                activated_turn_index = turn_index
                break
            fallback_plan = plan
            fallback_turn_index = turn_index

        chosen_plan = activated_plan or fallback_plan or {"activated": False, "blocked_reason": "empty_question"}
        selected_tool = chosen_plan.get("selected_tool") if chosen_plan.get("activated") else None
        if isinstance(selected_tool, str) and selected_tool:
            selected_tools.append(selected_tool)
            per_case_selected_tool[case_id] = selected_tool
        else:
            per_case_selected_tool[case_id] = None
        per_case_blocked_reason[case_id] = str(chosen_plan.get("blocked_reason") or "unknown")
        per_case_plan[case_id] = {
            "turn_index": activated_turn_index if activated_plan is not None else fallback_turn_index,
            **_compact_plan(chosen_plan),
        }

    distribution = Counter(selected_tools)
    plan_activated_count = sum(1 for value in per_case_selected_tool.values() if value)
    dominant_tool, dominant_count = (None, 0)
    if distribution:
        dominant_tool, dominant_count = distribution.most_common(1)[0]
    dominant_rate = dominant_count / plan_activated_count if plan_activated_count else 0.0
    first_failed = _first_failed_criterion(
        activated_count=plan_activated_count,
        distribution=distribution,
        dominant_rate=dominant_rate,
        dominant_threshold=dominant_threshold,
        schema_local=schema_local,
    )
    gate_passed = first_failed is None and not missing_dataset_ids

    return {
        "manifest_path": str(manifest_path),
        "rules_dir": str(rules_dir),
        "rule_path": str(rule_path),
        "runtime_config": str(runtime_config),
        "category": category,
        "m2_7f_candidate_plan_diversity_passed": gate_passed,
        "selected_case_count": len(selected_ids),
        "plan_activated_count": plan_activated_count,
        "selected_next_tool_distribution": dict(sorted(distribution.items(), key=lambda item: (-item[1], item[0]))),
        "dominant_selected_next_tool": dominant_tool,
        "dominant_selected_next_tool_rate": dominant_rate,
        "dominant_threshold": dominant_threshold,
        "candidate_rules_schema_local": schema_local,
        "candidate_policy_tool_distribution": candidate_policy_tool_distribution(rule_path),
        "selected_schema_tool_count": len(schema_tools),
        "missing_dataset_ids": missing_dataset_ids,
        "per_case_selected_tool": per_case_selected_tool,
        "per_case_blocked_reason": per_case_blocked_reason,
        "per_case_plan": per_case_plan,
        "diagnostic": {
            "checker_scope": "plan_only_no_upstream_model_call",
            "do_not_rerun_m2_7f_until_passed": not gate_passed,
            "first_failed_criterion": "dataset_row_missing" if missing_dataset_ids else first_failed,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check M2.7f candidate plan diversity without calling an upstream model.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_ARTIFACT_ROOT / "paired_subset_manifest.json")
    parser.add_argument("--rules-dir", type=Path, default=DEFAULT_RULES_DIR)
    parser.add_argument("--runtime-config", type=Path, default=DEFAULT_RUNTIME_CONFIG)
    parser.add_argument("--dominant-threshold", type=float, default=0.8)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate_candidate_plan_diversity(
        args.manifest,
        rules_dir=args.rules_dir,
        runtime_config=args.runtime_config,
        dominant_threshold=args.dominant_threshold,
    )
    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2))
    return 0 if report["m2_7f_candidate_plan_diversity_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
