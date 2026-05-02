#!/usr/bin/env python3
"""Check compact BFCL measurement provider protocol debug artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

KEY_LITERAL_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{16,}")
ENDPOINT_LITERAL_FRAGMENTS = ("apicz", "boyuerichdata", "http://", "https://")
REQUIRED_RECORD_FALSE = (
    "raw_provider_payload_persisted",
    "raw_log_persisted",
    "raw_trace_persisted",
    "raw_prompt_persisted",
    "source_input_read",
    "diagnostic_written",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "scorer_feedback_tuning_enabled",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
)
REQUIRED_TOP_FALSE = (
    "raw_request_persisted",
    "raw_response_persisted",
    "raw_header_persisted",
    "raw_body_persisted",
)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _walk(value: Any) -> list[Any]:
    values = [value]
    if isinstance(value, dict):
        for key, child in value.items():
            values.append(str(key))
            values.extend(_walk(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_walk(child))
    return values


def _secret_or_endpoint_blockers(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for value in _walk(data):
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        if any(fragment in lowered for fragment in ENDPOINT_LITERAL_FRAGMENTS):
            blockers.append("protocol_debug_artifact_endpoint_literal_forbidden")
        if KEY_LITERAL_PATTERN.search(value):
            blockers.append("protocol_debug_artifact_key_literal_forbidden")
    return sorted(set(blockers))


def validate_record(record: dict[str, Any], index: int = 0) -> list[str]:
    blockers: list[str] = []
    prefix = f"record_{index}"
    if record.get("route_profile") != "novacode":
        blockers.append(f"{prefix}_route_profile_invalid:{record.get('route_profile')!r}")
    if record.get("route_model") != "gpt-4.1":
        blockers.append(f"{prefix}_route_model_invalid:{record.get('route_model')!r}")
    if record.get("fallback_allowed") is not False or record.get("gpt_4o_fallback_allowed") is not False:
        blockers.append(f"{prefix}_fallback_not_false")
    for key in REQUIRED_RECORD_FALSE:
        if record.get(key) is not False:
            blockers.append(f"{prefix}_{key}_not_false:{record.get(key)!r}")
    contract = record.get("response_contract") if isinstance(record.get("response_contract"), dict) else {}
    if contract.get("empty_model_response") is True:
        blockers.append(f"{prefix}_empty_model_response")
    if contract.get("tool_call_required") is True and contract.get("tool_call_present") is not True:
        blockers.append(f"{prefix}_missing_required_tool_call")
    if contract.get("openai_compatible_response_shape") is not True:
        blockers.append(f"{prefix}_non_openai_compatible_response_shape")
    return blockers


def validate_artifact(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_measurement_provider_protocol_debug_compact":
        blockers.append(f"protocol_debug_artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("provider_request_executed") not in (False, True):
        blockers.append(f"protocol_debug_artifact_provider_request_executed_invalid:{data.get('provider_request_executed')!r}")
    if data.get("provider_request_executed") is True and data.get("provider_request_count") != 1:
        blockers.append(f"protocol_debug_artifact_provider_request_count_invalid:{data.get('provider_request_count')!r}")
    for key in REQUIRED_TOP_FALSE:
        if data.get(key) is not False:
            blockers.append(f"protocol_debug_artifact_{key}_not_false:{data.get(key)!r}")
    records = data.get("records")
    if not isinstance(records, list) or not records:
        blockers.append("protocol_debug_artifact_records_missing")
    else:
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                blockers.append(f"record_{index}_not_object")
                continue
            blockers.extend(validate_record(record, index))
    blockers.extend(_secret_or_endpoint_blockers(data))
    return blockers


def check(path: Path) -> dict[str, Any]:
    data = load_json(path)
    blockers = validate_artifact(data)
    return {
        "report_scope": "bfcl_measurement_provider_protocol_debug_artifact_check",
        "artifact_path": str(path),
        "bfcl_measurement_provider_protocol_debug_artifact_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "bfcl_measurement_provider_protocol_debug_artifact_check",
            "artifact_path": str(args.artifact),
            "bfcl_measurement_provider_protocol_debug_artifact_passed": False,
            "blockers": [f"protocol_debug_artifact_load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_measurement_provider_protocol_debug_artifact_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
