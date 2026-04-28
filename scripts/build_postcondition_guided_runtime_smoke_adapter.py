#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

import scripts.audit_postcondition_guided_dry_run_activation as activation_audit
import scripts.check_postcondition_guided_dry_run_policy as dry_check

DEFAULT_POLICY_DIR = Path("outputs/artifacts/phase2/postcondition_guided_policy_dry_run_v1/approved_low_risk")
DEFAULT_OUT_DIR = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk")
FORBIDDEN_TEXT = re.compile(
    r"(trace_relative_path|source_audit_record|candidate_id|run_name|gold|scorer|bfcl_result|raw_prompt|raw_output|request_original|repairs\.jsonl|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
GAP_PREDICATES = {
    "read_content": "postcondition_gap_read_content",
    "search_or_find": "postcondition_gap_search_or_find",
}
ERROR_TYPES = ["actionable_no_tool_decision", "post_tool_prose_summary"]


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def _policy_units(policy_dir: Path) -> list[dict[str, Any]]:
    payload = _load_yaml(policy_dir / "policy_unit.yaml")
    return [unit for unit in payload.get("policy_units") or [] if isinstance(unit, dict)]


def _runtime_rule(unit: dict[str, Any]) -> dict[str, Any]:
    gap = str((unit.get("trigger") or {}).get("postcondition_gap") or "")
    tools = [str(item) for item in ((unit.get("decision_policy") or {}).get("recommended_tools") or []) if str(item).strip()]
    predicate = GAP_PREDICATES[gap]
    request_predicates = ["tools_available", "prior_tool_outputs_present", predicate]
    fragment = (
        "When prior tool output is present and the current request still has an unsatisfied "
        f"`{gap}` postcondition, prefer the schema-available capability family "
        + ", ".join(f"`{tool}`" for tool in tools)
        + ". This is capability-only guidance: do not force exact tool choice, do not create arguments, "
        "and do not use benchmark answers, grading artifacts, or evaluation-specific identifiers."
    )
    return {
        "rule_id": f"{unit.get('policy_unit_id')}_runtime_adapter",
        "priority": 6,
        "enabled": True,
        "trigger": {"error_types": ERROR_TYPES, "request_predicates": request_predicates},
        "scope": {"patch_sites": ["prompt_injector", "policy_executor"]},
        "action": {
            "prompt_fragments": [fragment],
            "decision_policy": {
                "request_predicates": request_predicates,
                "recommended_tools": tools,
                "action_candidates": [],
                "continue_condition": "a schema-local capability can advance the observable postcondition without creating arguments",
                "stop_condition": "prose-only termination is admissible only when the postcondition is already satisfied or no local capability is available",
                "forbidden_terminations": ["prose_only_no_tool_termination"],
                "evidence_requirements": request_predicates,
                "next_tool_policy": {
                    "activation_predicates": request_predicates,
                    "recommended_tools": tools,
                    "tool_choice_mode": "soft",
                    "confidence": 0.65,
                },
            },
        },
    }


def evaluate(policy_dir: Path = DEFAULT_POLICY_DIR) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    dry_report = dry_check.evaluate(policy_dir)
    activation_report = activation_audit.evaluate(policy_dir)
    if dry_report.get("dry_run_policy_boundary_check_passed") is not True:
        failures.append({"check": "dry_run_policy_boundary_check_passed", "detail": dry_report.get("first_failure")})
    if activation_report.get("negative_control_activation_count") not in {0, None}:
        failures.append({"check": "negative_control_activation_count_zero"})
    if int(activation_report.get("generic_low_risk_match_with_ambiguity_guard_count") or 0) < 1:
        failures.append({"check": "generic_low_risk_match_with_ambiguity_guard_present"})
    rules: list[dict[str, Any]] = []
    for idx, unit in enumerate(_policy_units(policy_dir)):
        if unit.get("runtime_enabled") is not False:
            failures.append({"check": "source_unit_runtime_disabled", "index": idx})
        if unit.get("exact_tool_choice") is not False or unit.get("tool_choice_mode") != "soft":
            failures.append({"check": "source_unit_soft_guidance_only", "index": idx})
        decision = unit.get("decision_policy") if isinstance(unit.get("decision_policy"), dict) else {}
        if decision.get("argument_policy") != "no_argument_creation_or_binding" or decision.get("capability_only") is not True:
            failures.append({"check": "source_unit_capability_only_no_args", "index": idx})
        gap = str((unit.get("trigger") or {}).get("postcondition_gap") or "")
        if gap not in GAP_PREDICATES:
            failures.append({"check": "source_unit_allowed_gap", "index": idx, "gap": gap})
            continue
        rule = _runtime_rule(unit)
        text = yaml.safe_dump(rule, sort_keys=True)
        if FORBIDDEN_TEXT.search(text):
            failures.append({"check": "runtime_rule_forbidden_text", "index": idx})
        rules.append(rule)
    return {
        "report_scope": "postcondition_guided_runtime_smoke_adapter_compile",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "runtime_adapter_compile_ready": not failures and bool(rules),
        "runtime_rule_count": len(rules) if not failures else 0,
        "runtime_enabled_by_default": False,
        "smoke_requires_explicit_approval": True,
        "exact_tool_choice": False,
        "argument_creation_count": 0,
        "trace_level_ambiguity_guard_runtime_predicates": sorted(GAP_PREDICATES.values()),
        "candidate_commands": [],
        "planned_commands": [],
        "failure_count": len(failures),
        "first_failure": failures[0] if failures else None,
        "failures": failures[:50],
        "rules": rules if not failures else [],
        "next_required_action": "run_postcondition_guided_runtime_smoke_readiness_checker" if not failures else "fix_runtime_adapter_compile_inputs",
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if report.get("rules"):
        (out_dir / "rule.yaml").write_text(yaml.safe_dump({"patch_id": "postcondition_guided_runtime_smoke_adapter", "rules": report["rules"]}, sort_keys=True), encoding="utf-8")
    status_keys = [
        "report_scope", "offline_only", "does_not_call_bfcl_or_model", "does_not_authorize_scorer",
        "runtime_adapter_compile_ready", "runtime_rule_count", "runtime_enabled_by_default",
        "smoke_requires_explicit_approval", "exact_tool_choice", "argument_creation_count",
        "trace_level_ambiguity_guard_runtime_predicates", "candidate_commands", "planned_commands",
        "failure_count", "first_failure", "next_required_action",
    ]
    status = {key: report.get(key) for key in status_keys}
    (out_dir / "postcondition_guided_runtime_adapter_compile_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    md = [
        "# Postcondition-Guided Runtime Smoke Adapter",
        "",
        f"- Compile ready: `{status['runtime_adapter_compile_ready']}`",
        f"- Runtime rule count: `{status['runtime_rule_count']}`",
        f"- Exact tool choice: `{status['exact_tool_choice']}`",
        f"- Argument creation count: `{status['argument_creation_count']}`",
        f"- Does not authorize scorer: `{status['does_not_authorize_scorer']}`",
        f"- First failure: `{status['first_failure']}`",
        "",
    ]
    (out_dir / "postcondition_guided_runtime_adapter_compile_status.md").write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy-dir", type=Path, default=DEFAULT_POLICY_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.policy_dir)
    write_outputs(report, args.output_dir)
    if args.compact:
        keys = [
            "runtime_adapter_compile_ready", "runtime_rule_count", "exact_tool_choice",
            "argument_creation_count", "does_not_authorize_scorer", "candidate_commands",
            "planned_commands", "failure_count", "first_failure", "next_required_action",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    return 0 if report["runtime_adapter_compile_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
