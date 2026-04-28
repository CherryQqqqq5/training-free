#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/postcondition_guided_policy_candidate_manifest.json")
LOW_RISK_TOOLS = {"cat", "find", "grep"}
LOW_RISK_GAPS = {"read_content", "search_or_find"}
REQUIRED_CANDIDATE_FIELDS = {
    "source_audit_record_id",
    "source_audit_record_pointer",
    "available_tools",
    "disambiguation_cue",
    "ambiguity_flags",
    "rejection_reason",
    "negative_control_bucket",
    "forbidden_field_scan",
    "low_risk_dry_run_review_eligible",
    "dry_run_review_rejection_reason",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def evaluate(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = _load(path)
    failures: list[dict[str, Any]] = []
    rows = manifest.get("candidate_records") or []
    if manifest.get("runtime_enabled") is not False:
        failures.append({"check": "runtime_disabled", "reason": "manifest runtime_enabled must be false"})
    if manifest.get("candidate_commands") != [] or manifest.get("planned_commands") != []:
        failures.append({"check": "no_commands", "reason": "policy manifest must not emit scorer commands"})
    if not rows:
        failures.append({"check": "candidate_records_present", "reason": "manifest has no candidate records"})
    for idx, row in enumerate(rows):
        missing = sorted(field for field in REQUIRED_CANDIDATE_FIELDS if field not in row)
        if missing:
            failures.append({"check": "required_candidate_fields", "candidate_index": idx, "missing": missing})
        scan = row.get("forbidden_field_scan") or {}
        if not isinstance(scan, dict) or scan.get("forbidden_dependency_present"):
            failures.append({"check": "forbidden_field_scan", "candidate_index": idx, "candidate_id": row.get("candidate_id")})
        if row.get("runtime_enabled") is not False:
            failures.append({"check": "candidate_runtime_disabled", "candidate_index": idx, "candidate_id": row.get("candidate_id")})
        if row.get("exact_tool_choice") is not False:
            failures.append({"check": "no_exact_tool_choice", "candidate_index": idx, "candidate_id": row.get("candidate_id")})
        if row.get("low_risk_dry_run_review_eligible"):
            tools = set(row.get("recommended_tools") or [])
            if row.get("risk_level") != "low" or row.get("postcondition_gap") not in LOW_RISK_GAPS or not tools <= LOW_RISK_TOOLS:
                failures.append({"check": "low_risk_review_boundary", "candidate_index": idx, "candidate_id": row.get("candidate_id")})
    return {
        "report_scope": "postcondition_guided_policy_manifest_boundary_check",
        "manifest_path": str(path),
        "candidate_count": len(rows),
        "low_risk_dry_run_review_eligible_count": sum(1 for row in rows if row.get("low_risk_dry_run_review_eligible")),
        "required_candidate_fields": sorted(REQUIRED_CANDIDATE_FIELDS),
        "postcondition_guided_policy_manifest_check_passed": not failures,
        "first_failure": failures[0] if failures else None,
        "failure_count": len(failures),
        "failures": failures[:50],
        "candidate_commands": manifest.get("candidate_commands") or [],
        "planned_commands": manifest.get("planned_commands") or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.manifest)
    print(json.dumps(report if not args.compact else {key: report.get(key) for key in [
        "postcondition_guided_policy_manifest_check_passed",
        "candidate_count",
        "low_risk_dry_run_review_eligible_count",
        "failure_count",
        "first_failure",
    ]}, indent=2, sort_keys=True))
    return 0 if report["postcondition_guided_policy_manifest_check_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
