#!/usr/bin/env python3
"""Check the Stage 1F one-ID live decode exception shape capture gate packet."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_live_decode_exception_shape_capture_gate_packet.json")
SIGNED_ID = "web_search_base_0"
REQUIRED_COMPACT_FIELDS = [
    "run_id",
    "route_profile",
    "route_model",
    "bfcl_handler_class_label",
    "bfcl_api_path_label",
    "provider_status_class",
    "provider_response_has_tool_calls",
    "provider_response_has_nonempty_text",
    "proxy_responses_output_has_function_call",
    "proxy_function_call_item_count",
    "proxy_function_call_has_call_id",
    "proxy_function_call_has_name",
    "proxy_function_call_has_arguments",
    "proxy_function_call_has_status",
    "proxy_function_call_has_id",
    "proxy_name_field_placement_label",
    "proxy_arguments_shape_label",
    "proxy_arguments_json_parseable_bool",
    "proxy_status_shape_label",
    "proxy_call_id_source_label",
    "bfcl_parse_called",
    "bfcl_parse_exception_class",
    "bfcl_parse_model_responses_count",
    "bfcl_parse_model_responses_shape_label",
    "bfcl_decode_execute_called",
    "bfcl_decode_exception_class",
    "bfcl_decode_execute_nonempty",
    "bfcl_decode_output_count",
    "compact_result_status",
    "suspected_live_decode_failure_stage",
]
FALSE_KEYS = (
    "authorized",
    "provider_request_authorized",
    "live_shape_capture_authorized",
    "bfcl_generate_authorized",
    "bfcl_smoke_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "full_baseline_authorized",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
    "gpt_5_2_active",
    "openrouter_allowed",
)
FORBIDDEN_FIELD_RE = re.compile(r"(raw|prompt|case_content|provider_request|provider_response_body|response_headers|logs?|traces?|model_output_text|tool_arguments|function_name|gold|reference|expected|scorer_diff|endpoint|api_key|secret|candidate_output)", re.IGNORECASE)
FORBIDDEN_VALUE_RE = re.compile(("s" + "k-" + r"[A-Za-z0-9_-]{16,}|" + "api" + "cz" + "|" + "boyue" + "richdata|endpoint value|api key|provider payload|scorer diff|candidate output"), re.IGNORECASE)


def load_packet(path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain JSON object")
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


def _scan_values(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(data):
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_live_decode_exception_shape_capture_gate_packet":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "pending":
        blockers.append(f"approval_status_not_pending:{data.get('approval_status')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    signed_ids = data.get("signed_run_ids")
    if signed_ids != [SIGNED_ID]:
        blockers.append(f"signed_run_ids_invalid:{signed_ids!r}")
    if data.get("max_run_ids") != 1:
        blockers.append(f"max_run_ids_invalid:{data.get('max_run_ids')!r}")
    if data.get("requested_future_scope") != "one_id_live_decode_exception_shape_capture":
        blockers.append(f"requested_future_scope_invalid:{data.get('requested_future_scope')!r}")
    if data.get("compact_only") is not True:
        blockers.append("compact_only_not_true")
    if data.get("stop_after_compact_decode_exception_shape_capture") is not True:
        blockers.append("stop_after_capture_not_true")
    for key in FALSE_KEYS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    fields = data.get("allowed_compact_fields")
    if not isinstance(fields, list):
        blockers.append("allowed_compact_fields_not_list")
        fields = []
    if fields != REQUIRED_COMPACT_FIELDS:
        missing = [field for field in REQUIRED_COMPACT_FIELDS if field not in fields]
        extra = [field for field in fields if field not in REQUIRED_COMPACT_FIELDS]
        if missing:
            blockers.append(f"missing_required_compact_fields:{missing!r}")
        if extra:
            blockers.append(f"extra_compact_fields:{extra!r}")
        if fields and not missing and not extra:
            blockers.append("allowed_compact_fields_order_invalid")
    for field in fields:
        if not isinstance(field, str):
            blockers.append(f"compact_field_not_string:{field!r}")
            continue
        if FORBIDDEN_FIELD_RE.search(field):
            blockers.append(f"forbidden_compact_field:{field}")
    if "suspected_live_decode_failure_stage" not in fields:
        blockers.append("suspected_live_decode_failure_stage_missing_from_schema")
    blockers.extend(_scan_values(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet = load_packet(path)
    blockers = validate_packet(packet)
    return {
        "report_scope": "bfcl_live_decode_exception_shape_capture_gate_check",
        "packet_path": str(path),
        "bfcl_live_decode_exception_shape_capture_gate_passed": not blockers,
        "approval_status": packet.get("approval_status"),
        "signed_run_ids": packet.get("signed_run_ids"),
        "route_profile": packet.get("route_profile"),
        "route_model": packet.get("route_model"),
        "compact_field_count": len(packet.get("allowed_compact_fields", [])) if isinstance(packet.get("allowed_compact_fields"), list) else 0,
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
        summary = {"report_scope": "bfcl_live_decode_exception_shape_capture_gate_check", "bfcl_live_decode_exception_shape_capture_gate_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_live_decode_exception_shape_capture_gate_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
