#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_AUDIT = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_obligation_audit.json")
ALLOWED_RETRIEVE_TOOLS = {"memory_retrieve", "core_memory_retrieve", "core_memory_retrieve_all", "archival_memory_retrieve", "archival_memory_key_search", "core_memory_key_search", "memory_search", "memory_list", "core_memory_list_keys", "archival_memory_list_keys"}
FORBIDDEN_TOOLS = re.compile(r"(clear|remove|delete|add|replace|update|append)", re.IGNORECASE)
REQUIRED_FIELDS = {"candidate_id", "source_audit_record_id", "source_audit_record_pointer_debug_only", "operation", "operation_scope", "recommended_tools", "memory_witness_strength", "forbidden_field_scan", "review_eligible", "risk_level", "runtime_enabled", "exact_tool_choice", "retention_eligibility"}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def evaluate(path: Path = DEFAULT_AUDIT) -> dict[str, Any]:
    report = _load(path)
    failures: list[dict[str, Any]] = []
    rows = report.get("candidate_records") or []
    if report.get("runtime_enabled") is not False:
        failures.append({"check": "runtime_disabled"})
    if report.get("candidate_commands") != [] or report.get("planned_commands") != []:
        failures.append({"check": "no_commands"})
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
        if row.get("memory_postcondition_witness_present"):
            failures.append({"check": "candidate_must_have_unsatisfied_memory_postcondition", "index": idx})
        scan = row.get("forbidden_field_scan") or {}
        if scan.get("forbidden_dependency_present"):
            failures.append({"check": "forbidden_field_scan", "index": idx})
        if row.get("retention_eligibility") != "diagnostic_only_until_family_review":
            failures.append({"check": "retention_stays_diagnostic", "index": idx})
    return {
        "report_scope": "memory_operation_obligation_boundary_check",
        "memory_operation_obligation_check_passed": not failures,
        "candidate_count": len(rows),
        "failure_count": len(failures),
        "first_failure": failures[0] if failures else None,
        "failures": failures[:50],
        "candidate_commands": report.get("candidate_commands") or [],
        "planned_commands": report.get("planned_commands") or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.audit)
    print(json.dumps(report if not args.compact else {key: report.get(key) for key in ["memory_operation_obligation_check_passed", "candidate_count", "failure_count", "first_failure"]}, indent=2, sort_keys=True))
    return 0 if report["memory_operation_obligation_check_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
