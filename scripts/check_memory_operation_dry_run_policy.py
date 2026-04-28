#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

DEFAULT_DIR = Path("outputs/artifacts/phase2/memory_operation_obligation_dry_run_v1/first_pass")
ALLOWED_CAPABILITY_FAMILIES = {"memory_key_or_text_search", "memory_list_keys", "memory_value_retrieve"}
FORBIDDEN_RUNTIME_TEXT = re.compile(r"(trace_relative_path|source_audit_record|support_record_hash|case_id|run_name|gold|scorer|bfcl_result|raw_prompt|raw_output|request_original|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.IGNORECASE)
FORBIDDEN_TOOL_FAMILY_TEXT = re.compile(r"(clear|remove|delete|add|replace|update|append)", re.IGNORECASE)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def evaluate(policy_dir: Path = DEFAULT_DIR) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    policy_path = policy_dir / "policy_unit.yaml"
    approval_path = policy_dir / "policy_approval_manifest.json"
    status_path = policy_dir / "compile_status.json"
    policy = _load_yaml(policy_path)
    approval = _load_json(approval_path)
    status = _load_json(status_path)
    units = policy.get("policy_units") or []
    runtime_text = yaml.safe_dump(policy, sort_keys=True)
    if FORBIDDEN_RUNTIME_TEXT.search(runtime_text):
        failures.append({"check": "runtime_policy_forbidden_text", "reason": "policy_unit.yaml contains support/case/scorer-like text"})
    if policy.get("runtime_enabled") is not False or approval.get("runtime_enabled") is not False or status.get("runtime_enabled") is not False:
        failures.append({"check": "runtime_disabled"})
    if approval.get("compiler_enabled") is not False or status.get("compiler_enabled") is not False:
        failures.append({"check": "compiler_disabled"})
    if policy.get("candidate_commands") != [] or policy.get("planned_commands") != []:
        failures.append({"check": "policy_has_commands"})
    if approval.get("candidate_commands") != [] or approval.get("planned_commands") != []:
        failures.append({"check": "approval_has_commands"})
    if status.get("candidate_commands") != [] or status.get("planned_commands") != []:
        failures.append({"check": "status_has_commands"})
    if len(units) != 1:
        failures.append({"check": "single_policy_unit", "count": len(units)})
    for idx, unit in enumerate(units):
        trigger = unit.get("trigger") or {}
        decision = unit.get("decision_policy") or {}
        families = set(decision.get("recommended_tool_capability_families") or [])
        if unit.get("policy_unit_id") != "memory_first_pass_retrieve_soft_v1":
            failures.append({"check": "unit_id", "index": idx})
        if unit.get("runtime_enabled") is not False:
            failures.append({"check": "unit_runtime_disabled", "index": idx})
        if unit.get("exact_tool_choice") is not False or unit.get("tool_choice_mode") != "soft":
            failures.append({"check": "soft_guidance_only", "index": idx})
        if trigger.get("operation") != "retrieve" or trigger.get("memory_witness_strength") != "no_witness":
            failures.append({"check": "first_pass_trigger", "index": idx})
        if trigger.get("strong_value_witness_present") is not False or trigger.get("empty_or_error_witness_present") is not False:
            failures.append({"check": "unsatisfied_memory_postcondition_only", "index": idx})
        if decision.get("argument_policy") != "no_argument_creation_or_binding":
            failures.append({"check": "no_argument_creation", "index": idx})
        if decision.get("capability_only") is not True:
            failures.append({"check": "capability_only", "index": idx})
        if not families or not families <= ALLOWED_CAPABILITY_FAMILIES:
            failures.append({"check": "allowed_capability_families", "index": idx, "families": sorted(families)})
        if any(FORBIDDEN_TOOL_FAMILY_TEXT.search(str(family)) for family in families):
            failures.append({"check": "forbidden_capability_family", "index": idx, "families": sorted(families)})
        if int(unit.get("support_count") or 0) < 1:
            failures.append({"check": "support_count_present", "index": idx})
    if int(status.get("selected_first_pass_count") or 0) != int(approval.get("selected_first_pass_count") or 0):
        failures.append({"check": "status_approval_support_count_match"})
    if int(status.get("excluded_weak_witness_count") or 0) != 0 or int(approval.get("excluded_weak_witness_count") or 0) != 0:
        failures.append({"check": "weak_witness_excluded"})
    if int(status.get("argument_creation_count") or 0) != 0 or int(approval.get("argument_creation_count") or 0) != 0:
        failures.append({"check": "argument_creation_zero"})
    if status.get("dry_run_policy_compile_ready") is not True:
        failures.append({"check": "compile_ready"})
    return {
        "report_scope": "memory_operation_dry_run_policy_boundary_check",
        "policy_dir": str(policy_dir),
        "policy_unit_count": len(units),
        "selected_first_pass_count": approval.get("selected_first_pass_count"),
        "argument_creation_count": approval.get("argument_creation_count"),
        "dry_run_policy_boundary_check_passed": not failures,
        "failure_count": len(failures),
        "first_failure": failures[0] if failures else None,
        "failures": failures[:50],
        "candidate_commands": approval.get("candidate_commands") or [],
        "planned_commands": approval.get("planned_commands") or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.policy_dir)
    print(json.dumps(report if not args.compact else {key: report.get(key) for key in [
        "dry_run_policy_boundary_check_passed",
        "policy_unit_count",
        "selected_first_pass_count",
        "argument_creation_count",
        "failure_count",
        "first_failure",
    ]}, indent=2, sort_keys=True))
    return 0 if report["dry_run_policy_boundary_check_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
