#!/usr/bin/env python3
"""Validate RASHE approval matrix after bounded source approval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_MATRIX = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_approval_packet_review_matrix.json")
EXPECTED_LANES = [
    "runtime_behavior_approval",
    "source_real_trace_approval",
    "candidate_proposer_execution_approval",
    "scorer_dev_holdout_full_approval",
    "performance_3pp_huawei_acceptance_approval",
]
APPROVED_LANES = {"runtime_behavior_approval", "source_real_trace_approval"}
PENDING_LANES = set(EXPECTED_LANES) - APPROVED_LANES
FORBIDDEN_TRUE_FIELDS = (
    "raw_trace_capture_authorized",
    "raw_payload_capture_authorized",
    "candidate_generation_authorized",
    "candidate_pool_ready",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "bfcl_performance_ready",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def check(matrix_path: Path = DEFAULT_MATRIX) -> dict[str, Any]:
    matrix = load_json(matrix_path)
    blockers: list[str] = []
    lanes = matrix.get("lanes") if isinstance(matrix.get("lanes"), list) else []
    if not lanes:
        blockers.append("lanes_missing_or_not_list")
    lane_ids = [lane.get("lane_id") for lane in lanes if isinstance(lane, dict)]
    lane_by_id = {lane.get("lane_id"): lane for lane in lanes if isinstance(lane, dict)}
    if lane_ids != EXPECTED_LANES:
        blockers.append("lane_order_mismatch")
    if matrix.get("current_status") != "runtime_and_source_lanes_approved_downstream_pending":
        blockers.append("matrix_current_status_invalid")
    if matrix.get("runtime_behavior_authorized") is not True:
        blockers.append("matrix_runtime_behavior_authorized_not_true")
    if matrix.get("source_real_trace_approval_status") != "approved":
        blockers.append("matrix_source_status_not_approved")
    if matrix.get("source_real_trace_authorized") is not True:
        blockers.append("matrix_source_authorized_not_true")
    if matrix.get("source_collection_authorized") is not True:
        blockers.append("matrix_source_collection_authorized_not_true")
    if matrix.get("provider_calls_authorized") is not True:
        blockers.append("matrix_provider_calls_authorized_not_true")
    for field in FORBIDDEN_TRUE_FIELDS:
        if matrix.get(field) is True:
            blockers.append(f"matrix_forbidden_ready_field_true:{field}")

    for lane_id in EXPECTED_LANES:
        lane = lane_by_id.get(lane_id)
        if not isinstance(lane, dict):
            blockers.append(f"lane_missing:{lane_id}")
            continue
        if lane_id in APPROVED_LANES:
            if lane.get("current_status") != "approved":
                blockers.append(f"approved_lane_status_invalid:{lane_id}:{lane.get('current_status')}")
            if lane.get("authorized") is not True:
                blockers.append(f"approved_lane_authorized_not_true:{lane_id}")
        elif lane_id in PENDING_LANES:
            if lane.get("current_status") != "pending":
                blockers.append(f"pending_lane_status_invalid:{lane_id}:{lane.get('current_status')}")
            if lane.get("authorized") is not False:
                blockers.append(f"pending_lane_authorized_not_false:{lane_id}")
    source = lane_by_id.get("source_real_trace_approval", {})
    if isinstance(source, dict):
        if source.get("approval_checker_path") != "scripts/check_rashe_source_real_trace_approved.py":
            blockers.append("source_lane_checker_invalid")
        forbidden = " | ".join(str(item).lower() for item in source.get("forbidden_claims") or [])
        for phrase in ["candidate pool", "scorer", "performance", "huawei"]:
            if phrase not in forbidden:
                blockers.append(f"source_lane_forbidden_claim_missing:{phrase}")
    return {
        "report_scope": "rashe_approval_packet_review_matrix_after_source_approval_check",
        "matrix_path": str(matrix_path),
        "lane_ids": lane_ids,
        "runtime_behavior_authorized": matrix.get("runtime_behavior_authorized"),
        "source_collection_authorized": matrix.get("source_collection_authorized"),
        "provider_calls_authorized": matrix.get("provider_calls_authorized"),
        "candidate_generation_authorized": matrix.get("candidate_generation_authorized"),
        "candidate_pool_ready": matrix.get("candidate_pool_ready"),
        "scorer_authorized": matrix.get("scorer_authorized"),
        "performance_evidence": matrix.get("performance_evidence"),
        "huawei_acceptance_ready": matrix.get("huawei_acceptance_ready"),
        "rashe_approval_packet_review_matrix_after_source_approval_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check(args.matrix)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_approval_packet_review_matrix_after_source_approval_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
