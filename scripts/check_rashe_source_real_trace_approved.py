#!/usr/bin/env python3
"""Validate approved bounded RASHE source evidence collection scope.

Passing this checker authorizes only the bounded source evidence collection lane
described by the approved packet and runbook. It does not authorize raw trace
capture, raw payload tracking, candidate generation, scorer execution,
performance evidence, or Huawei acceptance readiness.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_real_trace_approval_packet.json")
DEFAULT_SCHEMA = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json")
APPROVED_CATEGORIES = (
    "agentic_web_search",
    "agentic_memory",
    "multi_turn_base",
    "multi_turn_long_context",
    "multi_turn_miss_param",
    "multi_turn_miss_func",
    "hallucination",
    "irrelevance",
)
FAILURE_BUCKETS = (
    "answered_without_tool",
    "wrong_first_tool",
    "search_query_too_broad",
    "fetch_missing_after_search",
    "memory_not_retrieved",
    "memory_update_when_should_search",
    "multi_turn_state_lost",
    "invalid_tool_call_format",
    "parser_schema_failure",
    "final_answer_before_tool",
    "irrelevant_tool_call",
    "unsupported_hallucinated_answer",
)
REQUIRED_TRUE_VALUES = {
    "approval_packet_kind": "source_real_trace",
    "approval_status": "approved",
    "authorized": True,
    "source_collection_authorized": True,
    "provider_calls_authorized": True,
    "provider_profile": "Chuangzhi/Novacode",
    "provider_model": "gpt-5.2",
}
REQUIRED_FALSE_VALUES = (
    "raw_trace_authorized",
    "raw_trace_capture_authorized",
    "raw_payload_capture_authorized",
    "candidate_generation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "proposer_execution_authorized",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "bfcl_performance_ready",
    "execution_started",
)
ZERO_FIELDS = (
    "candidate_call_count",
    "scorer_call_count",
    "raw_payload_tracked_count",
    "tracked_raw_payload_count",
    "forbidden_field_violation_count",
    "artifact_boundary_failure_count",
    "raw_trace_count",
    "raw_payload_capture_count",
    "raw_path_leak_count",
    "path_denylist_violation_count",
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
FORBIDDEN_FIELDS = (
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
FORBIDDEN_CLAIMS = (
    "candidate pool ready",
    "scorer authorized",
    "BFCL +3pp ready",
    "Huawei acceptance ready",
    "performance evidence",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


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
    for key, expected in REQUIRED_TRUE_VALUES.items():
        if packet.get(key) != expected:
            blockers.append(f"packet_{key}_invalid:{packet.get(key)!r}")
    for key in REQUIRED_FALSE_VALUES:
        if packet.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{packet.get(key)!r}")
    for key in ZERO_FIELDS:
        if int(packet.get(key, -1) or 0) != 0:
            blockers.append(f"packet_{key}_not_zero:{packet.get(key)!r}")

    categories = packet.get("approved_source_categories")
    if categories != list(APPROVED_CATEGORIES):
        blockers.append("packet_approved_source_categories_invalid")
    if int(packet.get("case_count_per_category_min") or 0) != 20:
        blockers.append("packet_case_count_per_category_min_invalid")
    if int(packet.get("case_count_per_category_max") or 0) != 50:
        blockers.append("packet_case_count_per_category_max_invalid")
    total_max = int(packet.get("total_case_count_max") or 0)
    if total_max <= 0 or total_max > 200:
        blockers.append("packet_total_case_count_max_invalid")

    no_leakage = packet.get("no_leakage_required")
    if not isinstance(no_leakage, dict):
        blockers.append("packet_no_leakage_required_missing")
    else:
        for key in NO_LEAKAGE_FALSE_FIELDS:
            if no_leakage.get(key) is not False:
                blockers.append(f"packet_no_leakage_field_not_false:{key}")
    forbidden = {str(item) for item in packet.get("forbidden_fields") or []}
    for field in FORBIDDEN_FIELDS:
        if field not in forbidden:
            blockers.append(f"packet_forbidden_field_missing:{field}")
    claims = {str(item) for item in packet.get("forbidden_claims") or []}
    for claim in FORBIDDEN_CLAIMS:
        if claim not in claims:
            blockers.append(f"packet_forbidden_claim_missing:{claim}")

    output_root = str(packet.get("output_root") or "")
    if output_root != "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/":
        blockers.append("packet_output_root_invalid")
    if packet.get("tracked_raw_payload_paths") not in ([], None):
        blockers.append("packet_tracked_raw_payload_paths_present")
    publication = " | ".join(str(item).lower() for item in packet.get("publication_rules") or [])
    for phrase in ["compact sanitized", "no tracked raw payload", "no candidate jsonl", "no scorer"]:
        if phrase not in publication:
            blockers.append(f"packet_publication_rule_missing:{phrase}")
    return blockers


def validate_schema(schema: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if schema.get("title") != "RASHE Source Diagnostic Compact Artifact":
        blockers.append("schema_title_invalid")
    required = set(schema.get("required") or [])
    for field in [
        "category",
        "case_count",
        "provider_call_count",
        "raw_payload_tracked_count",
        "forbidden_field_violation_count",
        "failure_bucket_counts",
        "candidate_generation_authorized",
        "scorer_authorized",
        "performance_evidence",
    ]:
        if field not in required:
            blockers.append(f"schema_required_field_missing:{field}")
    category_enum = schema.get("properties", {}).get("category", {}).get("enum")
    if category_enum != list(APPROVED_CATEGORIES):
        blockers.append("schema_category_enum_invalid")
    bucket_props = schema.get("properties", {}).get("failure_bucket_counts", {}).get("properties", {})
    for bucket in FAILURE_BUCKETS:
        if bucket not in bucket_props:
            blockers.append(f"schema_failure_bucket_missing:{bucket}")
    for field in ["candidate_generation_authorized", "scorer_authorized", "performance_evidence"]:
        if schema.get("properties", {}).get(field, {}).get("const") is not False:
            blockers.append(f"schema_false_const_missing:{field}")
    for field in ["raw_payload_tracked_count", "forbidden_field_violation_count"]:
        if schema.get("properties", {}).get(field, {}).get("const") != 0:
            blockers.append(f"schema_zero_const_missing:{field}")
    return blockers


def check(packet_path: Path = DEFAULT_PACKET, schema_path: Path = DEFAULT_SCHEMA, *, artifact_boundary: bool = True) -> dict[str, Any]:
    packet = load_json(packet_path)
    schema = load_json(schema_path)
    blockers = validate_packet(packet)
    blockers.extend(validate_schema(schema))
    artifact_boundary_passed = True
    if artifact_boundary:
        boundary_error = run_artifact_boundary()
        artifact_boundary_passed = boundary_error is None
        if boundary_error:
            blockers.append(f"artifact_boundary_failed:{boundary_error}")
    return {
        "report_scope": "rashe_source_real_trace_approved_check",
        "packet_path": str(packet_path),
        "schema_path": str(schema_path),
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "source_collection_authorized": packet.get("source_collection_authorized"),
        "provider_calls_authorized": packet.get("provider_calls_authorized"),
        "provider_profile": packet.get("provider_profile"),
        "provider_model": packet.get("provider_model"),
        "approved_source_categories": packet.get("approved_source_categories"),
        "case_count_per_category_min": packet.get("case_count_per_category_min"),
        "case_count_per_category_max": packet.get("case_count_per_category_max"),
        "total_case_count_max": packet.get("total_case_count_max"),
        "candidate_generation_authorized": packet.get("candidate_generation_authorized"),
        "candidate_pool_ready": packet.get("candidate_pool_ready"),
        "scorer_authorized": packet.get("scorer_authorized"),
        "performance_evidence": packet.get("performance_evidence"),
        "huawei_acceptance_ready": packet.get("huawei_acceptance_ready"),
        "candidate_call_count": packet.get("candidate_call_count"),
        "scorer_call_count": packet.get("scorer_call_count"),
        "raw_payload_tracked_count": packet.get("raw_payload_tracked_count"),
        "forbidden_field_violation_count": packet.get("forbidden_field_violation_count"),
        "artifact_boundary_passed": artifact_boundary_passed,
        "rashe_source_real_trace_approved_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--skip-artifact-boundary", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet, args.schema, artifact_boundary=not args.skip_artifact_boundary)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "rashe_source_real_trace_approved_check",
            "packet_path": str(args.packet),
            "schema_path": str(args.schema),
            "rashe_source_real_trace_approved_passed": False,
            "blockers": [f"load_error:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_source_real_trace_approved_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
