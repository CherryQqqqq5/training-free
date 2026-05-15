#!/usr/bin/env python3
"""Validate ABHE review request artifact without granting approval."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_REQUEST = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_review_request.json")
EXPECTED_REVIEWS = [
    "trace_extraction_review",
    "fresh_dev_slice_review",
    "bounded_dev_smoke_execution_review",
]
REQUIRED_FIELDS = {
    "artifact_kind",
    "schema_version",
    "approval_status",
    "authorized",
    "requested_reviews",
    "execution_started",
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "candidate_generation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
}
FALSE_KEYS = REQUIRED_FIELDS - {"artifact_kind", "schema_version", "approval_status", "requested_reviews"}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def validate_request(request: Dict[str, Any]) -> List[str]:
    blockers = []
    missing = sorted(REQUIRED_FIELDS - set(request))
    if missing:
        blockers.append("review_request_required_fields_missing:%s" % ",".join(missing))
        return blockers
    if request.get("artifact_kind") != "abhe_review_request":
        blockers.append("review_request_artifact_kind_invalid:%r" % request.get("artifact_kind"))
    if request.get("schema_version") != "abhe_review_request_v0":
        blockers.append("review_request_schema_version_invalid:%r" % request.get("schema_version"))
    if request.get("approval_status") != "pending":
        blockers.append("review_request_approval_status_must_remain_pending:%r" % request.get("approval_status"))
    if request.get("requested_reviews") != EXPECTED_REVIEWS:
        blockers.append("review_request_requested_reviews_invalid:%r" % request.get("requested_reviews"))
    for key in sorted(FALSE_KEYS):
        if request.get(key) is not False:
            blockers.append("review_request_%s_not_false:%r" % (key, request.get(key)))
    blockers.extend(scan_value(request, label="review_request"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_REQUEST) -> Dict[str, Any]:
    if not path.exists():
        return {
            "report_scope": "abhe_review_request_check",
            "request_path": str(path),
            "request_present": False,
            "abhe_review_request_passed": False,
            "blockers": ["review_request_missing"],
        }
    request = _load(path)
    blockers = validate_request(request)
    return {
        "report_scope": "abhe_review_request_check",
        "request_path": str(path),
        "request_present": True,
        "approval_status": request.get("approval_status"),
        "authorized": request.get("authorized"),
        "execution_started": request.get("execution_started"),
        "performance_evidence": request.get("performance_evidence"),
        "abhe_review_request_passed": not blockers,
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
            "report_scope": "abhe_review_request_check",
            "abhe_review_request_passed": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["abhe_review_request_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
