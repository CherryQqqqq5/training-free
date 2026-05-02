#!/usr/bin/env python3
"""Validate the RASHE provider route update approval packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_route_update_approval_packet.json")
SIGNED_ENDPOINT_ENVS = ["CHUANGZHI_NOVACODE_ENDPOINT", "NOVACODE_ENDPOINT"]
SIGNED_KEY_ENVS = ["CHUANGZHI_API_KEY", "NOVACODE_API_KEY"]
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
        "approval_packet_kind": "provider_route_update",
        "approval_status": "approved",
        "authorized": True,
        "route_update_required": True,
        "old_signed_model": "gpt-5.2",
        "old_signed_model_active": False,
        "old_signed_model_status": "unavailable_provider_auth_failed",
        "new_signed_model": "gpt-4.1",
        "provider_profile": "Chuangzhi/Novacode",
        "gpt_4_1_fc_preflight_passed": True,
        "gpt_4_1_auth_ok": True,
        "gpt_4_1_model_available": True,
        "gpt_4_1_tool_calling_supported": True,
        "gpt_4_1_tool_choice_supported": True,
        "gpt_4_1_tool_calls_returned": True,
        "gpt_4o_observed_supported": True,
        "gpt_4o_fallback_allowed": False,
        "fallback_allowed": False,
        "phase_b_auto_authorized": False,
        "phase_b_execution_authorized_by_this_packet": False,
        "source_diagnostic_execution_authorized_by_this_packet": False,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "raw_payload_persisted": False,
        "raw_prompt_persisted": False,
        "raw_provider_response_persisted": False,
    }
    for key, value in expected.items():
        if packet.get(key) != value:
            blockers.append(f"packet_{key}_invalid:{packet.get(key)!r}")
    endpoint_policy = packet.get("endpoint_policy") if isinstance(packet.get("endpoint_policy"), dict) else {}
    key_policy = packet.get("api_key_policy") if isinstance(packet.get("api_key_policy"), dict) else {}
    if endpoint_policy.get("allowed_env_vars") != SIGNED_ENDPOINT_ENVS:
        blockers.append("packet_endpoint_allowed_env_vars_invalid")
    if key_policy.get("allowed_env_vars") != SIGNED_KEY_ENVS:
        blockers.append("packet_api_key_allowed_env_vars_invalid")
    for policy_name, policy in [("endpoint", endpoint_policy), ("api_key", key_policy)]:
        if policy.get("env_only") is not True:
            blockers.append(f"packet_{policy_name}_env_only_not_true")
        for field in ["value_committed", "value_logged", "value_artifact_written"]:
            if policy.get(field) is not False:
                blockers.append(f"packet_{policy_name}_{field}_not_false:{policy.get(field)!r}")
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
        "report_scope": "rashe_provider_route_update_approved_check",
        "packet_path": str(packet_path),
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "route_update_required": packet.get("route_update_required"),
        "old_signed_model": packet.get("old_signed_model"),
        "old_signed_model_active": packet.get("old_signed_model_active"),
        "new_signed_model": packet.get("new_signed_model"),
        "gpt_4_1_fc_preflight_passed": packet.get("gpt_4_1_fc_preflight_passed"),
        "gpt_4o_observed_supported": packet.get("gpt_4o_observed_supported"),
        "gpt_4o_fallback_allowed": packet.get("gpt_4o_fallback_allowed"),
        "phase_b_auto_authorized": packet.get("phase_b_auto_authorized"),
        "candidate_generation_authorized": packet.get("candidate_generation_authorized"),
        "scorer_authorized": packet.get("scorer_authorized"),
        "performance_evidence": packet.get("performance_evidence"),
        "huawei_acceptance_ready": packet.get("huawei_acceptance_ready"),
        "rashe_provider_route_update_approved_passed": not blockers,
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
            "report_scope": "rashe_provider_route_update_approved_check",
            "packet_path": str(args.packet),
            "rashe_provider_route_update_approved_passed": False,
            "blockers": [f"provider_route_update_packet_load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_provider_route_update_approved_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
