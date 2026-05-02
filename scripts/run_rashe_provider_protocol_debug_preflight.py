#!/usr/bin/env python3
"""Plan or execute RASHE provider protocol debug preflight variants."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_rashe_provider_protocol_debug_preflight_packet import DEFAULT_PACKET, SIGNED_VARIANTS

SIGNED_ENDPOINT_ENV_VARS = ("CHUANGZHI_NOVACODE_ENDPOINT", "NOVACODE_ENDPOINT")
SIGNED_KEY_ENV_VARS = ("CHUANGZHI_API_KEY", "NOVACODE_API_KEY")
SIGNED_MODEL = "gpt-4.1"
PostJson = Callable[[dict[str, Any]], dict[str, Any]]
Opener = Callable[[urllib.request.Request, float], Any]


class ProtocolDebugTransportError(RuntimeError):
    def __init__(
        self,
        blocker: str,
        *,
        error_class: str | None = None,
        endpoint_value_read: bool = False,
        api_key_value_read: bool = False,
        provider_request_executed: bool = False,
    ) -> None:
        super().__init__(blocker)
        self.blocker = blocker
        self.error_class = error_class or blocker
        self.endpoint_value_read = endpoint_value_read
        self.api_key_value_read = api_key_value_read
        self.provider_request_executed = provider_request_executed


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
    error_class: str | None = None,
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
        "error_class": error_class,
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
    payload: dict[str, Any] = {"model": SIGNED_MODEL, "messages": base_messages, "tools": [tool], "temperature": 0}
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


def _first_present_env(env: Mapping[str, str], names: tuple[str, ...]) -> tuple[str | None, bool]:
    for name in names:
        value = env.get(name)
        if value:
            return value, True
    return None, False


def _default_opener(request: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.urlopen(request, timeout=timeout)


def build_env_post_json(env: Mapping[str, str] | None = None, opener: Opener | None = None, timeout: float = 15.0) -> PostJson:
    env_map = os.environ if env is None else env
    transport = _default_opener if opener is None else opener

    def post_json(payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("model") != SIGNED_MODEL:
            raise ProtocolDebugTransportError("unsigned_model", error_class="unsigned_model")
        endpoint, endpoint_read = _first_present_env(env_map, SIGNED_ENDPOINT_ENV_VARS)
        if not endpoint:
            raise ProtocolDebugTransportError("provider_endpoint_missing", error_class="provider_endpoint_missing")
        if not endpoint.startswith("https://"):
            raise ProtocolDebugTransportError("provider_endpoint_not_https", error_class="provider_endpoint_not_https", endpoint_value_read=True)
        key, key_read = _first_present_env(env_map, SIGNED_KEY_ENV_VARS)
        if not key:
            raise ProtocolDebugTransportError("provider_key_missing", error_class="provider_key_missing", endpoint_value_read=endpoint_read)

        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            response = transport(request, timeout)
            try:
                status = getattr(response, "status", None) or response.getcode()
                response_body = response.read()
            finally:
                close = getattr(response, "close", None)
                if callable(close):
                    close()
        except urllib.error.HTTPError as exc:
            return {
                "status": exc.code,
                "json": {},
                "endpoint_value_read": endpoint_read,
                "api_key_value_read": key_read,
                "provider_request_executed": True,
            }
        except urllib.error.URLError as exc:
            raise ProtocolDebugTransportError(
                "provider_protocol_debug_request_failed",
                error_class=type(exc.reason).__name__ if getattr(exc, "reason", None) is not None else type(exc).__name__,
                endpoint_value_read=endpoint_read,
                api_key_value_read=key_read,
                provider_request_executed=False,
            ) from exc
        try:
            parsed = json.loads(response_body.decode("utf-8")) if response_body else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = {}
        return {
            "status": status,
            "json": parsed if isinstance(parsed, dict) else {},
            "endpoint_value_read": endpoint_read,
            "api_key_value_read": key_read,
            "provider_request_executed": True,
        }

    return post_json


def default_post_json(payload: dict[str, Any]) -> dict[str, Any]:
    return build_env_post_json()(payload)


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


def execute_debug(post_json: PostJson = default_post_json) -> tuple[list[dict[str, Any]], list[str], bool, bool]:
    results: list[dict[str, Any]] = []
    blockers: list[str] = []
    endpoint_value_read = False
    api_key_value_read = False
    for variant in SIGNED_VARIANTS:
        try:
            response = post_json(payload_for_variant(variant))
        except ProtocolDebugTransportError as exc:
            endpoint_value_read = endpoint_value_read or exc.endpoint_value_read
            api_key_value_read = api_key_value_read or exc.api_key_value_read
            result = compact_result(
                variant,
                provider_request_executed=exc.provider_request_executed,
                status_class=None,
                blocker=exc.blocker,
                error_class=exc.error_class,
            )
            results.append(result)
            blockers.append(result["blocker"])
            continue
        except Exception as exc:
            result = compact_result(
                variant,
                provider_request_executed=False,
                status_class=None,
                blocker="provider_protocol_debug_request_failed",
                error_class=type(exc).__name__,
            )
            results.append(result)
            blockers.append(result["blocker"])
            continue
        endpoint_value_read = endpoint_value_read or bool(response.get("endpoint_value_read"))
        api_key_value_read = api_key_value_read or bool(response.get("api_key_value_read"))
        provider_request_executed = bool(response.get("provider_request_executed", True))
        cls = status_class(response.get("status"))
        tool_calls = has_tool_calls(response)
        blocker = None
        error_class = None
        if cls in {"401", "403"}:
            blocker = "provider_auth_failed"
            error_class = cls
        elif cls != "2xx":
            blocker = f"provider_http_status_{cls or 'unknown'}"
            error_class = cls or "unknown"
        elif not tool_calls:
            blocker = "tool_calls_not_returned"
            error_class = "tools_not_supported"
        if blocker:
            blockers.append(f"{variant}:{blocker}")
        results.append(
            compact_result(
                variant,
                planned_only=False,
                provider_request_executed=provider_request_executed,
                status_class=cls,
                blocker=blocker,
                error_class=error_class,
                tool_calls_returned=tool_calls,
            )
        )
    return results, blockers, endpoint_value_read, api_key_value_read


def build_plan(args: argparse.Namespace, post_json: PostJson = default_post_json) -> dict[str, Any]:
    blockers: list[str] = []
    endpoint_value_read = False
    api_key_value_read = False
    packet_ok, packet_error = run_packet_checker(args.packet)
    if not packet_ok:
        blockers.append(f"packet_check_failed:{packet_error}")
    if args.execute_debug:
        variants, execution_blockers, endpoint_value_read, api_key_value_read = execute_debug(post_json)
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
        "signed_model": SIGNED_MODEL,
        "fallback_allowed": False,
        "provider_request_executed": any(variant["provider_request_executed"] for variant in variants),
        "endpoint_value_read": endpoint_value_read,
        "api_key_value_read": api_key_value_read,
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
