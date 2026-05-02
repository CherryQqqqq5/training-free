#!/usr/bin/env python3
"""Check prepared BFCL live-shape telemetry packet."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_live_shape_telemetry_packet.json")
SIGNED_IDS = ["web_search_base_0", "multi_turn_base_0"]
REQUIRED_FALSE = (
    "bfcl_smoke_authorized",
    "bfcl_full_eval_authorized",
    "bfcl_scorer_authorized",
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
)
REQUIRED_TRUE = (
    "authorized",
    "live_shape_telemetry_preparation_authorized",
    "live_shape_telemetry_execution_authorized",
    "provider_request_authorized",
    "endpoint_env_only",
    "api_key_env_only",
    "candidate_specs_inert",
)
ALLOWED_FIELDS = [
    "endpoint_path_label",
    "request_shape_label",
    "response_shape_label",
    "status_code_class",
    "output_empty",
    "tool_call_present",
    "parser_decode_path_label",
    "token_forwarding_label",
    "tool_choice_forwarding_label",
    "instructions_forwarding_label",
    "engine_content_empty_label",
    "engine_coercion_label",
    "raw_text_persisted",
    "raw_body_persisted",
    "raw_payload_persisted",
    "raw_header_persisted",
    "raw_log_persisted",
    "raw_trace_persisted",
]
SIGNED_TELEMETRY_CLIENT_FACTORY = "scripts.bfcl_live_shape_telemetry_client:build_signed_live_shape_telemetry_client"
SECRET_OR_ENDPOINT_RE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|https?://)", re.IGNORECASE)
RAW_MARKERS = ("raw prompt", "BFCL case content", "provider payload", "response body", "scorer diff", "gold/reference/expected", "candidate output")


def _load(path: Path) -> dict[str, Any]:
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


def _scan_literals(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(data):
        if not isinstance(value, str):
            continue
        if SECRET_OR_ENDPOINT_RE.search(value):
            blockers.append(f"telemetry_packet_secret_or_endpoint_literal:{'.'.join(path)}")
        if path and path[0] in {"allowed_artifact_fields"}:
            continue
        if any(marker.lower() in value.lower() for marker in RAW_MARKERS):
            blockers.append(f"telemetry_packet_raw_marker_literal:{'.'.join(path)}")
    return sorted(set(blockers))


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected = {
        "artifact_kind": "bfcl_live_shape_telemetry_packet",
        "approval_status": "approved",
        "provider_profile": "Chuangzhi/Novacode",
        "active_profile": "novacode",
        "route_model": "gpt-4.1",
        "conformance_commit": "3650bf385204745197d18038d6f0fe8ba45297dd",
    }
    for key, value in expected.items():
        if data.get(key) != value:
            blockers.append(f"telemetry_packet_{key}_invalid:{data.get(key)!r}")
    for key in REQUIRED_FALSE:
        if data.get(key) is not False:
            blockers.append(f"telemetry_packet_{key}_not_false:{data.get(key)!r}")
    for key in REQUIRED_TRUE:
        if data.get(key) is not True:
            blockers.append(f"telemetry_packet_{key}_not_true:{data.get(key)!r}")
    ids = data.get("planned_run_ids") if isinstance(data.get("planned_run_ids"), list) else []
    if ids != SIGNED_IDS:
        blockers.append(f"telemetry_packet_run_ids_drift:{ids!r}")
    if len(ids) > 2:
        blockers.append(f"telemetry_packet_too_many_run_ids:{len(ids)}")
    if len(set(ids)) != len(ids):
        blockers.append("telemetry_packet_duplicate_run_ids")
    if data.get("allowed_artifact_fields") != ALLOWED_FIELDS:
        blockers.append("telemetry_packet_allowed_artifact_fields_drift")
    if data.get("provider_request_authorized_scope") != "single_live_shape_telemetry_gate_only":
        blockers.append(f"telemetry_packet_provider_scope_invalid:{data.get('provider_request_authorized_scope')!r}")
    if data.get("max_execution_count") != 1:
        blockers.append(f"telemetry_packet_max_execution_count_invalid:{data.get('max_execution_count')!r}")
    if data.get("telemetry_client_factory_required") is not True:
        blockers.append(f"telemetry_packet_client_factory_required_not_true:{data.get('telemetry_client_factory_required')!r}")
    if data.get("telemetry_client_factory_scope") != "single_live_shape_telemetry_gate_only":
        blockers.append(f"telemetry_packet_client_factory_scope_invalid:{data.get('telemetry_client_factory_scope')!r}")
    if data.get("signed_telemetry_client_factory") != SIGNED_TELEMETRY_CLIENT_FACTORY:
        blockers.append(f"telemetry_packet_signed_client_factory_invalid:{data.get('signed_telemetry_client_factory')!r}")
    blockers.extend(_scan_literals(data))
    return blockers


def check(path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    return {
        "report_scope": "bfcl_live_shape_telemetry_packet_check",
        "packet_path": str(path),
        "approval_status": data.get("approval_status"),
        "planned_run_ids": data.get("planned_run_ids"),
        "live_shape_telemetry_execution_authorized": data.get("live_shape_telemetry_execution_authorized"),
        "bfcl_live_shape_telemetry_packet_passed": not blockers,
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
        summary = {"report_scope": "bfcl_live_shape_telemetry_packet_check", "bfcl_live_shape_telemetry_packet_passed": False, "blockers": [f"telemetry_packet_load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_live_shape_telemetry_packet_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
