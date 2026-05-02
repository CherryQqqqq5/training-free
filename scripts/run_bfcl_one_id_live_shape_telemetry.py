#!/usr/bin/env python3
"""Plan or execute one-ID BFCL live-shape telemetry.

The committed packet is pending/fail-closed. Execute mode is present for a
future reviewed packet state and is testable with a signed fake live-capture
callable; dry-run/plan never reads endpoint or key values.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_one_id_live_shape_telemetry_artifact import validate as validate_artifact
from scripts.check_bfcl_one_id_live_shape_telemetry_gate import ALLOWED_TELEMETRY_FIELDS, SIGNED_IDS, check as check_packet

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_gate_packet.json")
DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_compact.json")
AFTER_TOOL_CHOICE_PATCH_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_after_tool_choice_patch_compact.json")
SIGNED_ROUTE_PROFILE = "novacode"
SIGNED_ROUTE_MODEL = "gpt-4.1"
SIGNED_LIVE_CAPTURE_FACTORY = "scripts.bfcl_one_id_live_shape_telemetry_capture:build_signed_one_id_live_shape_capture"
LiveCapture = Callable[[dict[str, Any]], dict[str, Any]]
LiveCaptureFactory = Callable[[dict[str, Any]], LiveCapture]


def _packet_output_blockers(packet_path: Path, output_artifact: Path) -> list[str]:
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"packet_output_scope_load_failed:{type(exc).__name__}"]
    scoped_output = packet.get("output_artifact")
    output_scope_required = packet.get("output_artifact_must_not_preexist") is True
    if output_scope_required and isinstance(scoped_output, str) and scoped_output:
        if Path(scoped_output) != output_artifact:
            return [f"output_artifact_mismatch_packet_scope:{output_artifact}"]
    return []


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    return {
        "report_scope": "bfcl_one_id_live_shape_telemetry_plan",
        "approval_status": packet_summary.get("approval_status"),
        "planned_run_ids": list(SIGNED_IDS),
        "planned_run_id_count": len(SIGNED_IDS),
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "generate_only": True,
        "provider_request_executed": False,
        "bfcl_generate_executed": False,
        "bfcl_smoke_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "raw_persistence_authorized": False,
        "output_artifact_planned": str(output_artifact),
        "signed_live_capture_factory": SIGNED_LIVE_CAPTURE_FACTORY,
        "telemetry_fields": list(ALLOWED_TELEMETRY_FIELDS),
        "blockers": ([] if packet_summary.get("bfcl_one_id_live_shape_telemetry_gate_passed") else packet_summary.get("blockers", [])) + _packet_output_blockers(packet_path, output_artifact),
    }


def _default_record() -> dict[str, Any]:
    return {
        "run_id": SIGNED_IDS[0],
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "local_proxy_endpoint_path_label": "bfcl_generate_local_proxy_responses_v1",
        "bfcl_handler_class_label": "openai_responses_handler",
        "bfcl_api_path_label": "responses",
        "request_shape_hash": "shape_hash_unavailable_in_scaffold",
        "request_message_count_bucket": "unknown",
        "request_has_instructions": False,
        "request_has_tools": False,
        "request_tool_count": 0,
        "request_tool_choice_shape": "unknown",
        "request_token_field_shape": "unknown",
        "provider_status_class": "not_executed",
        "provider_response_empty_bool": False,
        "provider_response_has_choices": False,
        "provider_response_has_message": False,
        "provider_response_has_tool_calls": False,
        "provider_response_has_nonempty_text": False,
        "engine_apply_response_called": False,
        "engine_final_has_tool_calls": False,
        "engine_final_has_nonempty_text": False,
        "engine_final_content_empty": False,
        "engine_coerced_nonempty_text_to_empty": False,
        "proxy_responses_output_has_function_call": False,
        "proxy_responses_output_has_nonempty_text": False,
        "bfcl_parse_called": False,
        "bfcl_parse_model_response_empty": False,
        "bfcl_decode_execute_called": False,
        "bfcl_decode_execute_nonempty": False,
        "result_file_written": False,
        "result_file_contains_nonempty_shape": False,
        "compact_classifier_status": "not_executed",
        "protocol_exception_observed": False,
        "protocol_exception_converted_to_empty_model_response": False,
        "classifier_false_empty_for_nonempty_result": False,
        "suspected_live_failure_stage": "provider_true_empty",
    }


def _sanitize_record(record: dict[str, Any]) -> dict[str, Any]:
    sanitized = _default_record()
    for key in ALLOWED_TELEMETRY_FIELDS:
        if key in record:
            sanitized[key] = record[key]
    sanitized["run_id"] = SIGNED_IDS[0]
    sanitized["route_profile"] = SIGNED_ROUTE_PROFILE
    sanitized["route_model"] = SIGNED_ROUTE_MODEL
    return sanitized


def _artifact_from_record(record: dict[str, Any], *, provider_request_executed: bool, bfcl_generate_executed: bool) -> dict[str, Any]:
    return {
        "artifact_kind": "bfcl_one_id_live_shape_telemetry_compact",
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "provider_request_executed": bool(provider_request_executed),
        "bfcl_generate_executed": bool(bfcl_generate_executed),
        "bfcl_smoke_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "openrouter_allowed": False,
        "gpt_5_2_active": False,
        "run_ids": list(SIGNED_IDS),
        "records": [_sanitize_record(record)],
    }


def _safe_error(exc: Exception) -> str:
    message = str(exc)
    if message.startswith("one_id_") or message.startswith("live_shape_"):
        return message
    return type(exc).__name__


def _load_signed_live_capture_factory(factory_ref: str) -> LiveCaptureFactory:
    if factory_ref != SIGNED_LIVE_CAPTURE_FACTORY:
        raise RuntimeError("one_id_live_capture_factory_not_signed")
    module_name, sep, function_name = factory_ref.partition(":")
    if not sep or not module_name or not function_name:
        raise RuntimeError("one_id_live_capture_factory_ref_invalid")
    module = importlib.import_module(module_name)
    factory = getattr(module, function_name, None)
    if not callable(factory):
        raise RuntimeError("one_id_live_capture_factory_not_callable")
    return factory


def execute_live_telemetry(*, packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT, clean_output: bool = False, live_capture: LiveCapture | None = None, live_capture_factory: LiveCaptureFactory | None = None, live_capture_factory_ref: str = SIGNED_LIVE_CAPTURE_FACTORY) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    output_blockers = _packet_output_blockers(packet_path, output_artifact)
    if output_blockers:
        return {
            "report_scope": "bfcl_one_id_live_shape_telemetry_execute",
            "provider_request_executed": False,
            "bfcl_generate_executed": False,
            "endpoint_value_read": False,
            "api_key_value_read": False,
            "diagnostic_written": False,
            "blockers": output_blockers,
        }
    if not packet_summary.get("bfcl_one_id_live_shape_telemetry_gate_passed"):
        return {
            "report_scope": "bfcl_one_id_live_shape_telemetry_execute",
            "provider_request_executed": False,
            "bfcl_generate_executed": False,
            "endpoint_value_read": False,
            "api_key_value_read": False,
            "diagnostic_written": False,
            "blockers": packet_summary.get("blockers", []),
        }
    if packet_summary.get("approval_status") != "approved":
        return {
            "report_scope": "bfcl_one_id_live_shape_telemetry_execute",
            "provider_request_executed": False,
            "bfcl_generate_executed": False,
            "endpoint_value_read": False,
            "api_key_value_read": False,
            "diagnostic_written": False,
            "blockers": ["one_id_live_shape_telemetry_packet_not_approved"],
        }
    if output_artifact.exists() and not clean_output:
        return {
            "report_scope": "bfcl_one_id_live_shape_telemetry_execute",
            "provider_request_executed": False,
            "bfcl_generate_executed": False,
            "endpoint_value_read": False,
            "api_key_value_read": False,
            "diagnostic_written": False,
            "blockers": ["output_artifact_exists_without_clean_output"],
        }
    request = {
        "run_ids": list(SIGNED_IDS),
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "generate_only": True,
        "raw_persistence_authorized": False,
    }
    if live_capture is None:
        selected_factory = live_capture_factory
        if selected_factory is None:
            try:
                selected_factory = _load_signed_live_capture_factory(live_capture_factory_ref)
            except Exception as exc:
                return {
                    "report_scope": "bfcl_one_id_live_shape_telemetry_execute",
                    "provider_request_executed": False,
                    "bfcl_generate_executed": False,
                    "endpoint_value_read": False,
                    "api_key_value_read": False,
                    "diagnostic_written": False,
                    "blockers": [_safe_error(exc)],
                }
        try:
            live_capture = selected_factory(request)
        except Exception as exc:
            return {
                "report_scope": "bfcl_one_id_live_shape_telemetry_execute",
                "provider_request_executed": False,
                "bfcl_generate_executed": False,
                "endpoint_value_read": False,
                "api_key_value_read": False,
                "diagnostic_written": False,
                "blockers": [_safe_error(exc)],
            }
    try:
        captured = live_capture(request)
    except Exception as exc:
        return {
            "report_scope": "bfcl_one_id_live_shape_telemetry_execute",
            "provider_request_executed": False,
            "bfcl_generate_executed": False,
            "endpoint_value_read": False,
            "api_key_value_read": False,
            "diagnostic_written": False,
            "blockers": [_safe_error(exc)],
        }
    if not isinstance(captured, dict):
        return {
            "report_scope": "bfcl_one_id_live_shape_telemetry_execute",
            "provider_request_executed": False,
            "bfcl_generate_executed": False,
            "endpoint_value_read": False,
            "api_key_value_read": False,
            "diagnostic_written": False,
            "blockers": ["live_capture_record_not_object"],
        }
    artifact = _artifact_from_record(captured, provider_request_executed=bool(captured.get("provider_request_executed", True)), bfcl_generate_executed=bool(captured.get("bfcl_generate_executed", True)))
    blockers = validate_artifact(artifact)
    if blockers:
        return {
            "report_scope": "bfcl_one_id_live_shape_telemetry_execute",
            "provider_request_executed": artifact["provider_request_executed"],
            "bfcl_generate_executed": artifact["bfcl_generate_executed"],
            "endpoint_value_read": False,
            "api_key_value_read": False,
            "diagnostic_written": False,
            "blockers": blockers,
        }
    output_artifact.parent.mkdir(parents=True, exist_ok=True)
    output_artifact.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "report_scope": "bfcl_one_id_live_shape_telemetry_execute",
        "provider_request_executed": artifact["provider_request_executed"],
        "bfcl_generate_executed": artifact["bfcl_generate_executed"],
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "diagnostic_written": True,
        "artifact_path": str(output_artifact),
        "blockers": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute-live-telemetry", action="store_true")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--clean-output", action="store_true")
    parser.add_argument("--live-capture-factory", default=SIGNED_LIVE_CAPTURE_FACTORY)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_live_telemetry:
        summary = execute_live_telemetry(packet_path=args.packet, output_artifact=args.output_artifact, clean_output=args.clean_output, live_capture_factory_ref=args.live_capture_factory)
    else:
        summary = build_plan(packet_path=args.packet, output_artifact=args.output_artifact)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
