#!/usr/bin/env python3
"""Validate the RASHE provider transport approval packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_transport_approval_packet.json")
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
SIGNED_SOURCE_INPUT_ROOT = "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact/"
SIGNED_OUTPUT_ROOT = "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/"
SIGNED_SCHEMA_PATH = "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json"
SIGNED_ADAPTER = "scripts.rashe_source_diagnostic_compact_adapter:run_compact_source_diagnostic"
SIGNED_FACTORY = "scripts.rashe_source_provider_client:build_chuangzhi_novacode_source_provider_client"
SIGNED_CASE_PROVIDER = "scripts.rashe_source_case_provider:build_signed_source_case_provider"
REQUIRED_TRUE = ("authorized", "provider_transport_authorized", "source_diagnostic_execution_authorized", "provider_calls_authorized")
REQUIRED_FALSE = (
    "raw_trace_capture_authorized",
    "raw_payload_capture_authorized",
    "candidate_generation_authorized",
    "candidate_pool_ready",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "diagnostics_generated",
    "execution_performed_in_this_commit",
)
ZERO_FIELDS = (
    "candidate_call_count",
    "scorer_call_count",
    "raw_payload_tracked_count",
    "forbidden_field_violation_count",
    "source_diagnostic_run_count",
    "provider_transport_run_count",
)
NO_LEAKAGE_FALSE = (
    "raw_case_id_used",
    "raw_prompt_used",
    "gold_used",
    "expected_used",
    "reference_used",
    "scorer_diff_used",
    "candidate_output_used",
    "repair_output_used",
    "feedback_used",
    "holdout_feedback_used",
    "full_suite_feedback_used",
    "raw_trace_committed",
    "provider_payload_committed",
    "api_key_logged_or_written",
)
RAW_INDICATORS = (
    "raw_trace",
    "raw-payload",
    "raw_payload",
    "case_id",
    "case-id",
    "provider_payload",
    "provider-payload",
    "gold",
    "expected",
    "reference",
    "scorer_diff",
    "candidate_output",
    "repair_output",
    "holdout_feedback",
    "full_suite_feedback",
)
FORBIDDEN_FIELDS = {
    "raw_case_id",
    "case_id",
    "raw_prompt",
    "prompt",
    "prompt_text",
    "task_text",
    "tool_trace",
    "trace_path",
    "raw_trace",
    "raw_provider_payload",
    "provider_payload",
    "provider_response",
    "raw_payload",
    "gold",
    "expected",
    "reference",
    "scorer_diff",
    "candidate_output",
    "repair_output",
    "feedback",
    "holdout_feedback",
    "full_suite_feedback",
    "candidate_jsonl",
    "dev_manifest",
    "holdout_manifest",
    "full_manifest",
    "scorer_output",
    "performance_evidence_claim",
    "huawei_acceptance_claim",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _path_raw_hits(value: str) -> list[str]:
    lowered = value.lower()
    return [indicator for indicator in RAW_INDICATORS if indicator in lowered]


def validate_packet(packet: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    required_values = {
        "approval_packet_kind": "provider_transport_execution",
        "approval_status": "approved",
        "provider_profile": "Chuangzhi/Novacode",
        "provider_model": "gpt-5.2",
        "approved_categories": list(APPROVED_CATEGORIES),
        "case_count_per_category": 20,
        "total_case_count": 160,
        "source_input_root": SIGNED_SOURCE_INPUT_ROOT,
        "output_root": SIGNED_OUTPUT_ROOT,
        "schema_path": SIGNED_SCHEMA_PATH,
        "execution_adapter": SIGNED_ADAPTER,
        "provider_client_factory": SIGNED_FACTORY,
        "source_case_provider": SIGNED_CASE_PROVIDER,
        "failure_buckets": list(FAILURE_BUCKETS),
    }
    for key, expected in required_values.items():
        if packet.get(key) != expected:
            blockers.append(f"packet_{key}_invalid:{packet.get(key)!r}")
    for key in REQUIRED_TRUE:
        if packet.get(key) is not True:
            blockers.append(f"packet_{key}_not_true:{packet.get(key)!r}")
    for key in REQUIRED_FALSE:
        if packet.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{packet.get(key)!r}")
    for key in ZERO_FIELDS:
        if int(packet.get(key, -1) or 0) != 0:
            blockers.append(f"packet_{key}_not_zero:{packet.get(key)!r}")
    for key in ["source_input_root", "output_root", "schema_path"]:
        value = str(packet.get(key) or "")
        if not value.startswith("outputs/artifacts/stage1_bfcl_acceptance/"):
            blockers.append(f"packet_{key}_outside_signed_artifact_dir:{value!r}")
        for hit in _path_raw_hits(value):
            blockers.append(f"packet_{key}_raw_indicator:{hit}")

    key_policy = packet.get("api_key_policy") if isinstance(packet.get("api_key_policy"), dict) else {}
    if key_policy.get("env_only") is not True:
        blockers.append("packet_api_key_env_only_not_true")
    if key_policy.get("execution_time_only") is not True:
        blockers.append("packet_api_key_execution_time_only_not_true")
    if key_policy.get("allowed_env_vars") != ["CHUANGZHI_API_KEY", "NOVACODE_API_KEY"]:
        blockers.append("packet_api_key_allowed_env_vars_invalid")
    for key in ["profile_file_read_authorized", "key_logging_authorized", "key_artifact_write_authorized"]:
        if key_policy.get(key) is not False:
            blockers.append(f"packet_api_key_policy_not_false:{key}")

    output_policy = packet.get("transport_output_policy") if isinstance(packet.get("transport_output_policy"), dict) else {}
    if output_policy.get("sanitized_counters_only") is not True:
        blockers.append("packet_transport_sanitized_counters_only_not_true")
    for key in ["raw_request_persisted", "raw_response_persisted"]:
        if output_policy.get(key) is not False:
            blockers.append(f"packet_transport_output_policy_not_false:{key}")
    for key in ["raw_payload_tracked_count", "forbidden_field_violation_count"]:
        if output_policy.get(key) != 0:
            blockers.append(f"packet_transport_output_policy_not_zero:{key}")
    if output_policy.get("allowed_result_fields") != ["failure_bucket", "failure_bucket_counts"]:
        blockers.append("packet_transport_allowed_result_fields_invalid")

    forbidden = set(packet.get("forbidden_fields") or [])
    for field in sorted(FORBIDDEN_FIELDS - forbidden):
        blockers.append(f"packet_forbidden_field_missing:{field}")
    no_leakage = packet.get("no_leakage_required") if isinstance(packet.get("no_leakage_required"), dict) else {}
    for key in NO_LEAKAGE_FALSE:
        if no_leakage.get(key) is not False:
            blockers.append(f"packet_no_leakage_field_not_false:{key}")
    return blockers


def check(packet_path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet = load_json(packet_path)
    blockers = validate_packet(packet)
    return {
        "report_scope": "rashe_provider_transport_approval_packet_check",
        "packet_path": str(packet_path),
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "provider_transport_authorized": packet.get("provider_transport_authorized"),
        "source_diagnostic_execution_authorized": packet.get("source_diagnostic_execution_authorized"),
        "provider_calls_authorized": packet.get("provider_calls_authorized"),
        "provider_profile": packet.get("provider_profile"),
        "provider_model": packet.get("provider_model"),
        "case_count_per_category": packet.get("case_count_per_category"),
        "total_case_count": packet.get("total_case_count"),
        "candidate_generation_authorized": packet.get("candidate_generation_authorized"),
        "scorer_authorized": packet.get("scorer_authorized"),
        "performance_evidence": packet.get("performance_evidence"),
        "huawei_acceptance_ready": packet.get("huawei_acceptance_ready"),
        "diagnostics_generated": packet.get("diagnostics_generated"),
        "rashe_provider_transport_approval_packet_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "rashe_provider_transport_approval_packet_check",
            "packet_path": str(args.packet),
            "rashe_provider_transport_approval_packet_passed": False,
            "blockers": [f"provider_transport_packet_load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_provider_transport_approval_packet_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
