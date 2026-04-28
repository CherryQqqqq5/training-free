#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

import scripts.check_memory_operation_dry_run_policy as dry_check
import scripts.simulate_memory_operation_activation as activation_sim

DEFAULT_POLICY_DIR = Path("outputs/artifacts/phase2/memory_operation_obligation_dry_run_v1/first_pass")
DEFAULT_OUT_DIR = Path("outputs/artifacts/phase2/memory_operation_obligation_runtime_smoke_v1/first_pass")
POLICY_UNIT_ID = "memory_first_pass_retrieve_soft_v1"
FORBIDDEN_TEXT = re.compile(
    r"(trace_relative_path|source_audit_record|support_record_hash|case_id|run_name|gold|scorer|bfcl_result|raw_prompt|raw_output|request_original|repairs\.jsonl|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def _policy_unit(policy_dir: Path) -> dict[str, Any]:
    payload = _load_yaml(policy_dir / "policy_unit.yaml")
    units = payload.get("policy_units") or []
    if len(units) != 1:
        return {}
    return units[0] if isinstance(units[0], dict) else {}


def _runtime_rule() -> dict[str, Any]:
    fragment = (
        "When the user asks for memory-backed information and no memory tool result is present, "
        "prefer a read-only memory retrieval, search, or list capability before final prose. "
        "Keep the action capability-only: use values already grounded by the current request or tool schema, "
        "and do not invent arguments."
    )
    return {
        "rule_id": "memory_first_pass_retrieve_soft_v1_runtime_adapter",
        "priority": 8,
        "enabled": True,
        "trigger": {
            "error_types": ["memory_first_pass_retrieve_obligation"],
            "request_predicates": [
                "tools_available",
                "memory_tools_available",
                "no_prior_tool_outputs_present",
            ],
        },
        "scope": {"patch_sites": ["prompt_injector"]},
        "action": {
            "prompt_fragments": [fragment],
            "decision_policy": {
                "request_predicates": [
                    "tools_available",
                    "memory_tools_available",
                    "no_prior_tool_outputs_present",
                ],
                "recommended_tools": [],
                "candidate_commands": [],
                "planned_commands": [],
            },
        },
    }


def evaluate(policy_dir: Path = DEFAULT_POLICY_DIR) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    dry_report = dry_check.evaluate(policy_dir)
    activation_report = activation_sim.evaluate()
    unit = _policy_unit(policy_dir)
    if dry_report.get("dry_run_policy_boundary_check_passed") is not True:
        failures.append({"check": "dry_run_policy_boundary_check_passed", "detail": dry_report.get("first_failure")})
    if activation_report.get("activation_simulation_passed") is not True:
        failures.append({"check": "activation_simulation_passed"})
    if unit.get("policy_unit_id") != POLICY_UNIT_ID:
        failures.append({"check": "expected_policy_unit", "policy_unit_id": unit.get("policy_unit_id")})
    if unit.get("runtime_enabled") is not False:
        failures.append({"check": "source_policy_unit_runtime_disabled"})
    if unit.get("exact_tool_choice") is not False:
        failures.append({"check": "source_policy_unit_exact_tool_choice_false"})
    decision = unit.get("decision_policy") if isinstance(unit.get("decision_policy"), dict) else {}
    if decision.get("argument_policy") != "no_argument_creation_or_binding":
        failures.append({"check": "source_policy_unit_no_argument_creation"})
    rule = _runtime_rule()
    text = yaml.safe_dump(rule, sort_keys=True)
    if FORBIDDEN_TEXT.search(text):
        failures.append({"check": "runtime_rule_forbidden_text"})
    return {
        "report_scope": "memory_operation_runtime_smoke_adapter_compile",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "policy_unit_id": POLICY_UNIT_ID,
        "runtime_adapter_compile_ready": not failures,
        "runtime_rule_count": 1 if not failures else 0,
        "runtime_enabled_by_default": False,
        "smoke_requires_explicit_approval": True,
        "exact_tool_choice": False,
        "argument_creation_count": 0,
        "candidate_commands": [],
        "planned_commands": [],
        "rule": rule if not failures else None,
        "failure_count": len(failures),
        "first_failure": failures[0] if failures else None,
        "failures": failures[:50],
        "next_required_action": "run_runtime_smoke_readiness_checker" if not failures else "fix_runtime_adapter_compile_inputs",
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if report.get("rule"):
        (out_dir / "rule.yaml").write_text(yaml.safe_dump(report["rule"], sort_keys=True), encoding="utf-8")
    status = {key: report.get(key) for key in [
        "report_scope",
        "offline_only",
        "does_not_call_bfcl_or_model",
        "does_not_authorize_scorer",
        "policy_unit_id",
        "runtime_adapter_compile_ready",
        "runtime_rule_count",
        "runtime_enabled_by_default",
        "smoke_requires_explicit_approval",
        "exact_tool_choice",
        "argument_creation_count",
        "candidate_commands",
        "planned_commands",
        "failure_count",
        "first_failure",
        "next_required_action",
    ]}
    (out_dir / "memory_operation_runtime_adapter_compile_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md = [
        "# Memory Operation Runtime Smoke Adapter",
        "",
        f"- Compile ready: `{status['runtime_adapter_compile_ready']}`",
        f"- Runtime rule count: `{status['runtime_rule_count']}`",
        f"- Exact tool choice: `{status['exact_tool_choice']}`",
        f"- Argument creation count: `{status['argument_creation_count']}`",
        f"- Does not authorize scorer: `{status['does_not_authorize_scorer']}`",
        f"- First failure: `{status['first_failure']}`",
        "",
    ]
    (out_dir / "memory_operation_runtime_adapter_compile_status.md").write_text("\n".join(md), encoding="utf-8")


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
            "runtime_adapter_compile_ready",
            "runtime_rule_count",
            "exact_tool_choice",
            "argument_creation_count",
            "does_not_authorize_scorer",
            "candidate_commands",
            "planned_commands",
            "failure_count",
            "first_failure",
            "next_required_action",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    return 0 if report["runtime_adapter_compile_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
