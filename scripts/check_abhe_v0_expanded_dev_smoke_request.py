#!/usr/bin/env python3
"""Validate the ABHE-v0 expanded dev smoke request without authorizing execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_expanded_dev_smoke_request.json")
ALLOWED_ENTRIES = {"state_tracking_v0", "hallucination_abstain_v0"}
ALLOWED_CATEGORIES = {
    "multi_turn_base",
    "multi_turn_long_context",
    "multi_turn_miss_func",
    "multi_turn_miss_param",
    "irrelevance",
    "live_irrelevance",
    "live_relevance",
}
FORCED_FALSE = [
    "authorized",
    "execution_started",
    "fresh_dev_slice_materialized",
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "holdout_authorized",
    "full_suite_authorized",
    "archive_update_authorized",
    "performance_evidence",
    "performance_claim_authorized",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
]


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("artifact must be object")
    return data


def validate(data: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if data.get("artifact_kind") != "abhe_v0_expanded_dev_smoke_request":
        blockers.append("artifact_kind_invalid")
    if data.get("schema_version") != "abhe_v0_expanded_dev_smoke_request_v0":
        blockers.append("schema_version_invalid")
    if data.get("approval_status") != "pending":
        blockers.append("approval_status_not_pending")
    if data.get("scope") != "expanded_dev_smoke_request_only_not_full_bfcl":
        blockers.append("scope_invalid")
    for key in FORCED_FALSE:
        if data.get(key) is not False:
            blockers.append("%s_not_false" % key)
    if data.get("selected_case_ids_hash") != "pending_until_expanded_slice_materialized":
        blockers.append("selected_case_ids_hash_not_pending")
    total_min = data.get("requested_total_case_count_min")
    total_max = data.get("requested_total_case_count_max")
    if total_min < 40 or total_max > 60 or total_min > total_max:
        blockers.append("requested_total_case_count_range_invalid")
    entries = data.get("requested_entries")
    if set(entries or []) != ALLOWED_ENTRIES:
        blockers.append("requested_entries_invalid")
    strata = data.get("requested_strata_by_entry") or {}
    for entry, categories in strata.items():
        if entry not in ALLOWED_ENTRIES:
            blockers.append("unapproved_entry:%s" % entry)
        for category in categories:
            if category not in ALLOWED_CATEGORIES:
                blockers.append("unapproved_category:%s" % category)
    caps = data.get("case_count_caps_by_category") or {}
    for category, cap in caps.items():
        if category not in ALLOWED_CATEGORIES:
            blockers.append("cap_for_unapproved_category:%s" % category)
        if not isinstance(cap, dict) or cap.get("min") < 5 or cap.get("max") > 10 or cap.get("min") > cap.get("max"):
            blockers.append("category_cap_invalid:%s" % category)
    if data.get("source_exclusion_proof_required") is not True:
        blockers.append("source_exclusion_proof_not_required")
    if data.get("source_160_compact_cases_reused_for_validation") is not False:
        blockers.append("source_160_reuse_not_false")
    if data.get("raw_material_absent_required") is not True:
        blockers.append("raw_material_absent_not_required")
    if "same_slice_rerun_stability" not in str(data.get("preconditions", [])):
        blockers.append("same_slice_stability_precondition_missing")
    blockers.extend(scan_value(data, label="abhe_v0_expanded_dev_smoke_request"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT) -> Dict[str, Any]:
    if not path.exists():
        return {
            "report_scope": "abhe_v0_expanded_dev_smoke_request_check",
            "artifact_present": False,
            "abhe_v0_expanded_dev_smoke_request_passed": False,
            "blockers": ["expanded_dev_smoke_request_missing"],
        }
    data = _load(path)
    blockers = validate(data)
    return {
        "report_scope": "abhe_v0_expanded_dev_smoke_request_check",
        "artifact_present": True,
        "abhe_v0_expanded_dev_smoke_request_passed": not blockers,
        "approval_status": data.get("approval_status"),
        "authorized": data.get("authorized"),
        "requested_total_case_count_min": data.get("requested_total_case_count_min"),
        "requested_total_case_count_max": data.get("requested_total_case_count_max"),
        "performance_evidence": data.get("performance_evidence"),
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = check(args.artifact)
    except Exception as exc:
        report = {
            "report_scope": "abhe_v0_expanded_dev_smoke_request_check",
            "abhe_v0_expanded_dev_smoke_request_passed": False,
            "blockers": ["load_failed:%s" % exc.__class__.__name__],
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report.get("abhe_v0_expanded_dev_smoke_request_passed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
