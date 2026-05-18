#!/usr/bin/env python3
"""Validate ABHE runtime-slot observability review artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_observability_review.json")
FALSE_FIELDS = [
    "authorized",
    "review_is_execution_approval",
    "bfcl_rerun_authorized",
    "provider_calls_authorized",
    "provider_calls_made",
    "bfcl_generate_authorized",
    "bfcl_generate_called",
    "bfcl_evaluate_authorized",
    "bfcl_evaluate_called",
    "scorer_authorized",
    "scorer_called",
    "holdout_touched",
    "full_suite_touched",
    "archive_updated",
    "performance_evidence",
    "candidate_jsonl_generated",
    "candidate_yaml_generated",
    "candidate_rule_generated",
]


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_runtime_slot_observability_review":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_runtime_slot_observability_review_v0":
        blockers.append("schema_version_invalid")
    if data.get("review_status") != "passed":
        blockers.append("review_status_not_passed")
    if data.get("observability_review_passed") is not True:
        blockers.append("observability_review_not_passed")
    if data.get("safe_fields_only") is not True or data.get("raw_material_absent") is not True:
        blockers.append("safe_boundary_not_true")
    for key in FALSE_FIELDS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false")
    findings = data.get("review_findings") if isinstance(data.get("review_findings"), dict) else {}
    if findings.get("observability_plan_check_passed") is not True:
        blockers.append("plan_check_not_passed")
    if findings.get("observability_fixture_check_passed") is not True:
        blockers.append("fixture_check_not_passed")
    if int(findings.get("bind_repair_rows") or 0) <= 0:
        blockers.append("bind_repair_rows_missing")
    if int(findings.get("provider_generated_valid_call_proxy_rows") or 0) <= 0:
        blockers.append("provider_generated_valid_call_proxy_rows_missing")
    if findings.get("direct_slot_binding_causality_for_prior_bfcl_run_confirmed") is not False:
        blockers.append("prior_bfcl_causality_overclaimed")
    if data.get("next_required_action") != "request_bounded_bfcl_rerun_approval_with_observability_enabled":
        blockers.append("next_required_action_invalid")
    if data.get("blockers"):
        blockers.extend(str(item) for item in data.get("blockers") if str(item))
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    try:
        data = _load(path)
        blockers = validate(data)
    except Exception as exc:
        data = {}
        blockers = [f"load_failed:{exc.__class__.__name__}"]
    findings = data.get("review_findings") if isinstance(data.get("review_findings"), dict) else {}
    return {
        "report_scope": "abhe_v0_runtime_slot_observability_review_check",
        "artifact_path": str(path),
        "observability_review_check_passed": not blockers,
        "blockers": blockers,
        "observability_review_passed": data.get("observability_review_passed"),
        "bfcl_rerun_authorized": data.get("bfcl_rerun_authorized", False),
        "performance_evidence": data.get("performance_evidence", False),
        "bind_repair_rows": findings.get("bind_repair_rows"),
        "provider_generated_valid_call_proxy_rows": findings.get("provider_generated_valid_call_proxy_rows"),
        "next_required_action": data.get("next_required_action"),
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = check(args.path)
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["observability_review_check_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
