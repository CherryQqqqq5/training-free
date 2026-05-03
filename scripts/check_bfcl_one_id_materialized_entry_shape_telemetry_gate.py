#!/usr/bin/env python3
"""Check the one-ID materialized-entry shape telemetry gate packet."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_materialized_entry_shape_telemetry_gate_packet.json")
SIGNED_ID = "multi_turn_long_context_0"
REQUIRED_COMPACT_FIELDS = [
    "run_id",
    "route_profile",
    "route_model",
    "bfcl_decode_execute_nonempty",
    "bfcl_decode_output_count",
    "materialization_called",
    "materialized_result_written",
    "materialized_entry_shape_label",
    "materialized_entry_has_grc_decoded_execution_output_shape",
    "materialized_marker_shape_label",
    "materialized_marker_decoded_output_count_nonzero",
    "materialized_result_field_shape_label",
    "materialized_inference_log_present",
    "materialized_protocol_error_indicator_present",
    "classifier_input_shape_label",
    "classifier_detected_nonempty",
    "classifier_status",
    "compact_result_status",
    "suspected_materialized_entry_shape_stage",
]
FALSE_KEYS = (
    "authorized",
    "provider_request_authorized",
    "live_materialized_entry_shape_telemetry_authorized",
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
ALLOWED_RAWISH_KEYS = {
    "provider_request_authorized",
    "runner_path",
    "checker_path",
    "source_artifact",
}
FORBIDDEN_KEY_RE = re.compile(
    r"(raw|prompt|case_content|provider_request_body|provider_response_body|response_headers|logs?|traces?|model_text|tool_args?|tool_arguments|function_name|gold|reference|expected|scorer_diff|endpoint|api_key|secret|candidate_output|raw_path|result_path)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|endpoint " + "value|api " + "key|provider " + "payload|raw " + "prompt|raw " + "case|raw " + "path|scorer " + "diff|candidate " + "output|gpt-4o|openrouter|gpt-5.2"),
    re.IGNORECASE,
)


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


def _scan(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(data):
        key = path[-1] if path else ""
        if path and path[0] == "forbidden_content":
            continue
        if key and key not in ALLOWED_RAWISH_KEYS and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if path and path[-1] == "route_model" and value == "gpt-4.1":
                continue
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_one_id_materialized_entry_shape_telemetry_gate_packet":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "pending":
        blockers.append(f"approval_status_invalid:{data.get('approval_status')!r}")
    for key in FALSE_KEYS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    if data.get("signed_run_ids") != [SIGNED_ID]:
        blockers.append(f"signed_run_ids_invalid:{data.get('signed_run_ids')!r}")
    if data.get("max_run_ids") != 1:
        blockers.append(f"max_run_ids_invalid:{data.get('max_run_ids')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    if data.get("candidate_specs_inert") is not True:
        blockers.append(f"candidate_specs_inert_not_true:{data.get('candidate_specs_inert')!r}")
    if data.get("requested_future_scope") != "one_id_materialized_entry_shape_telemetry":
        blockers.append(f"requested_future_scope_invalid:{data.get('requested_future_scope')!r}")
    if data.get("source_stage") != "unknown_compact_status_after_decode":
        blockers.append(f"source_stage_invalid:{data.get('source_stage')!r}")
    if not str(data.get("source_artifact", "")).endswith("bfcl_one_id_protocol_error_telemetry_after_protocol_status_patch_compact.json"):
        blockers.append(f"source_artifact_invalid:{data.get('source_artifact')!r}")
    for key in ("generate_only_path_for_future_capture", "stop_after_compact_materialized_entry_shape_capture", "compact_only"):
        if data.get(key) is not True:
            blockers.append(f"{key}_not_true:{data.get(key)!r}")
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
        elif field not in REQUIRED_COMPACT_FIELDS and FORBIDDEN_KEY_RE.search(field):
            blockers.append(f"forbidden_compact_field:{field}")
    for required in (
        "materialized_entry_shape_label",
        "materialized_entry_has_grc_decoded_execution_output_shape",
        "materialized_marker_shape_label",
        "materialized_marker_decoded_output_count_nonzero",
        "materialized_result_field_shape_label",
        "materialized_inference_log_present",
        "materialized_protocol_error_indicator_present",
        "classifier_input_shape_label",
        "suspected_materialized_entry_shape_stage",
    ):
        if required not in fields:
            blockers.append(f"materialized_entry_schema_field_missing:{required}")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet = load_packet(path)
    blockers = validate_packet(packet)
    return {
        "report_scope": "bfcl_one_id_materialized_entry_shape_telemetry_gate_check",
        "packet_path": str(path),
        "bfcl_one_id_materialized_entry_shape_telemetry_gate_passed": not blockers,
        "approval_status": packet.get("approval_status"),
        "provider_request_authorized": packet.get("provider_request_authorized"),
        "live_materialized_entry_shape_telemetry_authorized": packet.get("live_materialized_entry_shape_telemetry_authorized"),
        "bfcl_generate_authorized": packet.get("bfcl_generate_authorized"),
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
        summary = {
            "report_scope": "bfcl_one_id_materialized_entry_shape_telemetry_gate_check",
            "bfcl_one_id_materialized_entry_shape_telemetry_gate_passed": False,
            "blockers": [f"load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_one_id_materialized_entry_shape_telemetry_gate_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
