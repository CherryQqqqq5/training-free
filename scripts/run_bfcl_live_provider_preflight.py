#!/usr/bin/env python3
"""Dry-run or execute a compact-only synthetic live-provider preflight."""

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

from scripts.check_bfcl_live_provider_preflight_artifact import check as check_artifact
from scripts.check_bfcl_live_provider_preflight_gate import (
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    SIGNED_API_KEY_ENVS,
    SIGNED_BASE_URL_ENVS,
    SIGNED_ENDPOINT_ENVS,
    check as check_packet,
)

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_live_provider_preflight_compact.json")
TOY_TOOL_NAME = "synthetic_live_provider_preflight_ping"
PostJson = Callable[..., Any]
STATUS_CLASSIFIER_SCHEMA = "live_provider_preflight_status_classifier_v4"
CAPABILITY_SCHEMA = "live_provider_preflight_chat_tool_shape_v5"


def _first_present_env(env: dict[str, str], names: list[str]) -> tuple[bool, str | None, str]:
    for name in names:
        value = env.get(name)
        if value:
            return True, value, name
    return False, None, "none"


def _transport_target(base_url: str | None, endpoint: str | None, path: str, mode: str) -> tuple[str, str]:
    if mode == "base_url" and base_url is not None:
        return base_url.rstrip("/") + path, "base_url_chat_completions_appended"
    if mode == "full_endpoint" and endpoint is not None:
        return endpoint, "endpoint_used_as_is"
    return "", "not_reached"


def _http_status_class(status: int | None) -> str:
    if status is None:
        return "transport_error"
    if 200 <= status <= 299:
        return "2xx"
    if 300 <= status <= 399:
        return "3xx"
    if 400 <= status <= 499:
        return "4xx"
    if 500 <= status <= 599:
        return "5xx"
    return "unknown"


def _provider_http_status_label(status: int | None) -> str:
    if status is None:
        return "transport_error"
    if status in {400, 401, 403, 404, 405, 415, 422, 429}:
        return f"status_{status}"
    if 400 <= status <= 499:
        return "other_4xx"
    if 500 <= status <= 599:
        return "status_5xx"
    return "unknown"


def _exit_code_class(blockers: list[str]) -> str:
    return "zero" if not blockers else "nonzero_1"


def _chat_tool_payload() -> dict[str, Any]:
    return {
        "model": "gpt-4.1",
        "messages": [{"role": "user", "content": "Call the synthetic preflight tool with ok=true."}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": TOY_TOOL_NAME,
                    "description": "Synthetic live-provider preflight tool carrying no BFCL/source data.",
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
        "max_tokens": 16,
    }


def _responses_tool_payload() -> dict[str, Any]:
    return {
        "model": "gpt-4.1",
        "input": [{"role": "user", "content": "Call the synthetic preflight tool with ok=true."}],
        "tools": [
            {
                "type": "function",
                "name": TOY_TOOL_NAME,
                "description": "Synthetic live-provider preflight tool carrying no BFCL/source data.",
                "parameters": {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                    "additionalProperties": False,
                },
            }
        ],
        "tool_choice": {"type": "function", "name": TOY_TOOL_NAME},
        "temperature": 0,
        "max_tokens": 16,
    }


def _chat_text_payload() -> dict[str, Any]:
    return {"model": "gpt-4.1", "messages": [{"role": "user", "content": "Reply with the single word PONG."}], "temperature": 0, "max_tokens": 8}


def _default_post_json(target_url: str, api_key: str, payload: dict[str, Any]) -> tuple[Any, Any, str]:
    request = urllib.request.Request(
        target_url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = int(response.status)
            body = response.read()
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        body = exc.read()
    except Exception:
        return None, {}, "not_read"
    if not body:
        return status, {}, "empty_body"
    try:
        return status, json.loads(body.decode("utf-8")), "parsed_json"
    except (UnicodeDecodeError, json.JSONDecodeError):
        return status, {}, "invalid_json"



def _normalize_post_result(result: Any) -> tuple[Any, Any, str]:
    if isinstance(result, tuple) and len(result) == 3:
        return result[0], result[1], str(result[2])
    if isinstance(result, tuple) and len(result) == 2:
        return result[0], result[1], "parsed_json" if isinstance(result[1], dict) else "invalid_json"
    return None, {}, "not_read"


def _content_text_present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_content_text_present(item) for item in value)
    if isinstance(value, dict):
        for key in ("text", "content", "input_text", "output_text"):
            if _content_text_present(value.get(key)):
                return True
    return False


def _chat_message(payload: Any) -> tuple[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return "malformed", {}
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return "no_choices", {}
    first = choices[0]
    if not isinstance(first, dict):
        return "choices_no_message", {}
    message = first.get("message")
    if not isinstance(message, dict):
        return "choices_no_message", {}
    return "choices_message", message


def _message_has_tool_call(message: dict[str, Any]) -> bool:
    calls = message.get("tool_calls")
    if not isinstance(calls, list):
        return False
    for call in calls:
        function = call.get("function") if isinstance(call, dict) and isinstance(call.get("function"), dict) else {}
        if function.get("name") == TOY_TOOL_NAME:
            return True
    return False

def _chat_has_tool_call(payload: dict[str, Any]) -> bool:
    choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        calls = message.get("tool_calls")
        if not isinstance(calls, list):
            continue
        for call in calls:
            function = call.get("function") if isinstance(call, dict) and isinstance(call.get("function"), dict) else {}
            if function.get("name") == TOY_TOOL_NAME:
                return True
    return False


def _responses_has_tool_call(payload: dict[str, Any]) -> bool:
    output = payload.get("output") if isinstance(payload.get("output"), list) else []
    for item in output:
        if isinstance(item, dict) and item.get("type") == "function_call" and item.get("name") == TOY_TOOL_NAME:
            return True
    return False


def _chat_has_pong(payload: dict[str, Any]) -> bool:
    choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        content = message.get("content")
        if isinstance(content, str) and "pong" in content.lower():
            return True
    return False


def _base_record(*, command_executed: bool = False) -> dict[str, Any]:
    return {
        "preflight_command_executed": command_executed,
        "provider_request_executed": False,
        "provider_call_started": False,
        "endpoint_env_present": False,
        "base_url_env_present": False,
        "api_key_env_present": False,
        "https_endpoint_valid": False,
        "endpoint_mode_label": "not_selected",
        "selected_endpoint_env_label": "none",
        "transport_path_join_label": "not_reached",
        "http_status_class": "not_observed",
        "provider_http_status_label": "not_observed",
        "capability_probe_kind": "chat_tool_call_shape",
        "status_classifier_only": False,
        "response_body_read": False,
        "response_body_persisted": False,
        "response_json_parse_label": "not_read",
        "openai_chat_shape_label": "not_checked",
        "tool_call_present": False,
        "text_present": False,
        "auth_status_label": "not_checked",
        "model_route_label": "not_checked",
        "chat_tool_call_label": "not_checked",
        "responses_tool_call_label": "not_checked",
        "chat_text_response_label": "not_checked",
        "trace_emission_label": "not_persisted_compact_only",
        "preflight_exact_exit_code_class": "not_executed" if not command_executed else "zero",
        "preflight_failed_check_label": "none_observed",
        "bfcl_generate_started": False,
        "bfcl_evaluate_started": False,
        "scorer_started": False,
        "full_baseline_executed": False,
        "candidate_specs_inert": True,
        "performance_evidence": False,
        "raw_outputs_removed": True,
        "raw_outputs_committed": False,
        "stop_gate_triggered": "none",
        "suspected_live_preflight_failure_stage": "not_executed" if not command_executed else "pending",
    }


def _set_failure(record: dict[str, Any], label: str, stage: str) -> None:
    record["preflight_failed_check_label"] = label
    record["stop_gate_triggered"] = label
    record["suspected_live_preflight_failure_stage"] = stage


def _write_artifact(record: dict[str, Any], output_artifact: Path) -> None:
    payload = {
        "artifact_kind": "bfcl_live_provider_preflight_compact",
        "compact_schema_version": CAPABILITY_SCHEMA,
        "measurement_kind": "compact_synthetic_live_provider_preflight",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "bfcl_generate_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "source_collection_executed": False,
        "source_diagnostics_executed": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "raw_outputs_committed": False,
        "records": [{field: record.get(field) for field in REQUIRED_COMPACT_FIELDS}],
    }
    output_artifact.parent.mkdir(parents=True, exist_ok=True)
    output_artifact.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _blocked_summary(blockers: list[str]) -> dict[str, Any]:
    record = _base_record(command_executed=False)
    return {
        "report_scope": "bfcl_live_provider_preflight_execute",
        **record,
        "env_profile_sourced": False,
        "bfcl_generate_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed_summary": False,
        "source_collection_executed": False,
        "source_diagnostics_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "huawei_acceptance_ready": False,
        "blockers": sorted(set(blockers)),
    }


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    record = _base_record(command_executed=False)
    return {
        "report_scope": "bfcl_live_provider_preflight_plan",
        "packet_path": str(packet_path),
        "output_artifact_planned": str(output_artifact),
        "approval_status": packet_summary.get("approval_status"),
        "authorized": packet_summary.get("authorized"),
        "live_provider_preflight_authorized": packet_summary.get("live_provider_preflight_authorized"),
        "provider_request_authorized": packet_summary.get("provider_request_authorized"),
        "planned_attempt_count": 1,
        "compact_only": True,
        "synthetic_probe_only": True,
        "env_profile_sourced": False,
        "compact_fields": list(REQUIRED_COMPACT_FIELDS),
        **record,
        "bfcl_generate_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed_summary": False,
        "source_collection_executed": False,
        "source_diagnostics_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "huawei_acceptance_ready": False,
        "blockers": list(packet_summary.get("blockers", [])),
    }


def execute_live_provider_preflight(
    packet_path: Path = DEFAULT_PACKET,
    output_artifact: Path = DEFAULT_OUTPUT,
    *,
    environ: dict[str, str] | None = None,
    post_json: PostJson | None = None,
) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_live_provider_preflight_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("live_provider_preflight_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    if blockers:
        return _blocked_summary(blockers)

    env = dict(os.environ if environ is None else environ)
    record = _base_record(command_executed=True)
    base_url_present, base_url, base_url_label = _first_present_env(env, SIGNED_BASE_URL_ENVS)
    endpoint_present, endpoint, endpoint_label = _first_present_env(env, SIGNED_ENDPOINT_ENVS)
    key_present, api_key, _api_key_label = _first_present_env(env, SIGNED_API_KEY_ENVS)
    record["endpoint_env_present"] = endpoint_present
    record["base_url_env_present"] = base_url_present
    record["api_key_env_present"] = key_present
    blockers = []

    selected_target = base_url if base_url_present else endpoint
    selected_label = base_url_label if base_url_present else endpoint_label
    endpoint_mode = "base_url" if base_url_present else "full_endpoint" if endpoint_present else "not_selected"
    record["endpoint_mode_label"] = endpoint_mode
    record["selected_endpoint_env_label"] = selected_label

    if not (base_url_present or endpoint_present):
        _set_failure(record, "missing_endpoint_env", "endpoint_env_missing")
        blockers.append("missing_endpoint_env")
    elif selected_target is None or not selected_target.startswith("https://"):
        _set_failure(record, "endpoint_not_https", "endpoint_not_https")
        blockers.append("endpoint_not_https")
    elif not key_present:
        _set_failure(record, "missing_api_key_env", "api_key_env_missing")
        blockers.append("missing_api_key_env")
    else:
        record["https_endpoint_valid"] = True
        selected_post_json = _default_post_json if post_json is None else post_json
        try:
            record["provider_call_started"] = True
            target_url, join_label = _transport_target(base_url, endpoint, "/chat/completions", endpoint_mode)
            record["transport_path_join_label"] = join_label
            status, response, parse_label = _normalize_post_result(selected_post_json(target_url, api_key or "", _chat_tool_payload()))
            record["provider_request_executed"] = True
            record["response_body_read"] = True
            record["response_json_parse_label"] = parse_label
        except Exception:
            record["http_status_class"] = "transport_error"
            record["provider_http_status_label"] = "transport_error"
            _set_failure(record, "provider_transport_error", "provider_transport_error")
            blockers.append("provider_transport_error")
        else:
            status_class = _http_status_class(status)
            record["http_status_class"] = status_class
            record["provider_http_status_label"] = _provider_http_status_label(status)
            if status in {401, 403}:
                record["auth_status_label"] = "auth_failed"
                _set_failure(record, "provider_auth_failed", "provider_auth_failed")
                blockers.append("provider_auth_failed")
            elif status_class != "2xx":
                record["auth_status_label"] = "unknown"
                record["chat_tool_call_label"] = "non_2xx"
                _set_failure(record, "provider_non_2xx", "provider_non_2xx")
                blockers.append("provider_non_2xx")
            else:
                record["auth_status_label"] = "ok"
                record["model_route_label"] = "available"
                shape_label, message = _chat_message(response)
                record["openai_chat_shape_label"] = shape_label
                record["tool_call_present"] = _message_has_tool_call(message)
                record["text_present"] = _content_text_present(message.get("content"))
                if shape_label != "choices_message":
                    record["chat_tool_call_label"] = "malformed"
                    _set_failure(record, "chat_tool_call", "chat_tool_call_shape_malformed")
                    blockers.append("chat_tool_call")
                elif record["tool_call_present"]:
                    record["chat_tool_call_label"] = "passed"
                else:
                    record["chat_tool_call_label"] = "missing_tool_call"
                    _set_failure(record, "chat_tool_call", "chat_tool_call_missing_tool_call")
                    blockers.append("chat_tool_call")

    if not blockers:
        record["preflight_failed_check_label"] = "none_observed"
        record["stop_gate_triggered"] = "stopped_after_live_provider_preflight"
        record["suspected_live_preflight_failure_stage"] = "chat_tool_call_shape_classified_without_raw_persistence"
    record["preflight_exact_exit_code_class"] = _exit_code_class(blockers)
    _write_artifact(record, output_artifact)
    artifact_summary = check_artifact(output_artifact)
    if not artifact_summary.get("bfcl_live_provider_preflight_artifact_passed"):
        blockers.extend(str(blocker) for blocker in artifact_summary.get("blockers", []))
    return {
        "report_scope": "bfcl_live_provider_preflight_execute",
        **record,
        "env_profile_sourced": False,
        "bfcl_generate_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed_summary": False,
        "source_collection_executed": False,
        "source_diagnostics_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "huawei_acceptance_ready": False,
        "output_artifact": str(output_artifact),
        "blockers": sorted(set(blockers)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute-live-provider-preflight", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_live_provider_preflight:
        summary = execute_live_provider_preflight(args.packet, args.output_artifact)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
