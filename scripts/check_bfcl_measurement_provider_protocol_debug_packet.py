#!/usr/bin/env python3
"""Check the BFCL measurement provider protocol debug packet."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_measurement_provider_protocol_debug_packet.json")
SIGNED_ENDPOINT_ENVS = ["CHUANGZHI_NOVACODE_ENDPOINT", "NOVACODE_ENDPOINT"]
SIGNED_KEY_ENVS = ["CHUANGZHI_API_KEY", "NOVACODE_API_KEY"]
ENDPOINT_LITERAL_FRAGMENTS = ("apicz", "boyuerichdata", "http://", "https://")
KEY_LITERAL_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{16,}")
REQUIRED_FALSE = (
    "authorized",
    "protocol_debug_execution_authorized",
    "provider_request_authorized",
    "bfcl_smoke_authorized",
    "bfcl_full_eval_authorized",
    "scorer_authorized",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
    "openrouter_allowed",
    "endpoint_value_committed",
    "api_key_value_committed",
    "raw_provider_payload_persistence_authorized",
    "raw_log_persistence_authorized",
    "raw_trace_persistence_authorized",
    "raw_prompt_persistence_authorized",
    "scorer_feedback_tuning_enabled",
    "metrics_produced",
    "manifest_produced",
    "performance_claim_from_failed_attempt",
)
REQUIRED_TRUE = (
    "protocol_debug_preparation_authorized",
    "candidate_specs_inert",
    "endpoint_env_only",
    "api_key_env_only",
)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _walk(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(_walk(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_walk(child, path + (str(index),)))
    return items


def _literal_blockers(packet: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(packet):
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        if any(fragment in lowered for fragment in ENDPOINT_LITERAL_FRAGMENTS):
            blockers.append(f"protocol_debug_packet_endpoint_literal_forbidden:{'.'.join(path)}")
        if KEY_LITERAL_PATTERN.search(value):
            blockers.append(f"protocol_debug_packet_key_literal_forbidden:{'.'.join(path)}")
    return blockers


def validate(packet: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected = {
        "approval_packet_kind": "bfcl_measurement_provider_protocol_debug",
        "approval_status": "pending",
        "provider_profile": "Chuangzhi/Novacode",
        "active_profile": "novacode",
        "route_model": "gpt-4.1",
        "signed_endpoint_env_vars": SIGNED_ENDPOINT_ENVS,
        "signed_api_key_env_vars": SIGNED_KEY_ENVS,
        "failure_class": "empty_model_response_before_measurement_completion",
        "completed_cases_before_stop": 4,
        "observed_progress": "4/5217",
        "planned_debug_scope": "synthetic_pre_bfcl_protocol_contract_only",
        "planned_debug_checks": [
            "empty_model_response_guard",
            "tool_call_required_guard",
            "openai_compatible_response_shape_guard",
        ],
    }
    for key, value in expected.items():
        if packet.get(key) != value:
            blockers.append(f"protocol_debug_packet_{key}_invalid:{packet.get(key)!r}")
    for key in REQUIRED_TRUE:
        if packet.get(key) is not True:
            blockers.append(f"protocol_debug_packet_{key}_not_true:{packet.get(key)!r}")
    for key in REQUIRED_FALSE:
        if packet.get(key) is not False:
            blockers.append(f"protocol_debug_packet_{key}_not_false:{packet.get(key)!r}")
    forbidden = packet.get("forbidden_material") if isinstance(packet.get("forbidden_material"), list) else []
    for required in [
        "raw logs",
        "raw traces",
        "provider payloads",
        "prompts",
        "gold/reference",
        "scorer diffs",
        "candidate output",
        "endpoint/key values",
    ]:
        if required not in forbidden:
            blockers.append(f"protocol_debug_packet_forbidden_material_missing:{required}")
    blockers.extend(_literal_blockers(packet))
    return blockers


def check(packet_path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet = load_json(packet_path)
    blockers = validate(packet)
    return {
        "report_scope": "bfcl_measurement_provider_protocol_debug_packet_check",
        "packet_path": str(packet_path),
        "approval_status": packet.get("approval_status"),
        "route_model": packet.get("route_model"),
        "active_profile": packet.get("active_profile"),
        "protocol_debug_execution_authorized": packet.get("protocol_debug_execution_authorized"),
        "provider_request_authorized": packet.get("provider_request_authorized"),
        "bfcl_smoke_authorized": packet.get("bfcl_smoke_authorized"),
        "bfcl_full_eval_authorized": packet.get("bfcl_full_eval_authorized"),
        "scorer_authorized": packet.get("scorer_authorized"),
        "candidate_specs_inert": packet.get("candidate_specs_inert"),
        "bfcl_measurement_provider_protocol_debug_packet_passed": not blockers,
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
            "report_scope": "bfcl_measurement_provider_protocol_debug_packet_check",
            "packet_path": str(args.packet),
            "bfcl_measurement_provider_protocol_debug_packet_passed": False,
            "blockers": [f"protocol_debug_packet_load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_measurement_provider_protocol_debug_packet_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
