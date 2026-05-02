#!/usr/bin/env python3
"""Check one-ID BFCL live-shape telemetry compact artifact."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_one_id_live_shape_telemetry_gate import ALLOWED_TELEMETRY_FIELDS, SIGNED_IDS

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_compact.json")
REQUIRED_TOP_FALSE = (
    "bfcl_smoke_executed",
    "bfcl_evaluate_executed",
    "scorer_executed",
    "full_baseline_executed",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
    "openrouter_allowed",
    "gpt_5_2_active",
)
TOP_ALLOWED = {
    "artifact_kind",
    "route_profile",
    "route_model",
    "provider_request_executed",
    "bfcl_generate_executed",
    "bfcl_smoke_executed",
    "bfcl_evaluate_executed",
    "scorer_executed",
    "full_baseline_executed",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
    "openrouter_allowed",
    "gpt_5_2_active",
    "run_ids",
    "records",
}
FORBIDDEN_VALUE_RE = re.compile(("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz" + "|" + "boyue" + "richdata"), re.IGNORECASE)
RAW_KEY_RE = re.compile(r"(^|_)(raw|prompt|case_content|provider_payload|provider_request_body|response_body|headers|logs|traces|model_output_text|tool_arguments|gold|reference|expected|scorer_diff|candidate_output|endpoint_value|api_key_value)(_|$)", re.IGNORECASE)
ALLOWED_STATUSES = {
    "provider_true_empty",
    "provider_protocol_error",
    "provider_text_no_tool",
    "proxy_engine_tool_loss",
    "engine_text_coercion",
    "responses_envelope_loss",
    "bfcl_parse_decode_loss",
    "materialization_classifier_loss",
    "protocol_exception",
    "live_path_nonempty",
}


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
        if key and RAW_KEY_RE.search(key):
            blockers.append(f"forbidden_raw_or_secret_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            blockers.append(f"endpoint_or_key_literal:{'.'.join(path)}")
    return sorted(set(blockers))


def _bool(record: dict[str, Any], key: str) -> bool:
    return record.get(key) is True


def _validate_record(record: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    unknown = sorted(set(record) - set(ALLOWED_TELEMETRY_FIELDS))
    if unknown:
        blockers.append(f"record_unknown_fields:{unknown!r}")
    missing = [field for field in ALLOWED_TELEMETRY_FIELDS if field not in record]
    if missing:
        blockers.append(f"record_missing_fields:{missing!r}")
    if record.get("run_id") != SIGNED_IDS[0]:
        blockers.append(f"record_run_id_invalid:{record.get('run_id')!r}")
    if record.get("route_profile") != "novacode" or record.get("route_model") != "gpt-4.1":
        blockers.append("record_route_drift")
    status = record.get("suspected_live_failure_stage")
    if status not in ALLOWED_STATUSES:
        blockers.append(f"suspected_live_failure_stage_invalid:{status!r}")
    compact_status = record.get("compact_classifier_status")
    if not isinstance(compact_status, str) or not compact_status:
        blockers.append("compact_classifier_status_missing")

    provider_empty = _bool(record, "provider_response_empty_bool")
    provider_tool = _bool(record, "provider_response_has_tool_calls")
    provider_text = _bool(record, "provider_response_has_nonempty_text")
    engine_tool = _bool(record, "engine_final_has_tool_calls")
    engine_text = _bool(record, "engine_final_has_nonempty_text")
    engine_empty = _bool(record, "engine_final_content_empty")
    engine_coerced = _bool(record, "engine_coerced_nonempty_text_to_empty")
    response_function = _bool(record, "proxy_responses_output_has_function_call")
    response_text = _bool(record, "proxy_responses_output_has_nonempty_text")
    decode_called = _bool(record, "bfcl_decode_execute_called")
    decode_nonempty = _bool(record, "bfcl_decode_execute_nonempty")
    result_written = _bool(record, "result_file_written")
    result_nonempty = _bool(record, "result_file_contains_nonempty_shape")
    parse_called = _bool(record, "bfcl_parse_called")
    parse_empty = _bool(record, "bfcl_parse_model_response_empty")
    protocol_exception = _bool(record, "protocol_exception_observed")
    exception_to_empty = _bool(record, "protocol_exception_converted_to_empty_model_response")
    false_empty = _bool(record, "classifier_false_empty_for_nonempty_result")

    provider_status_class = str(record.get("provider_status_class") or "")
    provider_shape_valid = _bool(record, "provider_response_has_choices") and _bool(record, "provider_response_has_message")

    if protocol_exception:
        if exception_to_empty:
            blockers.append("protocol_exception_converted_to_empty_forbidden")
        expected = "protocol_exception" if provider_status_class == "protocol_exception" else "provider_protocol_error"
        if status != expected:
            blockers.append("protocol_exception_stage_mismatch" if expected == "protocol_exception" else "provider_protocol_error_stage_mismatch")
        return blockers
    if exception_to_empty:
        blockers.append("exception_to_empty_without_protocol_exception")
    if provider_status_class != "2xx":
        if status != "provider_protocol_error":
            blockers.append("provider_protocol_error_stage_mismatch")
        if provider_empty and status == "provider_true_empty":
            blockers.append("provider_true_empty_requires_2xx_valid_shape")
        return blockers

    if provider_empty:
        if provider_status_class != "2xx" or not provider_shape_valid:
            blockers.append("provider_true_empty_requires_2xx_valid_shape")
        if provider_tool or provider_text:
            blockers.append("provider_empty_with_tool_or_text")
        if status != "provider_true_empty":
            blockers.append("provider_true_empty_stage_mismatch")
    elif provider_text and not provider_tool and engine_empty:
        if not engine_coerced or status != "engine_text_coercion":
            blockers.append("engine_text_coercion_stage_mismatch")
    elif provider_text and not provider_tool:
        if status != "provider_text_no_tool":
            blockers.append("provider_text_no_tool_stage_mismatch")
    elif provider_tool and not engine_tool:
        if status != "proxy_engine_tool_loss":
            blockers.append("proxy_engine_tool_loss_stage_mismatch")
    elif engine_tool and not response_function:
        if status != "responses_envelope_loss":
            blockers.append("responses_envelope_loss_stage_mismatch")
    elif (response_function or response_text) and (not parse_called or parse_empty or not decode_called or not decode_nonempty):
        if status != "bfcl_parse_decode_loss":
            blockers.append("bfcl_parse_decode_loss_stage_mismatch")
    elif decode_nonempty and (not result_written or not result_nonempty or false_empty or compact_status == "empty_model_response"):
        if status != "materialization_classifier_loss":
            blockers.append("materialization_classifier_loss_stage_mismatch")
    elif decode_nonempty and result_written and result_nonempty and not false_empty:
        if status != "live_path_nonempty":
            blockers.append("live_path_nonempty_stage_mismatch")
    else:
        blockers.append("unclassified_live_shape_state")
    return blockers


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_one_id_live_shape_telemetry_compact":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    unknown_top = sorted(set(data) - TOP_ALLOWED)
    if unknown_top:
        blockers.append(f"top_unknown_fields:{unknown_top!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("artifact_route_drift")
    if data.get("run_ids") != SIGNED_IDS:
        blockers.append(f"run_ids_invalid:{data.get('run_ids')!r}")
    records = data.get("records")
    if not isinstance(records, list) or len(records) != 1:
        blockers.append(f"record_count_invalid:{0 if not isinstance(records, list) else len(records)}")
    else:
        blockers.extend(_validate_record(records[0]))
    for key in REQUIRED_TOP_FALSE:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    for key in ("provider_request_executed", "bfcl_generate_executed"):
        if data.get(key) not in {True, False}:
            blockers.append(f"{key}_not_bool:{data.get(key)!r}")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    return {
        "report_scope": "bfcl_one_id_live_shape_telemetry_artifact_check",
        "artifact_path": str(path),
        "bfcl_one_id_live_shape_telemetry_artifact_passed": not blockers,
        "run_ids": data.get("run_ids"),
        "route_model": data.get("route_model"),
        "suspected_live_failure_stage": data.get("records", [{}])[0].get("suspected_live_failure_stage") if isinstance(data.get("records"), list) and data.get("records") else None,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "bfcl_one_id_live_shape_telemetry_artifact_check", "bfcl_one_id_live_shape_telemetry_artifact_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_one_id_live_shape_telemetry_artifact_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
