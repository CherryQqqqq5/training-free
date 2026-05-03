#!/usr/bin/env python3
"""Run or dry-run one-ID live decode exception shape capture."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.bfcl_one_id_live_shape_telemetry_capture import (  # noqa: E402
    SIGNED_ID_MANIFEST,
    SIGNED_ROUTE_MODEL,
    SIGNED_ROUTE_PROFILE,
    _bfcl_generate_subprocess_env,
    _engine_observation_from_trace,
    _load_latest_trace,
    _one_id_generate_command,
    _provider_observation_from_trace,
    _responses_output_observation_from_trace,
    _result_observation,
    _shape_from_trace,
    _start_proxy,
    _sync_fixture_env,
    _temporary_one_id_manifest,
    _temporary_run_root,
    _terminate_proxy,
    _write_one_id_run_ids,
)
from scripts.check_bfcl_live_decode_exception_shape_capture_artifact import validate as validate_artifact  # noqa: E402
from scripts.check_bfcl_live_decode_exception_shape_capture_gate import (  # noqa: E402
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    SIGNED_ID,
    check as check_packet,
)
from scripts.run_bfcl_exact_2id_generate_smoke import REPO_ROOT as BFCL_REPO_ROOT, RUNTIME_CONFIG, RULES_DIR  # noqa: E402

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_live_decode_exception_shape_capture_compact.json")


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    return {
        "report_scope": "bfcl_live_decode_exception_shape_capture_plan",
        "approval_status": packet_summary.get("approval_status"),
        "planned_run_ids": [SIGNED_ID],
        "planned_run_id_count": 1,
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "generate_only": True,
        "stop_after_compact_decode_exception_shape_capture": True,
        "provider_request_executed": False,
        "live_shape_capture_executed": False,
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
        "output_artifact_planned": str(output_artifact),
        "compact_fields": list(REQUIRED_COMPACT_FIELDS),
        "blockers": [] if packet_summary.get("bfcl_live_decode_exception_shape_capture_gate_passed") else packet_summary.get("blockers", []),
    }


def _load_decode_events(path: Path) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    parse_events = [event for event in events if event.get("event") == "bfcl_parse"]
    decode_events = [event for event in events if event.get("event") == "bfcl_decode"]
    parse = parse_events[-1] if parse_events else {}
    decode = decode_events[-1] if decode_events else {}
    return {
        "proxy_function_call_item_count": int(parse.get("proxy_function_call_item_count") or 0),
        "proxy_function_call_has_call_id": bool(parse.get("proxy_function_call_has_call_id")),
        "proxy_function_call_has_name": bool(parse.get("proxy_function_call_has_name")),
        "proxy_function_call_has_arguments": bool(parse.get("proxy_function_call_has_arguments")),
        "proxy_function_call_has_status": bool(parse.get("proxy_function_call_has_status")),
        "proxy_function_call_has_id": bool(parse.get("proxy_function_call_has_id")),
        "proxy_name_field_placement_label": str(parse.get("proxy_name_field_placement_label") or "missing"),
        "proxy_arguments_shape_label": str(parse.get("proxy_arguments_shape_label") or "missing"),
        "proxy_arguments_json_parseable_bool": parse.get("proxy_arguments_json_parseable_bool") if isinstance(parse.get("proxy_arguments_json_parseable_bool"), bool) else False,
        "proxy_status_shape_label": str(parse.get("proxy_status_shape_label") or "missing"),
        "proxy_call_id_source_label": str(parse.get("proxy_call_id_source_label") or "missing"),
        "bfcl_parse_called": bool(parse.get("bfcl_parse_called")),
        "bfcl_parse_exception_class": str(parse.get("bfcl_parse_exception_class") or "not_observed"),
        "bfcl_parse_model_responses_count": int(parse.get("bfcl_parse_model_responses_count") or 0),
        "bfcl_parse_model_responses_shape_label": str(parse.get("bfcl_parse_model_responses_shape_label") or "not_observed"),
        "bfcl_decode_execute_called": bool(decode.get("bfcl_decode_execute_called")),
        "bfcl_decode_exception_class": str(decode.get("bfcl_decode_exception_class") or "not_observed"),
        "bfcl_decode_execute_nonempty": bool(decode.get("bfcl_decode_execute_nonempty")),
        "bfcl_decode_output_count": int(decode.get("bfcl_decode_output_count") or 0),
    }


def _derive_stage(record: dict[str, Any]) -> str:
    if record.get("bfcl_parse_exception_class") not in {"none", "not_observed"}:
        return "bfcl_parse_exception"
    if record.get("bfcl_decode_exception_class") not in {"none", "not_observed"}:
        return "bfcl_decode_exception"
    if record.get("proxy_responses_output_has_function_call") and not record.get("bfcl_decode_execute_nonempty"):
        return "bfcl_decode_empty_without_exception"
    if record.get("bfcl_decode_execute_nonempty") and record.get("compact_result_status") != "success_nonempty":
        return "materialization_or_classifier_after_decode"
    if record.get("bfcl_decode_execute_nonempty"):
        return "live_decode_nonempty"
    return "live_decode_shape_not_observed"


def _record_from_run(run_root: Path, decode_capture_path: Path) -> dict[str, Any]:
    trace = _load_latest_trace(run_root / "traces")
    result = _result_observation(SIGNED_ID, run_root / "bfcl/result")
    record: dict[str, Any] = {
        "run_id": SIGNED_ID,
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "bfcl_handler_class_label": "openai_responses_handler",
        "bfcl_api_path_label": "responses",
    }
    provider = _provider_observation_from_trace(trace)
    responses = _responses_output_observation_from_trace(trace)
    decode = _load_decode_events(decode_capture_path)
    record.update({
        "provider_status_class": provider["provider_status_class"],
        "provider_response_has_tool_calls": provider["provider_response_has_tool_calls"],
        "provider_response_has_nonempty_text": provider["provider_response_has_nonempty_text"],
        "proxy_responses_output_has_function_call": responses["proxy_responses_output_has_function_call"],
    })
    record.update(decode)
    status = str(result.get("compact_classifier_status") or "missing_result")
    if result.get("result_file_contains_nonempty_shape") is True and status not in {"empty_model_response", "protocol_error"}:
        status = "success_nonempty"
    record["compact_result_status"] = status
    record["suspected_live_decode_failure_stage"] = _derive_stage(record)
    return {field: record.get(field) for field in REQUIRED_COMPACT_FIELDS}


def _artifact(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_kind": "bfcl_live_decode_exception_shape_capture_compact",
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "provider_request_executed": True,
        "live_shape_capture_executed": True,
        "bfcl_generate_executed": True,
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
        "gpt_5_2_active": False,
        "openrouter_allowed": False,
        "run_ids": [SIGNED_ID],
        "records": [record],
    }


def execute_live_shape_capture(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_live_decode_exception_shape_capture_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("live_decode_exception_shape_capture_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    if blockers:
        return {
            "report_scope": "bfcl_live_decode_exception_shape_capture_execute",
            "provider_request_executed": False,
            "live_shape_capture_executed": False,
            "bfcl_generate_executed": False,
            "bfcl_smoke_executed": False,
            "bfcl_evaluate_executed": False,
            "scorer_executed": False,
            "full_baseline_executed": False,
            "endpoint_value_read": False,
            "api_key_value_read": False,
            "diagnostic_written": False,
            "output_artifact_planned": str(output_artifact),
            "blockers": sorted(set(blockers)),
        }
    runtime_config = BFCL_REPO_ROOT / RUNTIME_CONFIG
    rules_dir = BFCL_REPO_ROOT / RULES_DIR
    port = int(os.environ.get("GRC_LIVE_DECODE_CAPTURE_PORT") or 8131)
    proxy_proc = None
    with _temporary_run_root(prefix="bfcl_live_decode_exception_shape_capture_") as run_root:
        _write_one_id_run_ids(run_root)
        _sync_fixture_env(run_root, port)
        decode_capture_path = run_root / "decode_shape_capture.jsonl"
        try:
            with _temporary_one_id_manifest():
                proxy_proc = _start_proxy(port, run_root / "traces", runtime_config, rules_dir, run_root / "proxy.log")
                env = _bfcl_generate_subprocess_env(port)
                env["GRC_BFCL_DECODE_SHAPE_CAPTURE_PATH"] = str(decode_capture_path)
                completed = subprocess.run(
                    _one_id_generate_command(run_root),
                    cwd=BFCL_REPO_ROOT,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            record = _record_from_run(run_root, decode_capture_path)
            artifact = _artifact(record)
            blockers = validate_artifact(artifact)
            if blockers:
                return {
                    "report_scope": "bfcl_live_decode_exception_shape_capture_execute",
                    "provider_request_executed": True,
                    "live_shape_capture_executed": True,
                    "bfcl_generate_executed": True,
                    "bfcl_smoke_executed": False,
                    "bfcl_evaluate_executed": False,
                    "scorer_executed": False,
                    "full_baseline_executed": False,
                    "endpoint_value_read": False,
                    "api_key_value_read": False,
                    "diagnostic_written": False,
                    "returncode": completed.returncode,
                    "blockers": blockers,
                }
            output_artifact.parent.mkdir(parents=True, exist_ok=True)
            output_artifact.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return {
                "report_scope": "bfcl_live_decode_exception_shape_capture_execute",
                "provider_request_executed": True,
                "live_shape_capture_executed": True,
                "bfcl_generate_executed": True,
                "bfcl_smoke_executed": False,
                "bfcl_evaluate_executed": False,
                "scorer_executed": False,
                "full_baseline_executed": False,
                "endpoint_value_read": False,
                "api_key_value_read": False,
                "diagnostic_written": True,
                "artifact_path": str(output_artifact),
                "returncode": completed.returncode,
                "blockers": [],
            }
        finally:
            _terminate_proxy(proxy_proc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute-live-shape-capture", action="store_true")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_live_shape_capture:
        summary = execute_live_shape_capture(args.packet, args.output_artifact)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    ok = not summary.get("blockers")
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
