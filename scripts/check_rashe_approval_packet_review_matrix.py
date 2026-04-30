#!/usr/bin/env python3
"""Validate the fail-closed RASHE approval packet review matrix."""

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
FORBIDDEN_READY_FIELDS = (
    "execution_authorized",
    "runtime_behavior_authorized",
    "source_collection_authorized",
    "candidate_generation_authorized",
    "candidate_pool_ready",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "bfcl_performance_ready",
)
REQUIRED_LANE_FIELDS = (
    "owner_role",
    "approval_packet_path",
    "current_status",
    "prerequisites",
    "allowed_only_after_approval",
    "forbidden_until_approved",
    "stop_gates",
    "downstream_dependencies",
    "allowed_claims",
    "forbidden_claims",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _has_phrase(values: list[Any], needle: str) -> bool:
    return any(needle in str(value) for value in values)


def check(matrix_path: Path = DEFAULT_MATRIX) -> dict[str, Any]:
    blockers: list[str] = []
    matrix = load_json(matrix_path)
    lanes = matrix.get("lanes")
    if not isinstance(lanes, list):
        lanes = []
        blockers.append("lanes_missing_or_not_list")
    lane_by_id = {lane.get("lane_id"): lane for lane in lanes if isinstance(lane, dict)}
    lane_ids = [lane.get("lane_id") for lane in lanes if isinstance(lane, dict)]

    for lane_id in EXPECTED_LANES:
        if lane_id not in lane_by_id:
            blockers.append(f"lane_missing:{lane_id}")
    if lane_ids != EXPECTED_LANES:
        blockers.append("lane_order_mismatch")
    if lane_ids and lane_ids[-1] != "performance_3pp_huawei_acceptance_approval":
        blockers.append("performance_lane_not_last")

    for field in FORBIDDEN_READY_FIELDS:
        if matrix.get(field) is True:
            blockers.append(f"matrix_forbidden_ready_field_true:{field}")

    for index, lane in enumerate(lanes, start=1):
        if not isinstance(lane, dict):
            blockers.append(f"lane_not_object:{index}")
            continue
        lane_id = lane.get("lane_id", f"index_{index}")
        if lane.get("lane_order") != index:
            blockers.append(f"lane_order_field_mismatch:{lane_id}")
        for field in REQUIRED_LANE_FIELDS:
            if field not in lane:
                blockers.append(f"lane_required_field_missing:{lane_id}:{field}")
            elif isinstance(lane[field], list) and not lane[field]:
                blockers.append(f"lane_required_list_empty:{lane_id}:{field}")
        if lane.get("current_status") in {"approved", "authorized"}:
            blockers.append(f"lane_status_not_pending:{lane_id}:{lane.get('current_status')}")
        if lane.get("authorized") is True:
            blockers.append(f"lane_authorized_true:{lane_id}")
        forbidden_claims = lane.get("forbidden_claims")
        if not isinstance(forbidden_claims, list) or not forbidden_claims:
            blockers.append(f"lane_forbidden_claims_missing:{lane_id}")
        else:
            joined = " | ".join(str(item).lower() for item in forbidden_claims)
            if lane_id == "performance_3pp_huawei_acceptance_approval":
                for phrase in ["performance", "sota", "huawei"]:
                    if phrase not in joined:
                        blockers.append(f"performance_lane_forbidden_claim_missing:{phrase}")
            elif "performance" not in joined or "huawei" not in joined:
                blockers.append(f"lane_forbidden_claim_missing_performance_or_huawei:{lane_id}")
        allowed_claims = lane.get("allowed_claims")
        if isinstance(allowed_claims, list):
            if any("ready" in str(claim).lower() and "pending" not in str(claim).lower() and "unavailable" not in str(claim).lower() for claim in allowed_claims):
                blockers.append(f"lane_allowed_claim_implies_ready:{lane_id}")

    scorer = lane_by_id.get("scorer_dev_holdout_full_approval")
    if isinstance(scorer, dict):
        prereqs = scorer.get("prerequisites", [])
        if not isinstance(prereqs, list):
            blockers.append("scorer_prerequisites_not_list")
        else:
            if not _has_phrase(prereqs, "candidate_proposer_execution_approval"):
                blockers.append("scorer_missing_candidate_prerequisite")
            if not _has_phrase(prereqs, "source_real_trace_approval"):
                blockers.append("scorer_missing_source_prerequisite")
            if not _has_phrase(prereqs, "same provider/model/protocol"):
                blockers.append("scorer_missing_same_provider_model_protocol_prerequisite")
        if lane_ids and lane_ids.index("scorer_dev_holdout_full_approval") < lane_ids.index("candidate_proposer_execution_approval"):
            blockers.append("scorer_lane_before_candidate_lane")
        if lane_ids and lane_ids.index("scorer_dev_holdout_full_approval") < lane_ids.index("source_real_trace_approval"):
            blockers.append("scorer_lane_before_source_lane")

    summary = {
        "report_scope": "rashe_approval_packet_review_matrix_check",
        "matrix_path": str(matrix_path),
        "lane_count": len(lanes),
        "expected_lane_count": len(EXPECTED_LANES),
        "lane_ids": lane_ids,
        "performance_lane_last": bool(lane_ids and lane_ids[-1] == "performance_3pp_huawei_acceptance_approval"),
        "runtime_behavior_authorized": False,
        "source_collection_authorized": False,
        "candidate_generation_authorized": False,
        "candidate_pool_ready": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "rashe_approval_packet_review_matrix_passed": not blockers,
        "blockers": blockers,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check(args.matrix)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_approval_packet_review_matrix_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
