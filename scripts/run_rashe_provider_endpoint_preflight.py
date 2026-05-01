#!/usr/bin/env python3
"""Plan or execute the RASHE provider endpoint/model/tool-calling preflight."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_rashe_provider_endpoint_preflight_packet import (
    DEFAULT_PACKET,
    OPTIONAL_MODEL,
    PRIMARY_MODEL,
    SIGNED_ENDPOINT_ENVS,
    SIGNED_KEY_ENVS,
    TOY_TOOL_NAME,
)

PROBE_FIELDS = [
    "endpoint_present",
    "key_present",
    "https_valid",
    "auth_ok",
    "model_gpt_5_2_available",
    "optional_model_gpt_5_4_observed",
    "tool_calling_supported",
    "tool_choice_supported",
    "tool_calls_returned",
    "raw_payload_persisted",
    "raw_prompt_persisted",
    "candidate_generation_authorized",
    "scorer_authorized",
    "performance_evidence",
    "blocker",
]
PostJson = Callable[[str, str, dict[str, Any]], dict[str, Any]]


def run_packet_checker(packet: Path) -> tuple[bool, str | None]:
    result = subprocess.run(
        [sys.executable, "scripts/check_rashe_provider_endpoint_preflight_packet.py", "--packet", str(packet), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, result.stdout.strip() or result.stderr.strip() or "provider_endpoint_preflight_packet_failed"
    return True, None


def present_by_name(environ: dict[str, str], names: list[str]) -> bool:
    env_names = set(environ)
    return any(name in env_names for name in names)


def signed_env_value(environ: dict[str, str], names: list[str]) -> tuple[bool, str | None]:
    for name in names:
        value = environ.get(name)
        if value:
            return True, value
    return False, None


def base_observation(endpoint_present: bool, key_present: bool) -> dict[str, Any]:
    return {
        "endpoint_present": endpoint_present,
        "key_present": key_present,
        "https_valid": False,
        "auth_ok": False,
        "model_gpt_5_2_available": False,
        "optional_model_gpt_5_4_observed": False,
        "tool_calling_supported": False,
        "tool_choice_supported": False,
        "tool_calls_returned": False,
        "raw_payload_persisted": False,
        "raw_prompt_persisted": False,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "blocker": None,
    }


def compact_summary(args: argparse.Namespace, observation: dict[str, Any], blockers: list[str], *, provider_request_executed: bool, endpoint_value_read: bool, api_key_value_read: bool) -> dict[str, Any]:
    return {
        "report_scope": "rashe_provider_endpoint_preflight_plan",
        "packet_path": str(args.packet),
        "rashe_provider_endpoint_preflight_plan_passed": not blockers,
        "dry_run": args.dry_run,
        "plan_only": args.plan_only,
        "execute_preflight": args.execute_preflight,
        "provider_request_executed": provider_request_executed,
        "api_key_value_read": api_key_value_read,
        "endpoint_value_read": endpoint_value_read,
        "diagnostic_written": False,
        "phase_b_execution_authorized": False,
        "signed_primary_model": PRIMARY_MODEL,
        "optional_capability_observation_model": OPTIONAL_MODEL,
        "route_update_required": "route_update_required" in blockers,
        "openai_compatible_chat_adapter_review_required_if_standard_chat_only": True,
        **observation,
        "planned_probe_fields": PROBE_FIELDS,
        "blockers": blockers,
    }


def toy_chat_payload(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": "synthetic endpoint preflight only"},
            {"role": "user", "content": "return ok"},
        ],
        "max_tokens": 8,
        "temperature": 0,
    }


def toy_tool_payload(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": "call the synthetic preflight tool"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": TOY_TOOL_NAME,
                    "description": "Synthetic provider preflight tool; carries no BFCL/source data.",
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
        "max_tokens": 8,
        "temperature": 0,
    }


def default_post_json(endpoint: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = int(response.status)
            data = response.read()
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": int(exc.code)}
    except Exception:
        return {"ok": False, "status": None, "blocker": "provider_preflight_transport_failed"}
    if status < 200 or status >= 300:
        return {"ok": False, "status": status}
    try:
        parsed = json.loads(data.decode("utf-8")) if data else {}
    except json.JSONDecodeError:
        return {"ok": False, "status": status, "blocker": "provider_preflight_response_not_json"}
    return {"ok": True, "status": status, "json": parsed}


def response_auth_failed(response: dict[str, Any]) -> bool:
    return response.get("status") in {401, 403}


def model_available(response: dict[str, Any]) -> bool:
    return response.get("ok") is True


def tool_calls_returned(response: dict[str, Any]) -> bool:
    data = response.get("json") if isinstance(response.get("json"), dict) else {}
    choices = data.get("choices") if isinstance(data.get("choices"), list) else []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        calls = message.get("tool_calls")
        if isinstance(calls, list) and calls:
            return True
    return False


def execute_preflight(args: argparse.Namespace, environ: dict[str, str], post_json: PostJson = default_post_json) -> dict[str, Any]:
    blockers: list[str] = []
    packet_ok, packet_error = run_packet_checker(args.packet)
    if not packet_ok:
        blockers.append(f"packet_check_failed:{packet_error}")
    endpoint_present, endpoint = signed_env_value(environ, SIGNED_ENDPOINT_ENVS)
    key_present, key = signed_env_value(environ, SIGNED_KEY_ENVS)
    observation = base_observation(endpoint_present, key_present)
    endpoint_value_read = endpoint_present
    api_key_value_read = False
    if not endpoint_present:
        blockers.append("provider_endpoint_missing")
        observation["blocker"] = "provider_endpoint_missing"
        return compact_summary(args, observation, blockers, provider_request_executed=False, endpoint_value_read=False, api_key_value_read=False)
    if not str(endpoint).startswith("https://"):
        blockers.append("provider_endpoint_not_https")
        observation["blocker"] = "provider_endpoint_not_https"
        return compact_summary(args, observation, blockers, provider_request_executed=False, endpoint_value_read=endpoint_value_read, api_key_value_read=False)
    observation["https_valid"] = True
    if not key_present:
        blockers.append("provider_key_missing")
        observation["blocker"] = "provider_key_missing"
        return compact_summary(args, observation, blockers, provider_request_executed=False, endpoint_value_read=endpoint_value_read, api_key_value_read=False)
    api_key_value_read = True

    primary_response = post_json(str(endpoint), str(key), toy_chat_payload(PRIMARY_MODEL))
    provider_request_executed = True
    if response_auth_failed(primary_response):
        blockers.append("provider_auth_failed")
        observation["blocker"] = "provider_auth_failed"
        return compact_summary(args, observation, blockers, provider_request_executed=provider_request_executed, endpoint_value_read=endpoint_value_read, api_key_value_read=api_key_value_read)
    if model_available(primary_response):
        observation["auth_ok"] = True
        observation["model_gpt_5_2_available"] = True
        tool_response = post_json(str(endpoint), str(key), toy_tool_payload(PRIMARY_MODEL))
        if response_auth_failed(tool_response):
            blockers.append("provider_auth_failed")
            observation["blocker"] = "provider_auth_failed"
        elif not model_available(tool_response) or not tool_calls_returned(tool_response):
            blockers.append("tools_not_supported")
            observation["blocker"] = "tools_not_supported"
        else:
            observation["tool_calling_supported"] = True
            observation["tool_choice_supported"] = True
            observation["tool_calls_returned"] = True
        return compact_summary(args, observation, blockers, provider_request_executed=provider_request_executed, endpoint_value_read=endpoint_value_read, api_key_value_read=api_key_value_read)

    optional_response = post_json(str(endpoint), str(key), toy_chat_payload(OPTIONAL_MODEL))
    if response_auth_failed(optional_response):
        blockers.append("provider_auth_failed")
        observation["blocker"] = "provider_auth_failed"
    elif model_available(optional_response):
        observation["auth_ok"] = True
        observation["optional_model_gpt_5_4_observed"] = True
        blockers.append("route_update_required")
        observation["blocker"] = "route_update_required"
    else:
        blockers.append("model_gpt_5_2_unavailable")
        observation["blocker"] = "model_gpt_5_2_unavailable"
    return compact_summary(args, observation, blockers, provider_request_executed=provider_request_executed, endpoint_value_read=endpoint_value_read, api_key_value_read=api_key_value_read)


def build_plan(args: argparse.Namespace, environ: dict[str, str] | None = None, post_json: PostJson = default_post_json) -> dict[str, Any]:
    environ = dict(os.environ if environ is None else environ)
    if args.execute_preflight:
        return execute_preflight(args, environ, post_json)

    blockers: list[str] = []
    packet_ok, packet_error = run_packet_checker(args.packet)
    if not packet_ok:
        blockers.append(f"packet_check_failed:{packet_error}")
    if not (args.dry_run or args.plan_only):
        blockers.append("dry_run_or_plan_only_required")
    endpoint_present = present_by_name(environ, SIGNED_ENDPOINT_ENVS)
    key_present = present_by_name(environ, SIGNED_KEY_ENVS)
    observation = base_observation(endpoint_present, key_present)
    return compact_summary(args, observation, blockers, provider_request_executed=False, endpoint_value_read=False, api_key_value_read=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute-preflight", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = build_plan(args)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_provider_endpoint_preflight_plan_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
