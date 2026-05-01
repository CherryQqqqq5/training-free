#!/usr/bin/env python3
"""Validate the pending/fail-closed RASHE source real-trace approval lane.

This checker prepares the source-real-trace approval lane only. Passing this
checker does not authorize source collection, raw trace capture, provider calls,
candidate generation, scorer execution, performance evidence, or Huawei
acceptance.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_real_trace_approval_packet.json")
DEFAULT_MATRIX = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_approval_packet_review_matrix.json")

REQUIRED_PACKET_VALUES = {
    "approval_packet_kind": "source_real_trace",
    "approval_status": "pending",
    "authorized": False,
    "source_collection_authorized": False,
    "provider_calls_authorized": False,
    "raw_trace_authorized": False,
    "raw_trace_capture_authorized": False,
    "raw_payload_capture_authorized": False,
    "candidate_generation_authorized": False,
    "candidate_jsonl_authorized": False,
    "candidate_pool_ready": False,
    "proposer_execution_authorized": False,
    "scorer_authorized": False,
    "performance_evidence": False,
    "sota_3pp_claim_ready": False,
    "huawei_acceptance_ready": False,
    "bfcl_performance_ready": False,
    "execution_started": False,
}

ZERO_COUNT_FIELDS = (
    "provider_call_count",
    "source_collection_call_count",
    "scorer_call_count",
    "candidate_call_count",
    "raw_trace_count",
    "raw_payload_capture_count",
    "tracked_raw_payload_count",
    "raw_path_leak_count",
    "path_denylist_violation_count",
    "forbidden_field_violation_count",
    "artifact_boundary_failure_count",
)

NO_LEAKAGE_FALSE_FIELDS = (
    "raw_case_id_used",
    "raw_trace_committed",
    "provider_payload_used",
    "gold_used",
    "expected_used",
    "reference_used",
    "scorer_diff_used",
    "feedback_used",
    "candidate_output_used",
    "repair_output_used",
    "holdout_feedback_used",
    "full_suite_feedback_used",
    "case_id_specific_rules_allowed",
    "raw_payload_tracked",
)

REQUIRED_FORBIDDEN_FIELDS = (
    "raw_case_id",
    "raw_trace",
    "raw_provider_payload",
    "gold",
    "expected",
    "reference",
    "scorer_diff",
    "candidate_output",
    "repair_output",
    "feedback",
    "holdout_feedback",
    "full_suite_feedback",
)

REQUIRED_PATH_DENYLIST = (
    "provider://",
    "scorer://",
    "source_collection://",
    "/provider/",
    "/scorer/",
    "/source_collection/",
    "outputs/bfcl_runs",
    "raw_trace",
    "raw_response_capture",
)

REQUIRED_LIST_FIELDS = (
    "prerequisites",
    "allowed_if_approved",
    "forbidden_until_approved",
    "rollback_stop_gates",
    "raw_payload_handling_rules",
    "sanitization_rules",
    "artifact_boundary_rules",
    "publication_rules",
    "future_approval_conditions",
)

PATH_VALUE_KEYS = ("path", "paths", "root", "uri", "url")
PATH_DENY_INDICATORS = REQUIRED_PATH_DENYLIST


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _contains_path_indicator(value: str) -> str | None:
    value_l = value.lower()
    for indicator in PATH_DENY_INDICATORS:
        if indicator in value_l:
            return indicator
    return None


def _iter_path_values(obj: Any, path: str = ""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_s = str(key)
            next_path = f"{path}.{key_s}" if path else key_s
            if isinstance(value, str) and any(token in key_s.lower() for token in PATH_VALUE_KEYS):
                yield next_path, value
            elif isinstance(value, list) and any(token in key_s.lower() for token in PATH_VALUE_KEYS):
                for index, item in enumerate(value):
                    if isinstance(item, str):
                        yield f"{next_path}[{index}]", item
            yield from _iter_path_values(value, next_path)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from _iter_path_values(value, f"{path}[{index}]")


def run_artifact_boundary() -> str | None:
    result = subprocess.run(
        [sys.executable, "scripts/check_artifact_boundary.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return result.stdout.strip() or result.stderr.strip() or "artifact_boundary_failed"
    return None


def validate_packet(packet: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for key, expected in REQUIRED_PACKET_VALUES.items():
        if packet.get(key) != expected:
            blockers.append(f"packet_{key}_invalid:{packet.get(key)!r}")

    for key in ZERO_COUNT_FIELDS:
        if int(packet.get(key, -1) or 0) != 0:
            blockers.append(f"packet_count_not_zero:{key}:{packet.get(key)!r}")

    no_leakage = packet.get("no_leakage_required")
    if not isinstance(no_leakage, dict):
        blockers.append("packet_no_leakage_required_missing")
    else:
        for key in NO_LEAKAGE_FALSE_FIELDS:
            if no_leakage.get(key) is not False:
                blockers.append(f"packet_no_leakage_field_not_false:{key}")
        for key, value in no_leakage.items():
            if value is not False:
                blockers.append(f"packet_no_leakage_extra_field_not_false:{key}")

    forbidden = packet.get("forbidden_fields")
    if not isinstance(forbidden, list):
        blockers.append("packet_forbidden_fields_missing")
    else:
        missing = sorted(set(REQUIRED_FORBIDDEN_FIELDS) - {str(item) for item in forbidden})
        for field in missing:
            blockers.append(f"packet_forbidden_field_missing:{field}")

    denylist = packet.get("path_denylist")
    if not isinstance(denylist, list):
        blockers.append("packet_path_denylist_missing")
    else:
        missing = sorted(set(REQUIRED_PATH_DENYLIST) - {str(item) for item in denylist})
        for item in missing:
            blockers.append(f"packet_path_denylist_missing:{item}")

    for key in REQUIRED_LIST_FIELDS:
        value = packet.get(key)
        if not isinstance(value, list) or not value:
            blockers.append(f"packet_required_list_missing:{key}")

    if packet.get("signed_raw_root") not in (None, ""):
        blockers.append("packet_signed_raw_root_present_while_pending")
    if packet.get("tracked_raw_payload_paths") not in ([], None):
        blockers.append("packet_tracked_raw_payload_paths_present")
    for path, value in _iter_path_values(packet):
        if path == "path_denylist" or path.startswith("path_denylist[") or ".path_denylist[" in path:
            continue
        indicator = _contains_path_indicator(value)
        if indicator:
            blockers.append(f"packet_raw_path_indicator:{path}:{indicator}")

    joined_publication = " | ".join(str(item).lower() for item in packet.get("publication_rules", []))
    if "hash" not in joined_publication or "counter" not in joined_publication:
        blockers.append("packet_publication_rules_missing_hash_counter_only")
    if "sanitized compact" not in joined_publication:
        blockers.append("packet_publication_rules_missing_sanitized_compact")
    return blockers


def validate_matrix(matrix: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if matrix.get("source_real_trace_approval_status") != "pending":
        blockers.append("matrix_source_real_trace_approval_status_not_pending")
    if matrix.get("source_real_trace_authorized") is not False:
        blockers.append("matrix_source_real_trace_authorized_not_false")
    for key in [
        "source_collection_authorized",
        "candidate_generation_authorized",
        "candidate_pool_ready",
        "scorer_authorized",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
        "bfcl_performance_ready",
    ]:
        if matrix.get(key) is True:
            blockers.append(f"matrix_downstream_field_true:{key}")
    source_lane = None
    for lane in matrix.get("lanes", []):
        if isinstance(lane, dict) and lane.get("lane_id") == "source_real_trace_approval":
            source_lane = lane
            break
    if not isinstance(source_lane, dict):
        blockers.append("matrix_source_lane_missing")
        return blockers
    if source_lane.get("current_status") != "pending":
        blockers.append("matrix_source_lane_status_not_pending")
    if source_lane.get("authorized") is not False:
        blockers.append("matrix_source_lane_authorized_not_false")
    if source_lane.get("approval_checker_path") != "scripts/check_rashe_source_real_trace_approval_packet.py":
        blockers.append("matrix_source_lane_checker_missing")
    for key in ["prerequisites", "allowed_only_after_approval", "forbidden_until_approved", "stop_gates"]:
        if not isinstance(source_lane.get(key), list) or not source_lane.get(key):
            blockers.append(f"matrix_source_lane_required_list_missing:{key}")
    return blockers


def check(packet_path: Path = DEFAULT_PACKET, matrix_path: Path = DEFAULT_MATRIX, *, artifact_boundary: bool = True) -> dict[str, Any]:
    packet = load_json(packet_path)
    matrix = load_json(matrix_path)
    blockers = validate_packet(packet)
    blockers.extend(validate_matrix(matrix))
    artifact_boundary_passed = True
    if artifact_boundary:
        boundary_error = run_artifact_boundary()
        artifact_boundary_passed = boundary_error is None
        if boundary_error:
            blockers.append(f"artifact_boundary_failed:{boundary_error}")
    return {
        "report_scope": "rashe_source_real_trace_approval_check",
        "packet_path": str(packet_path),
        "matrix_path": str(matrix_path),
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "source_collection_authorized": packet.get("source_collection_authorized"),
        "provider_calls_authorized": packet.get("provider_calls_authorized"),
        "raw_trace_capture_authorized": packet.get("raw_trace_capture_authorized"),
        "raw_payload_capture_authorized": packet.get("raw_payload_capture_authorized"),
        "candidate_generation_authorized": packet.get("candidate_generation_authorized"),
        "candidate_pool_ready": packet.get("candidate_pool_ready"),
        "scorer_authorized": packet.get("scorer_authorized"),
        "performance_evidence": packet.get("performance_evidence"),
        "sota_3pp_claim_ready": packet.get("sota_3pp_claim_ready"),
        "huawei_acceptance_ready": packet.get("huawei_acceptance_ready"),
        "artifact_boundary_passed": artifact_boundary_passed,
        "source_real_trace_approval_pending_fail_closed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--skip-artifact-boundary", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet, args.matrix, artifact_boundary=not args.skip_artifact_boundary)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "rashe_source_real_trace_approval_check",
            "packet_path": str(args.packet),
            "matrix_path": str(args.matrix),
            "source_real_trace_approval_pending_fail_closed": False,
            "blockers": [f"load_error:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["source_real_trace_approval_pending_fail_closed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
