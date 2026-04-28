#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_AUDIT = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_obligation_audit.json")
DEFAULT_NEGATIVE = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_negative_control_audit.json")
DEFAULT_APPROVAL = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_approval_manifest.json")
ALLOWED_RETRIEVE_TOOLS = {"memory_retrieve", "core_memory_retrieve", "core_memory_retrieve_all", "archival_memory_retrieve", "archival_memory_key_search", "core_memory_key_search", "memory_search", "memory_list", "core_memory_list_keys", "archival_memory_list_keys"}
FORBIDDEN_TOOLS = re.compile(r"(clear|remove|delete|add|replace|update|append)", re.IGNORECASE)
REQUIRED_FIELDS = {"candidate_id", "source_audit_record_id", "source_audit_record_pointer_debug_only", "operation", "operation_scope", "recommended_tools", "memory_witness_strength", "forbidden_field_scan", "review_eligible", "risk_level", "runtime_enabled", "exact_tool_choice", "retention_eligibility", "compiler_input_eligible"}
FORBIDDEN_APPROVAL_KEYS = {
    "source_audit_record_pointer_debug_only",
    "trace_relative_path",
    "available_memory_tools",
    "called_memory_tools",
    "case_id",
    "raw_prompt",
    "raw_output",
    "prompt",
    "output",
    "request",
    "request_original",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _forbidden_key_paths(obj: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_path = f"{path}.{key}" if path else str(key)
            if key in FORBIDDEN_APPROVAL_KEYS:
                hits.append(key_path)
            hits.extend(_forbidden_key_paths(value, key_path))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            hits.extend(_forbidden_key_paths(value, f"{path}[{idx}]"))
    return hits


def _check_audit(report: dict[str, Any], failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = report.get("candidate_records") or []
    if report.get("runtime_enabled") is not False:
        failures.append({"check": "runtime_disabled"})
    if report.get("candidate_commands") != [] or report.get("planned_commands") != []:
        failures.append({"check": "no_commands"})
    if not rows:
        failures.append({"check": "candidate_records_present"})
    if int(report.get("candidate_count") or 0) != len(rows):
        failures.append({"check": "candidate_count_matches_records", "reported": report.get("candidate_count"), "actual": len(rows)})
    for idx, row in enumerate(rows):
        missing = sorted(field for field in REQUIRED_FIELDS if field not in row)
        if missing:
            failures.append({"check": "candidate_required_fields", "index": idx, "missing": missing})
        tools = set(row.get("recommended_tools") or [])
        if row.get("operation") != "retrieve" or row.get("operation_scope") != "retrieve_only":
            failures.append({"check": "retrieve_only", "index": idx})
        if not tools or not tools <= ALLOWED_RETRIEVE_TOOLS or any(FORBIDDEN_TOOLS.search(tool) for tool in tools):
            failures.append({"check": "retrieve_tool_allowlist", "index": idx, "tools": sorted(tools)})
        if row.get("runtime_enabled") is not False or row.get("exact_tool_choice") is not False:
            failures.append({"check": "candidate_runtime_disabled_guidance_only", "index": idx})
        if row.get("compiler_input_eligible") is not False:
            failures.append({"check": "candidate_not_compiler_input_before_approval", "index": idx})
        if row.get("memory_witness_strength") == "weak_lookup_witness" and row.get("compiler_input_eligible"):
            failures.append({"check": "weak_witness_requires_separate_approval", "index": idx})
        if row.get("memory_postcondition_witness_present"):
            failures.append({"check": "candidate_must_have_unsatisfied_memory_postcondition", "index": idx})
        scan = row.get("forbidden_field_scan") or {}
        if scan.get("forbidden_dependency_present"):
            failures.append({"check": "forbidden_field_scan", "index": idx})
        if row.get("retention_eligibility") != "diagnostic_only_until_family_review":
            failures.append({"check": "retention_stays_diagnostic", "index": idx})
    return failures


def _check_negative(negative: dict[str, Any], report: dict[str, Any], failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not negative:
        failures.append({"check": "negative_control_audit_present"})
        return failures
    if negative.get("candidate_commands") != [] or negative.get("planned_commands") != []:
        failures.append({"check": "negative_control_no_commands"})
    if negative.get("negative_control_audit_passed") is not True:
        failures.append({"check": "negative_control_audit_passed"})
    if int(negative.get("candidate_count") or 0) != int(report.get("candidate_count") or 0):
        failures.append({"check": "negative_candidate_count_matches_audit", "negative": negative.get("candidate_count"), "audit": report.get("candidate_count")})
    controls = negative.get("negative_control_evaluations") or {}
    required = {"no_memory_tools", "no_memory_intent", "strong_value_witness", "empty_or_error_witness", "delete_clear_forget", "forbidden_dependency"}
    missing = sorted(required - set(controls))
    if missing:
        failures.append({"check": "negative_controls_complete", "missing": missing})
    for name, control in controls.items():
        if int(control.get("activation_count") or 0) != 0 or control.get("passed") is not True:
            failures.append({"check": "negative_control_zero_activation", "control": name, "activation_count": control.get("activation_count")})
    if int(negative.get("weak_witness_compiler_input_count") or 0) != 0:
        failures.append({"check": "weak_witness_not_compiler_input", "count": negative.get("weak_witness_compiler_input_count")})
    return failures


def _check_approval(approval: dict[str, Any], failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not approval:
        failures.append({"check": "approval_manifest_present"})
        return failures
    if approval.get("candidate_commands") != [] or approval.get("planned_commands") != []:
        failures.append({"check": "approval_no_commands"})
    if approval.get("runtime_enabled") is not False or approval.get("compiler_enabled") is not False:
        failures.append({"check": "approval_runtime_compiler_disabled"})
    if approval.get("approval_manifest_sanitized") is not True:
        failures.append({"check": "approval_manifest_sanitized"})
    if approval.get("approval_manifest_ready_for_review") is not True:
        failures.append({"check": "approval_manifest_ready_for_review"})
    if int(approval.get("compiler_input_eligible_count") or 0) != 0:
        failures.append({"check": "approval_has_no_compiler_inputs", "count": approval.get("compiler_input_eligible_count")})
    support_records = approval.get("support_records") or []
    if not support_records:
        failures.append({"check": "approval_support_records_present"})
    forbidden_paths = _forbidden_key_paths(support_records)
    if forbidden_paths:
        failures.append({"check": "approval_manifest_forbidden_keys", "paths": forbidden_paths[:20]})
    for idx, support in enumerate(support_records):
        if not support.get("support_record_hash"):
            failures.append({"check": "approval_support_hash_present", "index": idx})
        if support.get("compiler_input_eligible") is not False:
            failures.append({"check": "approval_support_not_compiler_input", "index": idx})
        if support.get("memory_witness_strength") == "weak_lookup_witness" and support.get("requires_separate_weak_witness_approval") is not True:
            failures.append({"check": "approval_weak_witness_separate_approval", "index": idx})
        families = support.get("recommended_tool_capability_families") or []
        if any(FORBIDDEN_TOOLS.search(str(family)) for family in families):
            failures.append({"check": "approval_forbidden_tool_family", "index": idx, "families": families})
    return failures


def evaluate(
    path: Path = DEFAULT_AUDIT,
    negative_path: Path | None = DEFAULT_NEGATIVE,
    approval_path: Path | None = DEFAULT_APPROVAL,
    *,
    require_approval_artifacts: bool = True,
) -> dict[str, Any]:
    report = _load(path)
    failures: list[dict[str, Any]] = []
    _check_audit(report, failures)
    negative = _load(negative_path) if negative_path else {}
    approval = _load(approval_path) if approval_path else {}
    if require_approval_artifacts:
        _check_negative(negative, report, failures)
        _check_approval(approval, failures)
    return {
        "report_scope": "memory_operation_obligation_boundary_check",
        "memory_operation_obligation_check_passed": not failures,
        "candidate_count": len(report.get("candidate_records") or []),
        "reported_candidate_count": report.get("candidate_count"),
        "negative_control_audit_present": bool(negative),
        "approval_manifest_present": bool(approval),
        "negative_control_audit_passed": negative.get("negative_control_audit_passed") if negative else None,
        "approval_manifest_ready_for_review": approval.get("approval_manifest_ready_for_review") if approval else None,
        "approval_manifest_sanitized": approval.get("approval_manifest_sanitized") if approval else None,
        "failure_count": len(failures),
        "first_failure": failures[0] if failures else None,
        "failures": failures[:50],
        "candidate_commands": report.get("candidate_commands") or [],
        "planned_commands": report.get("planned_commands") or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--negative", type=Path, default=DEFAULT_NEGATIVE)
    parser.add_argument("--approval", type=Path, default=DEFAULT_APPROVAL)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.audit, args.negative, args.approval)
    print(json.dumps(report if not args.compact else {key: report.get(key) for key in ["memory_operation_obligation_check_passed", "candidate_count", "reported_candidate_count", "negative_control_audit_passed", "approval_manifest_ready_for_review", "approval_manifest_sanitized", "failure_count", "first_failure"]}, indent=2, sort_keys=True))
    return 0 if report["memory_operation_obligation_check_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
