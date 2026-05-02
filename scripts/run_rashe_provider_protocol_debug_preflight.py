#!/usr/bin/env python3
"""Plan or execute RASHE provider protocol debug preflight variants."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_rashe_provider_protocol_debug_preflight_packet import DEFAULT_PACKET, SIGNED_VARIANTS

PostJson = Callable[[dict[str, Any]], dict[str, Any]]


def run_packet_checker(packet: Path) -> tuple[bool, str | None]:
    result = subprocess.run(
        [sys.executable, "scripts/check_rashe_provider_protocol_debug_preflight_packet.py", "--packet", str(packet), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, result.stdout.strip() or result.stderr.strip() or "provider_protocol_debug_preflight_packet_failed"
    return True, None


def variant_plan() -> list[dict[str, Any]]:
    return [compact_result(variant, planned_only=True) for variant in SIGNED_VARIANTS]


def compact_result(
    variant: str,
    *,
    planned_only: bool = False,
    provider_request_executed: bool | None = None,
    status_class: str | None = None,
    blocker: str | None = None,
    tool_calls_returned: bool = False,
) -> dict[str, Any]:
    ok_status = status_class == "2xx"
    return {
        "variant": variant,
        "planned_only": planned_only,
        "provider_request_executed": (not planned_only) if provider_request_executed is None else provider_request_executed,
        "http_status_class": status_class,
        "auth_ok": False if status_class in {"401", "403", "4xx_auth"} else ok_status,
        "model_available": ok_status,
        "tool_calls_returned": tool_calls_returned,
        "raw_request_persisted": False,
        "raw_response_persisted": False,
        "raw_headers_persisted": False,
        "raw_body_persisted": False,
        "source_input_read": False,
        "diagnostic_written": False,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "blocker": blocker,
    }


def payload_for_variant(variant: str) -> dict[str, Any]:
    base_messages = [{"role": "user", "content": "synthetic protocol debug"}]
    tool = {
        "type": "function",
        "function": {
            "name": "synthetic_preflight_ping",
            "description": "Synthetic protocol debug tool carrying no source data.",
            "parameters": {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            },
        },
    }
    payload: dict[str, Any] = {"model": "gpt-4.1", "messages": base_messages, "tools": [tool], "temperature": 0}
    if variant == "baseline_chat_tools_required":
        payload["tool_choice"] = {"type": "function", "function": {"name": "synthetic_preflight_ping"}}
        payload["max_tokens"] = 16
    elif variant == "chat_tools_auto":
        payload["tool_choice"] = "auto"
        payload["max_tokens"] = 16
    elif variant == "chat_tools_required_no_strict":
        payload["tool_choice"] = {"type": "function", "function": {"name": "synthetic_preflight_ping"}}
        payload["max_tokens"] = 16
        payload["tools"][0]["function"]["parameters"].pop("additionalProperties", None)
    elif variant == "chat_tools_max_completion_tokens":
        payload["tool_choice"] = {"type": "function", "function": {"name": "synthetic_preflight_ping"}}
        payload["max_completion_tokens"] = 16
    elif variant == "chat_tools_minimal_messages":
        payload["tool_choice"] = {"type": "function", "function": {"name": "synthetic_preflight_ping"}}
        payload["messages"] = [{"role": "user", "content": "ping"}]
        payload["max_tokens"] = 16
    else:  # pragma: no cover - variants are checker constrained.
        raise ValueError(f"unsigned_variant:{variant}")
    return payload


def default_post_json(payload: dict[str, Any]) -> dict[str, Any]:
    raise RuntimeError("protocol_debug_transport_not_configured")


def status_class(status: int | None) -> str | None:
    if status is None:
        return None
    if 200 <= status <= 299:
        return "2xx"
    if status == 401:
        return "401"
    if status == 403:
        return "403"
    if 400 <= status <= 499:
        return "4xx"
    if 500 <= status <= 599:
        return "5xx"
    return "other"


def has_tool_calls(response: dict[str, Any]) -> bool:
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


def execute_debug(post_json: PostJson = default_post_json) -> tuple[list[dict[str, Any]], list[str]]:
    results: list[dict[str, Any]] = []
    blockers: list[str] = []
    for variant in SIGNED_VARIANTS:
        try:
            response = post_json(payload_for_variant(variant))
        except Exception as exc:
            result = compact_result(
                variant,
                provider_request_executed=False,
                status_class=None,
                blocker=f"provider_protocol_debug_request_failed:{type(exc).__name__}",
            )
            results.append(result)
            blockers.append(result["blocker"])
            continue
        cls = status_class(response.get("status"))
        tool_calls = has_tool_calls(response)
        blocker = None
        if cls in {"401", "403"}:
            blocker = "provider_auth_failed"
        elif cls != "2xx":
            blocker = f"provider_http_status_{cls or 'unknown'}"
        elif not tool_calls:
            blocker = "tool_calls_not_returned"
        if blocker:
            blockers.append(f"{variant}:{blocker}")
        results.append(compact_result(variant, planned_only=False, status_class=cls, blocker=blocker, tool_calls_returned=tool_calls))
    return results, blockers


def build_plan(args: argparse.Namespace, post_json: PostJson = default_post_json) -> dict[str, Any]:
    blockers: list[str] = []
    packet_ok, packet_error = run_packet_checker(args.packet)
    if not packet_ok:
        blockers.append(f"packet_check_failed:{packet_error}")
    if args.execute_debug:
        variants, execution_blockers = execute_debug(post_json)
        blockers.extend(execution_blockers)
    else:
        variants = variant_plan()
        if not (args.dry_run or args.plan_only):
            blockers.append("dry_run_or_plan_only_required")
    return {
        "report_scope": "rashe_provider_protocol_debug_preflight_plan",
        "packet_path": str(args.packet),
        "rashe_provider_protocol_debug_preflight_plan_passed": not blockers,
        "dry_run": args.dry_run,
        "plan_only": args.plan_only,
        "execute_debug": args.execute_debug,
        "signed_model": "gpt-4.1",
        "fallback_allowed": False,
        "provider_request_executed": any(variant["provider_request_executed"] for variant in variants),
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "source_input_read": False,
        "diagnostic_written": False,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "variants": variants,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute-debug", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = build_plan(args)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_provider_protocol_debug_preflight_plan_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
