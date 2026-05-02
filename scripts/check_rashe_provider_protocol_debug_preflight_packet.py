#!/usr/bin/env python3
"""Validate the RASHE provider protocol debug preflight packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_protocol_debug_preflight_packet.json")
SIGNED_VARIANTS = [
    "baseline_chat_tools_required",
    "chat_tools_auto",
    "chat_tools_required_no_strict",
    "chat_tools_max_completion_tokens",
    "chat_tools_minimal_messages",
]
ALLOWED_RESULT_FIELDS = [
    "variant",
    "planned_only",
    "provider_request_executed",
    "raw_request_persisted",
    "raw_response_persisted",
    "raw_headers_persisted",
    "raw_body_persisted",
    "source_input_read",
    "diagnostic_written",
    "candidate_generation_authorized",
    "scorer_authorized",
    "performance_evidence",
    "blocker",
]
REQUIRED_FALSE = (
    "authorized",
    "execution_authorized",
    "provider_request_authorized",
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
    "source_diagnostic_execution_authorized",
    "bfcl_source_input_authorized",
    "source_input_root_read_authorized",
    "candidate_generation_authorized",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "diagnostics_generated",
    "raw_request_persisted",
    "raw_response_persisted",
    "raw_headers_persisted",
    "raw_body_persisted",
    "endpoint_value_logged_or_written",
    "api_key_logged_or_written",
)
FORBIDDEN_CONTENT = {
    "bfcl_case",
    "source_input_root",
    "rashe_source_inputs_compact",
    "raw_prompt",
    "case_id",
    "gold",
    "expected",
    "reference",
    "scorer_diff",
    "feedback",
    "candidate_output",
    "raw_request",
    "raw_response",
    "raw_header",
    "raw_body",
    "provider_payload",
    "rashe_source_diagnostics_compact",
}
FORBIDDEN_VALUE_FRAGMENTS = ("https://", "api_key=", "endpoint=", "bearer ", "sk-")


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
    expected = {
        "approval_packet_kind": "provider_protocol_debug_preflight",
        "approval_status": "prepared",
        "signed_model": "gpt-4.1",
        "provider_profile": "Chuangzhi/Novacode",
        "allowed_variants": SIGNED_VARIANTS,
        "allowed_result_fields": ALLOWED_RESULT_FIELDS,
    }
    for key, value in expected.items():
        if packet.get(key) != value:
            blockers.append(f"packet_{key}_invalid:{packet.get(key)!r}")
    if len(packet.get("allowed_variants") or []) != len(SIGNED_VARIANTS):
        blockers.append("packet_allowed_variants_count_invalid")
    for key in REQUIRED_FALSE:
        if packet.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{packet.get(key)!r}")
    forbidden = set(packet.get("forbidden_content") or [])
    for item in sorted(FORBIDDEN_CONTENT - forbidden):
        blockers.append(f"packet_forbidden_content_missing:{item}")
    for value in _walk_strings(packet):
        lowered = value.lower()
        for fragment in FORBIDDEN_VALUE_FRAGMENTS:
            if fragment in lowered:
                blockers.append(f"packet_contains_forbidden_secret_or_endpoint_fragment:{fragment}")
    return blockers


def check(packet_path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet = load_json(packet_path)
    blockers = validate_packet(packet)
    return {
        "report_scope": "rashe_provider_protocol_debug_preflight_packet_check",
        "packet_path": str(packet_path),
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "execution_authorized": packet.get("execution_authorized"),
        "provider_request_authorized": packet.get("provider_request_authorized"),
        "signed_model": packet.get("signed_model"),
        "fallback_allowed": packet.get("fallback_allowed"),
        "source_diagnostic_execution_authorized": packet.get("source_diagnostic_execution_authorized"),
        "candidate_generation_authorized": packet.get("candidate_generation_authorized"),
        "scorer_authorized": packet.get("scorer_authorized"),
        "performance_evidence": packet.get("performance_evidence"),
        "huawei_acceptance_ready": packet.get("huawei_acceptance_ready"),
        "variant_count": len(packet.get("allowed_variants") or []),
        "rashe_provider_protocol_debug_preflight_packet_passed": not blockers,
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
            "report_scope": "rashe_provider_protocol_debug_preflight_packet_check",
            "packet_path": str(args.packet),
            "rashe_provider_protocol_debug_preflight_packet_passed": False,
            "blockers": [f"provider_protocol_debug_preflight_packet_load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_provider_protocol_debug_preflight_packet_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
