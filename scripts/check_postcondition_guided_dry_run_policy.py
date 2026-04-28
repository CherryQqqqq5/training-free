#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

DEFAULT_DIR = Path("outputs/artifacts/phase2/postcondition_guided_policy_dry_run_v1/approved_low_risk")
FORBIDDEN_RUNTIME_TEXT = re.compile(r"(trace_relative_path|source_audit_record|candidate_id|run_name|gold|scorer|bfcl_result|multi_turn_[a-z_]+_\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.IGNORECASE)
ALLOWED_TOOLS = {"cat", "find", "grep"}
ALLOWED_GAPS = {"read_content", "search_or_find"}


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
        failures.append({"check": "runtime_policy_forbidden_text", "reason": "policy_unit.yaml contains trace/case/scorer-like text"})
    if policy.get("runtime_enabled") is not False or approval.get("runtime_enabled") is not False or status.get("runtime_enabled") is not False:
        failures.append({"check": "runtime_disabled", "reason": "dry-run artifacts must keep runtime disabled"})
    if policy.get("candidate_commands") != [] or policy.get("planned_commands") != []:
        failures.append({"check": "policy_has_commands"})
    if approval.get("candidate_commands") != [] or approval.get("planned_commands") != []:
        failures.append({"check": "approval_has_commands"})
    if not units:
        failures.append({"check": "policy_units_present"})
    for idx, unit in enumerate(units):
        tools = set(((unit.get("decision_policy") or {}).get("recommended_tools") or []))
        trigger = unit.get("trigger") or {}
        if unit.get("runtime_enabled") is not False:
            failures.append({"check": "unit_runtime_disabled", "index": idx})
        if unit.get("exact_tool_choice") is not False or unit.get("tool_choice_mode") != "soft":
            failures.append({"check": "soft_guidance_only", "index": idx})
        if trigger.get("postcondition_gap") not in ALLOWED_GAPS or not tools or not tools <= ALLOWED_TOOLS:
            failures.append({"check": "low_risk_scope", "index": idx})
        if (unit.get("decision_policy") or {}).get("argument_policy") != "no_argument_creation_or_binding":
            failures.append({"check": "no_argument_creation", "index": idx})
    if approval.get("selected_non_ambiguous_low_risk_count", 0) < 1:
        failures.append({"check": "approval_support_present"})
    return {
        "report_scope": "postcondition_guided_dry_run_policy_boundary_check",
        "policy_dir": str(policy_dir),
        "policy_unit_count": len(units),
        "selected_non_ambiguous_low_risk_count": approval.get("selected_non_ambiguous_low_risk_count"),
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
        "selected_non_ambiguous_low_risk_count",
        "failure_count",
        "first_failure",
    ]}, indent=2, sort_keys=True))
    return 0 if report["dry_run_policy_boundary_check_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
