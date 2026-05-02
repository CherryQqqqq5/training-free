#!/usr/bin/env python3
"""Gated BFCL live-shape telemetry runner."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_live_shape_telemetry_artifact import validate as validate_artifact
from scripts.check_bfcl_live_shape_telemetry_packet import SIGNED_IDS, check as check_packet

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_live_shape_telemetry_compact.json")
SIGNED_ENDPOINT_ENVS = ("CHUANGZHI_NOVACODE_ENDPOINT", "NOVACODE_ENDPOINT")
SIGNED_KEY_ENVS = ("CHUANGZHI_API_KEY", "NOVACODE_API_KEY")
SIGNED_TELEMETRY_CLIENT_FACTORY = "scripts.bfcl_live_shape_telemetry_client:build_signed_live_shape_telemetry_client"
TelemetryClient = Callable[[dict[str, Any]], list[dict[str, Any]]]


def _env_present(names: tuple[str, ...]) -> bool:
    return any(bool(os.environ.get(name)) for name in names)


def build_plan() -> dict[str, object]:
    packet_summary = check_packet()
    return {
        "report_scope": "bfcl_live_shape_telemetry_plan",
        "approval_status": packet_summary.get("approval_status"),
        "planned_run_ids": SIGNED_IDS,
        "planned_run_id_count": len(SIGNED_IDS),
        "route_model": "gpt-4.1",
        "active_profile": "novacode",
        "provider_request_executed": False,
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "bfcl_smoke_executed": False,
        "bfcl_scorer_executed": False,
        "candidate_runtime_activation_authorized": False,
        "performance_evidence": False,
        "raw_persistence_authorized": False,
        "output_artifact_planned": str(DEFAULT_OUTPUT),
        "signed_telemetry_client_factory": SIGNED_TELEMETRY_CLIENT_FACTORY,
        "telemetry_fields": [
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
            "upstream_returned_tool_call",
            "upstream_returned_nonempty_text",
            "upstream_returned_true_empty",
            "responses_to_chat_conversion_exercised",
            "runtime_engine_exercised",
            "engine_final_has_tool_calls",
            "engine_final_content_empty",
            "engine_coerced_nonempty_text_to_empty",
            "chat_to_responses_conversion_exercised",
            "responses_output_has_function_call",
            "responses_output_has_message_text",
            "bfcl_or_openai_decode_exercised",
            "bfcl_decode_execute_nonempty",
            "suspected_failure_stage",
        ],
        "blockers": [] if packet_summary.get("bfcl_live_shape_telemetry_packet_passed") else packet_summary.get("blockers", []),
    }


def _load_signed_client_factory(factory_ref: str) -> Callable[[dict[str, Any]], TelemetryClient]:
    if factory_ref != SIGNED_TELEMETRY_CLIENT_FACTORY:
        raise RuntimeError("telemetry_client_factory_not_signed")
    module_name, sep, function_name = factory_ref.partition(":")
    if not sep or not module_name or not function_name:
        raise RuntimeError("telemetry_client_factory_ref_invalid")
    module = importlib.import_module(module_name)
    factory = getattr(module, function_name, None)
    if not callable(factory):
        raise RuntimeError("telemetry_client_factory_not_callable")
    return factory


def _safe_error(exc: Exception) -> str:
    message = str(exc)
    if message.startswith("telemetry_"):
        return message
    return type(exc).__name__


def _sanitize_record(record: dict[str, Any], run_id: str) -> dict[str, Any]:
    allowed = {
        "run_id_label",
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
        "upstream_returned_tool_call",
        "upstream_returned_nonempty_text",
        "upstream_returned_true_empty",
        "responses_to_chat_conversion_exercised",
        "runtime_engine_exercised",
        "engine_final_has_tool_calls",
        "engine_final_content_empty",
        "engine_coerced_nonempty_text_to_empty",
        "chat_to_responses_conversion_exercised",
        "responses_output_has_function_call",
        "responses_output_has_message_text",
        "bfcl_or_openai_decode_exercised",
        "bfcl_decode_execute_nonempty",
        "suspected_failure_stage",
    }
    sanitized = {key: record.get(key) for key in allowed if key in record}
    sanitized.setdefault("run_id_label", run_id)
    for key in ("raw_text_persisted", "raw_body_persisted", "raw_payload_persisted", "raw_header_persisted", "raw_log_persisted", "raw_trace_persisted"):
        sanitized[key] = False
    return sanitized


def execute_telemetry(*, output: Path = DEFAULT_OUTPUT, client: TelemetryClient | None = None, client_factory: Callable[[dict[str, Any]], TelemetryClient] | None = None, client_factory_ref: str = SIGNED_TELEMETRY_CLIENT_FACTORY, read_env: bool = True) -> dict[str, Any]:
    packet_summary = check_packet()
    if not packet_summary.get("bfcl_live_shape_telemetry_packet_passed"):
        return {"report_scope": "bfcl_live_shape_telemetry_execute", "provider_request_executed": False, "endpoint_value_read": False, "api_key_value_read": False, "diagnostic_written": False, "blockers": packet_summary.get("blockers", [])}
    request = {
        "run_ids": list(SIGNED_IDS),
        "route_model": "gpt-4.1",
        "active_profile": "novacode",
        "max_total_cases": 2,
        "raw_persistence_authorized": False,
    }
    selected_factory: Callable[[dict[str, Any]], TelemetryClient] | None = client_factory
    if client is None and selected_factory is None:
        try:
            selected_factory = _load_signed_client_factory(client_factory_ref)
        except Exception as exc:
            return {"report_scope": "bfcl_live_shape_telemetry_execute", "provider_request_executed": False, "endpoint_value_read": False, "api_key_value_read": False, "diagnostic_written": False, "blockers": [_safe_error(exc)]}
    if read_env:
        endpoint_present = _env_present(SIGNED_ENDPOINT_ENVS)
        key_present = _env_present(SIGNED_KEY_ENVS)
        if not endpoint_present:
            return {"report_scope": "bfcl_live_shape_telemetry_execute", "provider_request_executed": False, "endpoint_value_read": False, "api_key_value_read": False, "diagnostic_written": False, "blockers": ["telemetry_endpoint_missing"]}
        if not key_present:
            return {"report_scope": "bfcl_live_shape_telemetry_execute", "provider_request_executed": False, "endpoint_value_read": True, "api_key_value_read": False, "diagnostic_written": False, "blockers": ["telemetry_api_key_missing"]}
    if client is not None:
        provider_client = client
    else:
        try:
            assert selected_factory is not None
            provider_client = selected_factory(request)
        except Exception as exc:
            return {"report_scope": "bfcl_live_shape_telemetry_execute", "provider_request_executed": False, "endpoint_value_read": bool(read_env), "api_key_value_read": bool(read_env), "diagnostic_written": False, "blockers": [_safe_error(exc)]}
    try:
        records = provider_client(request)
    except Exception as exc:
        return {"report_scope": "bfcl_live_shape_telemetry_execute", "provider_request_executed": False, "endpoint_value_read": bool(read_env), "api_key_value_read": bool(read_env), "diagnostic_written": False, "blockers": [_safe_error(exc)]}
    if not isinstance(records, list):
        return {"report_scope": "bfcl_live_shape_telemetry_execute", "provider_request_executed": True, "endpoint_value_read": bool(read_env), "api_key_value_read": bool(read_env), "diagnostic_written": False, "blockers": ["telemetry_client_records_not_list"]}
    if len(records) != len(SIGNED_IDS):
        return {"report_scope": "bfcl_live_shape_telemetry_execute", "provider_request_executed": True, "endpoint_value_read": bool(read_env), "api_key_value_read": bool(read_env), "diagnostic_written": False, "blockers": [f"telemetry_record_count_invalid:{len(records)}"]}
    sanitized_records = [_sanitize_record(record, run_id) for record, run_id in zip(records, SIGNED_IDS)]
    artifact = {
        "artifact_kind": "bfcl_live_shape_telemetry_compact",
        "active_profile": "novacode",
        "route_model": "gpt-4.1",
        "provider_request_executed": True,
        "bfcl_smoke_executed": False,
        "bfcl_scorer_executed": False,
        "candidate_runtime_activation_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "openrouter_allowed": False,
        "run_ids": list(SIGNED_IDS),
        "records": sanitized_records,
    }
    blockers = validate_artifact(artifact)
    if blockers:
        return {"report_scope": "bfcl_live_shape_telemetry_execute", "provider_request_executed": True, "endpoint_value_read": bool(read_env), "api_key_value_read": bool(read_env), "diagnostic_written": False, "blockers": blockers}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report_scope": "bfcl_live_shape_telemetry_execute", "provider_request_executed": True, "endpoint_value_read": bool(read_env), "api_key_value_read": bool(read_env), "diagnostic_written": True, "artifact_path": str(output), "blockers": []}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute-telemetry", action="store_true")
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--telemetry-client-factory", default=SIGNED_TELEMETRY_CLIENT_FACTORY)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_telemetry:
        summary = execute_telemetry(output=args.output_artifact, client_factory_ref=args.telemetry_client_factory)
    else:
        summary = build_plan()
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
