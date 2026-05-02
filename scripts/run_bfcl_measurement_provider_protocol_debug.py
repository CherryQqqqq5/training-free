#!/usr/bin/env python3
"""Run or plan a synthetic BFCL measurement provider protocol debug probe."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_measurement_provider_protocol_debug_artifact import validate_artifact
from scripts.check_bfcl_measurement_provider_protocol_debug_packet import check as check_packet

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_measurement_provider_protocol_debug_packet.json")
ENDPOINT_ENVS = ("CHUANGZHI_NOVACODE_ENDPOINT", "NOVACODE_ENDPOINT")
KEY_ENVS = ("CHUANGZHI_API_KEY", "NOVACODE_API_KEY")
TOY_TOOL_NAME = "synthetic_measurement_protocol_ping"
PLANNED_PROBES = [
    "synthetic_empty_response_guard",
    "synthetic_tool_call_required_guard",
    "synthetic_openai_response_shape_guard",
]
Transport = Callable[[str, str, dict[str, Any]], tuple[int, dict[str, Any]]]


def _packet_blockers(packet: Path) -> list[str]:
    packet_summary = check_packet(packet)
    return list(packet_summary["blockers"])


def build_plan(packet: Path = PACKET) -> dict:
    blockers = _packet_blockers(packet)
    return {
        "report_scope": "bfcl_measurement_provider_protocol_debug_plan",
        "packet_path": str(packet),
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "openrouter_allowed": False,
        "planned_probes": PLANNED_PROBES,
        "provider_request_executed": False,
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "bfcl_scorer_executed": False,
        "bfcl_smoke_executed": False,
        "bfcl_full_eval_executed": False,
        "source_input_read": False,
        "diagnostic_written": False,
        "raw_provider_payload_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
        "raw_prompt_persisted": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "scorer_feedback_tuning_enabled": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "bfcl_measurement_provider_protocol_debug_plan_passed": not blockers,
        "blockers": blockers,
    }


def _first_present(env: dict[str, str], names: tuple[str, ...]) -> tuple[bool, str | None]:
    for name in names:
        value = env.get(name)
        if value:
            return True, value
    return False, None


def build_synthetic_payload() -> dict[str, Any]:
    return {
        "model": "gpt-4.1",
        "messages": [
            {"role": "system", "content": "Return exactly one tool call for the synthetic protocol check."},
            {"role": "user", "content": "Run the synthetic protocol check."},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": TOY_TOOL_NAME,
                    "description": "Synthetic pre-BFCL protocol check only.",
                    "parameters": {
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                        "required": ["ok"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
        "tool_choice": {"type": "function", "function": {"name": TOY_TOOL_NAME}},
        "temperature": 0,
        "max_tokens": 32,
    }


def default_transport(endpoint: str, api_key: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = int(response.status)
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        body = exc.read().decode("utf-8", errors="replace")
    parsed = json.loads(body) if body else {}
    if not isinstance(parsed, dict):
        parsed = {}
    return status, parsed


def _has_required_tool_call(response: dict[str, Any]) -> bool:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return False
    first = choices[0]
    if not isinstance(first, dict):
        return False
    message = first.get("message")
    if not isinstance(message, dict):
        return False
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        return False
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        function = call.get("function")
        if isinstance(function, dict) and function.get("name") == TOY_TOOL_NAME:
            return True
    return False


def _openai_compatible_shape(response: dict[str, Any]) -> bool:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return False
    first = choices[0]
    if not isinstance(first, dict):
        return False
    return isinstance(first.get("message"), dict)


def execute_debug(
    *,
    packet: Path = PACKET,
    env: dict[str, str] | None = None,
    transport: Transport | None = None,
    output_artifact: Path | None = None,
) -> dict[str, Any]:
    blockers = _packet_blockers(packet)
    if blockers:
        return _execute_summary(False, False, False, 0, False, False, False, False, blockers)
    env = dict(os.environ if env is None else env)
    endpoint_present, endpoint = _first_present(env, ENDPOINT_ENVS)
    key_present, api_key = _first_present(env, KEY_ENVS)
    if not endpoint_present:
        return _execute_summary(True, False, False, 0, False, False, False, False, ["provider_endpoint_missing"])
    if not key_present:
        return _execute_summary(True, True, False, 0, False, False, False, False, ["provider_key_missing"])
    if endpoint is None or not endpoint.startswith("https://"):
        return _execute_summary(True, True, True, 0, False, False, False, False, ["provider_endpoint_not_https"])
    payload = build_synthetic_payload()
    selected_transport = default_transport if transport is None else transport
    try:
        status, response = selected_transport(endpoint, api_key or "", payload)
    except Exception as exc:  # pragma: no cover - real transport failure path.
        return _execute_summary(True, True, True, 0, True, False, False, False, [f"provider_protocol_debug_request_failed:{type(exc).__name__}"])
    http_status_class = int(status // 100) if isinstance(status, int) else 0
    openai_shape = _openai_compatible_shape(response)
    tool_call_present = _has_required_tool_call(response)
    empty_response = not bool(response)
    blockers = []
    if http_status_class != 2:
        blockers.append(f"provider_http_status_class_{http_status_class}")
    if empty_response:
        blockers.append("empty_model_response")
    if not openai_shape:
        blockers.append("non_openai_compatible_response_shape")
    if not tool_call_present:
        blockers.append("missing_required_tool_call")
    summary = _execute_summary(
        True,
        True,
        True,
        http_status_class,
        True,
        openai_shape,
        tool_call_present,
        empty_response,
        blockers,
    )
    if output_artifact is not None and not blockers:
        output_artifact.parent.mkdir(parents=True, exist_ok=True)
        output_artifact.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def _execute_summary(
    endpoint_present: bool,
    endpoint_value_read: bool,
    api_key_value_read: bool,
    http_status_class: int,
    provider_request_executed: bool,
    openai_shape: bool,
    tool_call_present: bool,
    empty_response: bool,
    blockers: list[str],
) -> dict[str, Any]:
    record = {
        "variant": "synthetic_pre_bfcl_protocol_debug",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "http_status_class": http_status_class,
        "auth_ok": http_status_class == 2,
        "model_available": http_status_class == 2,
        "tool_calls_returned": tool_call_present,
        "raw_provider_payload_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
        "raw_prompt_persisted": False,
        "source_input_read": False,
        "diagnostic_written": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "scorer_feedback_tuning_enabled": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "response_contract": {
            "empty_model_response": empty_response,
            "tool_call_required": True,
            "tool_call_present": tool_call_present,
            "openai_compatible_response_shape": openai_shape,
        },
    }
    summary = {
        "artifact_kind": "bfcl_measurement_provider_protocol_debug_compact",
        "provider_request_executed": provider_request_executed,
        "provider_request_count": 1 if provider_request_executed else 0,
        "endpoint_present": endpoint_present,
        "endpoint_value_read": endpoint_value_read,
        "api_key_present": api_key_value_read,
        "api_key_value_read": api_key_value_read,
        "raw_request_persisted": False,
        "raw_response_persisted": False,
        "raw_header_persisted": False,
        "raw_body_persisted": False,
        "records": [record],
        "blockers": blockers,
        "bfcl_measurement_provider_protocol_debug_passed": not blockers,
    }
    artifact_blockers = validate_artifact(summary)
    if artifact_blockers:
        summary["blockers"] = sorted(set(blockers + artifact_blockers))
        summary["bfcl_measurement_provider_protocol_debug_passed"] = False
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute-debug", action="store_true")
    parser.add_argument("--packet", type=Path, default=PACKET)
    parser.add_argument("--output-artifact", type=Path)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_debug:
        summary = execute_debug(packet=args.packet, output_artifact=args.output_artifact)
        passed_key = "bfcl_measurement_provider_protocol_debug_passed"
    else:
        summary = build_plan(args.packet)
        passed_key = "bfcl_measurement_provider_protocol_debug_plan_passed"
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary[passed_key]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
