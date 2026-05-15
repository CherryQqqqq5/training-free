#!/usr/bin/env python3
"""Validate the ABHE fresh dev slice request without materializing a slice."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_REQUEST = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_fresh_dev_slice_request.json")
EXPECTED_ENTRY_IDS = ["state_tracking_v0", "hallucination_abstain_v0"]
REQUIRED_FIELDS = {
    "artifact_kind",
    "schema_version",
    "approval_status",
    "authorized",
    "slice_materialized",
    "entry_ids",
    "fresh_dev_slice_required",
    "archive_seed_source_excluded",
    "source_160_compact_cases_reused_for_validation",
    "case_list_hash",
    "case_count_cap",
    "stratification",
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "performance_evidence",
}
FALSE_KEYS = {
    "authorized",
    "slice_materialized",
    "source_160_compact_cases_reused_for_validation",
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "performance_evidence",
}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def validate_request(request: Dict[str, Any]) -> List[str]:
    blockers = []
    missing = sorted(REQUIRED_FIELDS - set(request))
    if missing:
        blockers.append("fresh_slice_request_required_fields_missing:%s" % ",".join(missing))
        return blockers
    if request.get("artifact_kind") != "abhe_fresh_dev_slice_request":
        blockers.append("fresh_slice_request_artifact_kind_invalid:%r" % request.get("artifact_kind"))
    if request.get("schema_version") != "abhe_fresh_dev_slice_request_v0":
        blockers.append("fresh_slice_request_schema_version_invalid:%r" % request.get("schema_version"))
    if request.get("approval_status") != "pending":
        blockers.append("fresh_slice_request_approval_status_must_remain_pending:%r" % request.get("approval_status"))
    if request.get("entry_ids") != EXPECTED_ENTRY_IDS:
        blockers.append("fresh_slice_request_entry_ids_invalid:%r" % request.get("entry_ids"))
    if request.get("fresh_dev_slice_required") is not True:
        blockers.append("fresh_slice_request_fresh_dev_slice_required_not_true")
    if request.get("archive_seed_source_excluded") is not True:
        blockers.append("fresh_slice_request_archive_seed_source_excluded_not_true")
    if request.get("case_list_hash") != "pending":
        blockers.append("fresh_slice_request_case_list_hash_must_remain_pending:%r" % request.get("case_list_hash"))
    if request.get("case_count_cap") != "pending_review":
        blockers.append("fresh_slice_request_case_count_cap_invalid:%r" % request.get("case_count_cap"))
    if request.get("stratification") != "behavior_first_bfcl_stratified":
        blockers.append("fresh_slice_request_stratification_invalid:%r" % request.get("stratification"))
    for key in sorted(FALSE_KEYS):
        if request.get(key) is not False:
            blockers.append("fresh_slice_request_%s_not_false:%r" % (key, request.get(key)))
    blockers.extend(scan_value(request, label="fresh_slice_request"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_REQUEST) -> Dict[str, Any]:
    if not path.exists():
        return {
            "report_scope": "abhe_fresh_dev_slice_request_check",
            "request_path": str(path),
            "request_present": False,
            "abhe_fresh_dev_slice_request_passed": False,
            "blockers": ["fresh_slice_request_missing"],
        }
    request = _load(path)
    blockers = validate_request(request)
    return {
        "report_scope": "abhe_fresh_dev_slice_request_check",
        "request_path": str(path),
        "request_present": True,
        "approval_status": request.get("approval_status"),
        "authorized": request.get("authorized"),
        "slice_materialized": request.get("slice_materialized"),
        "source_160_compact_cases_reused_for_validation": request.get("source_160_compact_cases_reused_for_validation"),
        "performance_evidence": request.get("performance_evidence"),
        "abhe_fresh_dev_slice_request_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.request)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "abhe_fresh_dev_slice_request_check",
            "abhe_fresh_dev_slice_request_passed": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["abhe_fresh_dev_slice_request_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
