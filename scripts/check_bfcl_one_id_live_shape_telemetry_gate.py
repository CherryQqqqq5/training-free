#!/usr/bin/env python3
"""Check the one-ID BFCL live-shape telemetry gate packet."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_gate_packet.json")
SIGNED_IDS = ["web_search_base_0"]
ALLOWED_TELEMETRY_FIELDS = [
    "run_id",
    "route_profile",
    "route_model",
    "local_proxy_endpoint_path_label",
    "bfcl_handler_class_label",
    "bfcl_api_path_label",
    "request_shape_hash",
    "request_message_count_bucket",
    "request_has_instructions",
    "request_has_tools",
    "request_tool_count",
    "request_tool_choice_shape",
    "request_token_field_shape",
    "provider_status_class",
    "provider_response_empty_bool",
    "provider_response_has_choices",
    "provider_response_has_message",
    "provider_response_has_tool_calls",
    "provider_response_has_nonempty_text",
    "engine_apply_response_called",
    "engine_final_has_tool_calls",
    "engine_final_has_nonempty_text",
    "engine_final_content_empty",
    "engine_coerced_nonempty_text_to_empty",
    "proxy_responses_output_has_function_call",
    "proxy_responses_output_has_nonempty_text",
    "bfcl_parse_called",
    "bfcl_parse_model_response_empty",
    "bfcl_decode_execute_called",
    "bfcl_decode_execute_nonempty",
    "result_file_written",
    "result_file_contains_nonempty_shape",
    "compact_classifier_status",
    "suspected_live_failure_stage",
]
AUTHORIZATION_KEYS = (
    "authorized",
    "provider_request_authorized",
    "bfcl_generate_authorized",
)
ALWAYS_FALSE_KEYS = (
    "bfcl_smoke_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "full_baseline_authorized",
    "bfcl_baseline_authorized",
    "candidate_runtime_activation_authorized",
    "candidate_runtime_activation_allowed",
    "candidate_generation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
    "openrouter_allowed",
    "gpt_5_2_active",
    "raw_prompt_text_allowed",
    "raw_bfcl_case_content_allowed",
    "raw_provider_request_allowed",
    "raw_provider_response_body_allowed",
    "raw_response_headers_allowed",
    "raw_logs_allowed",
    "raw_traces_allowed",
    "raw_model_output_text_allowed",
    "raw_tool_arguments_allowed",
    "case_gold_reference_expected_allowed",
    "scorer_diff_allowed",
    "source_nonce_mapping_allowed",
    "candidate_output_allowed",
    "raw_persistence_authorized",
    "endpoint_value_committed",
    "api_key_value_committed",
)
TRUE_KEYS = (
    "candidate_specs_inert",
    "endpoint_env_only",
    "api_key_env_only",
    "generate_only",
    "one_live_bfcl_shaped_provider_path",
    "compact_shape_telemetry_only",
)
FORBIDDEN_VALUE_RE = re.compile(("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz" + "|" + "boyue" + "richdata"), re.IGNORECASE)
RAW_FIELD_RE = re.compile(r"(^|_)(raw|prompt|case_content|provider_payload|response_body|headers|logs|traces|model_output_text|tool_arguments|gold|reference|expected|scorer_diff|candidate_output|endpoint_value|api_key_value)(_|$)", re.IGNORECASE)
RAW_MARKER_RE = re.compile(r"(raw prompt|raw bfcl case|provider payload|provider request|response body|scorer diff|gold/reference/expected|candidate output|endpoint/key value|source nonce)", re.IGNORECASE)
ALLOWED_RAW_CONTEXT_KEYS = {"forbidden_telemetry_content"}
ALLOWED_FALSE_RAW_KEYS = set(ALWAYS_FALSE_KEYS)


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


def _scan(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(data):
        key = path[-1] if path else ""
        if key and RAW_FIELD_RE.search(key) and key not in ALLOWED_FALSE_RAW_KEYS:
            blockers.append(f"forbidden_raw_or_secret_key:{'.'.join(path)}")
        if isinstance(value, str):
            if FORBIDDEN_VALUE_RE.search(value):
                blockers.append(f"endpoint_or_key_literal:{'.'.join(path)}")
            if not (path and path[0] in ALLOWED_RAW_CONTEXT_KEYS) and RAW_MARKER_RE.search(value):
                blockers.append(f"raw_marker_literal:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_one_id_live_shape_telemetry_gate_packet":
        blockers.append(f"packet_kind_invalid:{data.get('artifact_kind')!r}")
    approval_status = data.get("approval_status")
    if approval_status not in {"pending", "approved"}:
        blockers.append(f"approval_status_invalid:{approval_status!r}")
    expected_auth = approval_status == "approved"
    for key in AUTHORIZATION_KEYS:
        if data.get(key) is not expected_auth:
            blockers.append(f"{key}_invalid_for_{approval_status}:{data.get(key)!r}")
    for key in ALWAYS_FALSE_KEYS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    for key in TRUE_KEYS:
        if data.get(key) is not True:
            blockers.append(f"{key}_not_true:{data.get(key)!r}")
    ids = data.get("signed_run_ids") if isinstance(data.get("signed_run_ids"), list) else []
    if ids != SIGNED_IDS:
        blockers.append(f"signed_run_ids_invalid:{ids!r}")
    if len(ids) > 1:
        blockers.append(f"too_many_run_ids:{len(ids)}")
    if len(set(ids)) != len(ids):
        blockers.append("duplicate_run_ids")
    if data.get("max_run_ids") != 1:
        blockers.append(f"max_run_ids_invalid:{data.get('max_run_ids')!r}")
    if data.get("route_profile") != "novacode":
        blockers.append(f"route_profile_invalid:{data.get('route_profile')!r}")
    if data.get("provider_profile") != "Chuangzhi/Novacode":
        blockers.append(f"provider_profile_invalid:{data.get('provider_profile')!r}")
    if data.get("route_model") != "gpt-4.1":
        blockers.append(f"route_model_invalid:{data.get('route_model')!r}")
    if data.get("gpt_5_2_status") != "historical_superseded_only":
        blockers.append(f"gpt_5_2_status_invalid:{data.get('gpt_5_2_status')!r}")
    if data.get("requested_future_scope") != "one_id_live_shape_bfcl_generate_only_telemetry":
        blockers.append(f"requested_future_scope_invalid:{data.get('requested_future_scope')!r}")
    if data.get("runner_path") != "scripts/run_bfcl_one_id_live_shape_telemetry.py":
        blockers.append(f"runner_path_invalid:{data.get('runner_path')!r}")
    if data.get("checker_path") != "scripts/check_bfcl_one_id_live_shape_telemetry_gate.py":
        blockers.append(f"checker_path_invalid:{data.get('checker_path')!r}")
    if data.get("allowed_telemetry_fields") != ALLOWED_TELEMETRY_FIELDS:
        blockers.append("allowed_telemetry_fields_drift")
    for field in data.get("allowed_telemetry_fields", []):
        if not isinstance(field, str) or RAW_FIELD_RE.search(field):
            blockers.append(f"forbidden_output_field:{field!r}")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    data = _load(packet_path)
    blockers = validate_packet(data)
    return {
        "report_scope": "bfcl_one_id_live_shape_telemetry_gate_check",
        "packet_path": str(packet_path),
        "approval_status": data.get("approval_status"),
        "signed_run_ids": data.get("signed_run_ids"),
        "provider_request_authorized": data.get("provider_request_authorized"),
        "bfcl_generate_authorized": data.get("bfcl_generate_authorized"),
        "bfcl_one_id_live_shape_telemetry_gate_passed": not blockers,
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
        summary = {"report_scope": "bfcl_one_id_live_shape_telemetry_gate_check", "bfcl_one_id_live_shape_telemetry_gate_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_one_id_live_shape_telemetry_gate_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
