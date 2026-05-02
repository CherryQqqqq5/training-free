#!/usr/bin/env python3
"""Validate the RASHE provider endpoint/model/tool-calling preflight packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_endpoint_preflight_packet.json")
SIGNED_ENDPOINT_ENVS = ["CHUANGZHI_NOVACODE_ENDPOINT", "NOVACODE_ENDPOINT"]
SIGNED_KEY_ENVS = ["CHUANGZHI_API_KEY", "NOVACODE_API_KEY"]
PRIMARY_MODEL = "gpt-4.1"
OPTIONAL_MODEL = "gpt-4o"
TOY_TOOL_NAME = "synthetic_preflight_ping"
PLANNED_FIELDS = [
    "endpoint_present",
    "key_present",
    "https_valid",
    "auth_ok",
    "model_gpt_4_1_available",
    "optional_model_gpt_4o_observed",
    "tool_calling_supported",
    "tool_choice_supported",
    "tool_calls_returned",
    "raw_payload_persisted",
    "raw_prompt_persisted",
    "candidate_generation_authorized",
    "scorer_authorized",
    "performance_evidence",
    "blocker",
]
REQUIRED_TRUE = (
    "authorized",
    "preflight_only",
    "provider_preflight_requires_second_review",
    "endpoint_env_presence_check_authorized",
    "key_env_presence_check_authorized",
    "endpoint_value_read_authorized",
    "key_value_read_authorized",
    "provider_request_authorized",
    "provider_request_authorized_in_this_commit",
    "actual_preflight_request_path_implemented",
    "https_endpoint_required_for_future_preflight",
    "route_update_required_if_only_optional_model_supported",
    "synthetic_toy_probe_only",
    "standard_chat_adapter_review_required_if_only_chat_completions",
)
REQUIRED_FALSE = (
    "phase_b_execution_authorized",
    "bfcl_source_diagnostic_authorized",
    "source_diagnostic_execution_authorized",
    "actual_preflight_executed_in_this_commit",
    "endpoint_value_logging_authorized",
    "key_logging_authorized",
    "endpoint_artifact_write_authorized",
    "key_artifact_write_authorized",
    "bfcl_case_or_source_prompt_allowed",
    "raw_tool_data_allowed",
    "raw_prompt_persisted",
    "raw_payload_persisted",
    "raw_provider_response_persisted",
    "raw_payload_capture_authorized",
    "raw_trace_capture_authorized",
    "compact_diagnostic_payload_allowed_for_preflight",
    "candidate_generation_authorized",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "diagnostics_generated",
)
FORBIDDEN_PROBE_CONTENT = {
    "bfcl_case",
    "source_case",
    "case_id",
    "raw_prompt",
    "prompt_text",
    "raw_tool_data",
    "raw_trace",
    "raw_payload",
    "provider_payload",
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
    "performance_claim",
    "huawei_acceptance_claim",
}
FORBIDDEN_PACKET_VALUE_FRAGMENTS = (
    "https://",
    "api_key=",
    "endpoint=",
    "bearer ",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        strings: list[str] = []
        for key, child in value.items():
            strings.append(str(key))
            strings.extend(_walk_strings(child))
        return strings
    if isinstance(value, list):
        strings = []
        for child in value:
            strings.extend(_walk_strings(child))
        return strings
    if isinstance(value, str):
        return [value]
    return []


def validate_packet(packet: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected_values = {
        "approval_packet_kind": "provider_endpoint_model_tool_calling_preflight",
        "approval_status": "approved",
        "signed_endpoint_env_vars": SIGNED_ENDPOINT_ENVS,
        "signed_key_env_vars": SIGNED_KEY_ENVS,
        "signed_primary_model": PRIMARY_MODEL,
        "optional_capability_observation_model": OPTIONAL_MODEL,
        "provider_request_scope": "synthetic_toy_endpoint_model_tool_calling_preflight_only",
        "toy_probe_tool_name": TOY_TOOL_NAME,
        "planned_compact_result_fields": PLANNED_FIELDS,
    }
    for key, expected in expected_values.items():
        if packet.get(key) != expected:
            blockers.append(f"packet_{key}_invalid:{packet.get(key)!r}")
    for key in REQUIRED_TRUE:
        if packet.get(key) is not True:
            blockers.append(f"packet_{key}_not_true:{packet.get(key)!r}")
    for key in REQUIRED_FALSE:
        if packet.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{packet.get(key)!r}")
    forbidden = set(packet.get("forbidden_probe_content") or [])
    for field in sorted(FORBIDDEN_PROBE_CONTENT - forbidden):
        blockers.append(f"packet_forbidden_probe_content_missing:{field}")
    for value in _walk_strings(packet):
        lowered = value.lower()
        for fragment in FORBIDDEN_PACKET_VALUE_FRAGMENTS:
            if fragment in lowered:
                blockers.append(f"packet_contains_forbidden_secret_or_endpoint_fragment:{fragment}")
    return blockers


def check(packet_path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet = load_json(packet_path)
    blockers = validate_packet(packet)
    return {
        "report_scope": "rashe_provider_endpoint_preflight_packet_check",
        "packet_path": str(packet_path),
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "preflight_only": packet.get("preflight_only"),
        "provider_request_authorized": packet.get("provider_request_authorized"),
        "provider_request_authorized_in_this_commit": packet.get("provider_request_authorized_in_this_commit"),
        "provider_preflight_requires_second_review": packet.get("provider_preflight_requires_second_review"),
        "actual_preflight_request_path_implemented": packet.get("actual_preflight_request_path_implemented"),
        "actual_preflight_executed_in_this_commit": packet.get("actual_preflight_executed_in_this_commit"),
        "endpoint_value_read_authorized": packet.get("endpoint_value_read_authorized"),
        "key_value_read_authorized": packet.get("key_value_read_authorized"),
        "signed_endpoint_env_vars": packet.get("signed_endpoint_env_vars"),
        "signed_key_env_vars": packet.get("signed_key_env_vars"),
        "signed_primary_model": packet.get("signed_primary_model"),
        "optional_capability_observation_model": packet.get("optional_capability_observation_model"),
        "phase_b_execution_authorized": packet.get("phase_b_execution_authorized"),
        "bfcl_source_diagnostic_authorized": packet.get("bfcl_source_diagnostic_authorized"),
        "candidate_generation_authorized": packet.get("candidate_generation_authorized"),
        "scorer_authorized": packet.get("scorer_authorized"),
        "performance_evidence": packet.get("performance_evidence"),
        "diagnostics_generated": packet.get("diagnostics_generated"),
        "rashe_provider_endpoint_preflight_packet_passed": not blockers,
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
            "report_scope": "rashe_provider_endpoint_preflight_packet_check",
            "packet_path": str(args.packet),
            "rashe_provider_endpoint_preflight_packet_passed": False,
            "blockers": [f"provider_endpoint_preflight_packet_load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_provider_endpoint_preflight_packet_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
