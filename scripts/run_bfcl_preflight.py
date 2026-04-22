#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml


def _responses_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or item.get("input_text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        text = content.get("text") or content.get("content") or content.get("input_text")
        if isinstance(text, str):
            return text
    return ""


def _load_runtime_config(config_path: str) -> dict[str, Any]:
    payload = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _resolve_expected_api_key_env(config_path: str) -> str:
    cfg = _load_runtime_config(config_path)
    upstream = dict(cfg.get("upstream") or {})
    profiles = upstream.get("profiles") if isinstance(upstream.get("profiles"), dict) else {}
    profile_name = os.environ.get("GRC_UPSTREAM_PROFILE") or upstream.get("active_profile") or ""
    resolved = dict(upstream)
    if profile_name and profile_name in profiles:
        resolved.update(profiles[profile_name] or {})
    api_key_env = os.environ.get("GRC_UPSTREAM_API_KEY_ENV") or resolved.get("api_key_env") or ""
    return str(api_key_env)


def _post_json(base_url: str, path: str, payload: dict[str, Any]) -> tuple[int, Any]:
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("OPENAI_API_KEY") or "dummy"
    headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.getcode(), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except Exception:
            payload = {"raw_body": body}
        return exc.code, payload


def _chat_message_from_response(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return {}
    choice = choices[0]
    if not isinstance(choice, dict):
        return {}
    message = choice.get("message")
    return message if isinstance(message, dict) else {}


def validate_chat_tool_response(payload: dict[str, Any]) -> tuple[bool, str]:
    message = _chat_message_from_response(payload)
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        return False, "chat tool smoke did not return tool_calls"
    first = tool_calls[0] if isinstance(tool_calls[0], dict) else {}
    function = first.get("function") if isinstance(first.get("function"), dict) else {}
    if function.get("name") != "echo":
        return False, f"chat tool smoke returned unexpected tool name: {function.get('name')!r}"
    arguments = function.get("arguments")
    try:
        decoded_args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except Exception:
        return False, "chat tool smoke returned non-JSON function arguments"
    if not isinstance(decoded_args, dict) or decoded_args.get("text") != "ping":
        return False, f"chat tool smoke returned unexpected arguments: {decoded_args!r}"
    return True, "ok"


def validate_responses_tool_response(payload: dict[str, Any]) -> tuple[bool, str]:
    output = payload.get("output")
    if not isinstance(output, list) or not output:
        return False, "responses smoke returned no output items"
    function_calls = [item for item in output if isinstance(item, dict) and item.get("type") == "function_call"]
    if not function_calls:
        return False, "responses smoke returned no function_call item"
    first = function_calls[0]
    if first.get("name") != "echo":
        return False, f"responses smoke returned unexpected function name: {first.get('name')!r}"
    arguments = first.get("arguments")
    try:
        decoded_args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except Exception:
        return False, "responses smoke returned non-JSON function arguments"
    if not isinstance(decoded_args, dict) or decoded_args.get("text") != "ping":
        return False, f"responses smoke returned unexpected arguments: {decoded_args!r}"
    return True, "ok"


def validate_chat_text_response(payload: dict[str, Any]) -> tuple[bool, str]:
    message = _chat_message_from_response(payload)
    text = _responses_content_to_text(message.get("content", ""))
    if not text.strip():
        return False, "text smoke returned empty assistant content"
    if "pong" not in text.lower():
        return False, f"text smoke did not contain pong: {text!r}"
    return True, "ok"


def run_preflight(base_url: str, trace_dir: str, config_path: str) -> dict[str, Any]:
    before_traces = {path.name for path in Path(trace_dir).glob("*.json")}
    expected_api_key_env = _resolve_expected_api_key_env(config_path)
    env_status = {
        "expected_api_key_env": expected_api_key_env,
        "is_set": bool(expected_api_key_env and os.environ.get(expected_api_key_env)),
    }

    chat_tool_request = {
        "model": "preflight-model",
        "messages": [{"role": "user", "content": "Do not answer in natural language. Call echo with text exactly 'ping'."}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "echo",
                    "description": "Echo text",
                    "parameters": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                },
            }
        ],
    }
    responses_tool_request = {
        "model": "preflight-model",
        "input": [{"role": "user", "content": "Do not answer in natural language. Call echo with text exactly 'ping'."}],
        "tools": [
            {
                "type": "function",
                "name": "echo",
                "description": "Echo text",
                "parameters": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            }
        ],
    }
    chat_text_request = {
        "model": "preflight-model",
        "messages": [{"role": "user", "content": "Reply with the single word PONG."}],
    }

    checks: list[dict[str, Any]] = []
    for name, path, request_payload, validator in [
        ("chat_tool_call", "/v1/chat/completions", chat_tool_request, validate_chat_tool_response),
        ("responses_tool_call", "/v1/responses", responses_tool_request, validate_responses_tool_response),
        ("chat_text_response", "/v1/chat/completions", chat_text_request, validate_chat_text_response),
    ]:
        status_code, response_json = _post_json(base_url, path, request_payload)
        passed = status_code < 400
        reason = "ok"
        if passed:
            passed, reason = validator(response_json if isinstance(response_json, dict) else {})
        else:
            reason = f"http {status_code}: {response_json!r}"
        checks.append(
            {
                "name": name,
                "request_path": path,
                "http_status": status_code,
                "passed": passed,
                "reason": reason,
                "response": response_json,
            }
        )

    after_traces = sorted(path.name for path in Path(trace_dir).glob("*.json"))
    new_traces = [name for name in after_traces if name not in before_traces]
    if len(new_traces) < len(checks):
        checks.append(
            {
                "name": "trace_emission",
                "request_path": None,
                "http_status": None,
                "passed": False,
                "reason": f"expected at least {len(checks)} new traces, observed {len(new_traces)}",
                "response": {"new_traces": new_traces},
            }
        )
    else:
        checks.append(
            {
                "name": "trace_emission",
                "request_path": None,
                "http_status": None,
                "passed": True,
                "reason": "ok",
                "response": {"new_traces": new_traces},
            }
        )

    overall_passed = all(check["passed"] for check in checks) and env_status["is_set"]
    if not env_status["is_set"]:
        env_reason = f"required upstream env var is unset: {expected_api_key_env or 'missing from config'}"
    else:
        env_reason = "ok"
    return {
        "base_url": base_url,
        "config_path": config_path,
        "trace_dir": trace_dir,
        "expected_api_key_env": expected_api_key_env,
        "environment_check": {
            **env_status,
            "reason": env_reason,
        },
        "checks": checks,
        "passed": overall_passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a minimal BFCL I/O preflight against a local grc proxy.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--trace-dir", required=True)
    parser.add_argument("--config-path", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = run_preflight(args.base_url, args.trace_dir, args.config_path)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
