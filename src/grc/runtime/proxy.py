from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict

import httpx
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from grc.runtime.engine import RuleEngine
from grc.runtime.trace_store import TraceStore


def _responses_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or item.get("input_text")
                if isinstance(text, str):
                    chunks.append(text)
        return "\n".join(chunk for chunk in chunks if chunk)
    if isinstance(content, dict):
        text = content.get("text") or content.get("content") or content.get("input_text")
        if isinstance(text, str):
            return text
    return ""


def _responses_input_to_messages(input_value: Any) -> list[Dict[str, Any]]:
    if isinstance(input_value, str):
        return [{"role": "user", "content": input_value}]

    if isinstance(input_value, list):
        messages: list[Dict[str, Any]] = []
        for item in input_value:
            if isinstance(item, str):
                messages.append({"role": "user", "content": item})
                continue
            if not isinstance(item, dict):
                continue

            role = item.get("role") or "user"
            # Responses API sometimes uses {"type":"message", ...}
            if item.get("type") == "message":
                role = item.get("role") or role

            text = _responses_content_to_text(item.get("content"))
            if text:
                messages.append({"role": role, "content": text})

        if messages:
            return messages

    return [{"role": "user", "content": ""}]


def _responses_tools_to_chat_tools(tools: Any) -> list[Dict[str, Any]]:
    if not isinstance(tools, list):
        return []

    mapped: list[Dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue

        if "function" in tool and isinstance(tool.get("function"), dict):
            mapped.append(tool)
            continue

        # Responses format: {"type":"function","name":"...","parameters":{...}}
        if tool.get("type") == "function" and tool.get("name"):
            mapped.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name"),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                    },
                }
            )

    return mapped


def _chat_response_to_responses_payload(chat_json: Dict[str, Any]) -> Dict[str, Any]:
    choices = chat_json.get("choices", [])
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    msg_content = message.get("content", "")
    output_text = _responses_content_to_text(msg_content)

    output_items: list[Dict[str, Any]] = []
    if output_text:
        output_items.append(
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": output_text}],
            }
        )

    for tool_call in message.get("tool_calls", []) or []:
        if not isinstance(tool_call, dict):
            continue
        fn = tool_call.get("function", {}) if isinstance(tool_call.get("function"), dict) else {}
        output_items.append(
            {
                "type": "function_call",
                "id": tool_call.get("id"),
                "call_id": tool_call.get("id"),
                "name": fn.get("name"),
                "arguments": fn.get("arguments", "{}"),
            }
        )

    if not output_items:
        output_items.append(
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": ""}],
            }
        )

    return {
        "id": chat_json.get("id", f"resp_{int(time.time())}"),
        "object": "response",
        "created_at": int(time.time()),
        "model": chat_json.get("model"),
        "output": output_items,
        "usage": chat_json.get("usage"),
    }


def _resolve_upstream_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    upstream_cfg = dict(cfg["upstream"])
    profiles = upstream_cfg.get("profiles", {}) if isinstance(upstream_cfg.get("profiles"), dict) else {}
    profile_name = os.environ.get("GRC_UPSTREAM_PROFILE", upstream_cfg.get("active_profile", ""))

    resolved = dict(upstream_cfg)
    if profile_name:
        if profile_name not in profiles:
            raise ValueError(f"unknown upstream profile: {profile_name}")
        resolved.update(profiles[profile_name] or {})

    base_url_env = resolved.get("base_url_env")
    base_url = (
        os.environ.get("GRC_UPSTREAM_BASE_URL")
        or (os.environ.get(base_url_env) if base_url_env else None)
        or resolved.get("base_url")
        or ""
    )
    api_key_env = os.environ.get("GRC_UPSTREAM_API_KEY_ENV") or resolved.get("api_key_env", "")
    model = os.environ.get("GRC_UPSTREAM_MODEL") or resolved.get("model")

    headers: Dict[str, str] = {
        "Content-Type": "application/json",
    }

    http_referer_env = resolved.get("http_referer_env")
    title_env = resolved.get("title_env")
    http_referer = os.environ.get(http_referer_env, "") if http_referer_env else ""
    title = os.environ.get(title_env, "") if title_env else ""
    if http_referer:
        headers["HTTP-Referer"] = http_referer
    if title:
        headers["X-Title"] = title
    elif resolved.get("default_title"):
        headers["X-Title"] = str(resolved["default_title"])

    return {
        "profile_name": profile_name,
        "base_url": str(base_url).rstrip("/"),
        "api_key_env": str(api_key_env),
        "model": model,
        "headers": headers,
    }


def create_app(config_path: str, rules_dir: str, trace_dir: str) -> FastAPI:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    engine = RuleEngine(rules_dir)
    trace_store = TraceStore(trace_dir)

    upstream_cfg = _resolve_upstream_config(cfg)
    upstream_profile = upstream_cfg["profile_name"]
    upstream_base_url = upstream_cfg["base_url"]
    upstream_api_key_env = upstream_cfg["api_key_env"]
    upstream_model = upstream_cfg["model"]
    timeout_sec = cfg.get("timeout_sec", 120)

    if not upstream_base_url or "YOUR_" in upstream_base_url:
        raise ValueError(
            "upstream.base_url is not configured; set GRC_UPSTREAM_BASE_URL or update configs/runtime.yaml"
        )

    app = FastAPI()

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {"ok": True}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> JSONResponse:
        original_req_json = await request.json()
        req_json, request_patches = engine.apply_request(original_req_json)

        if upstream_model:
            req_json["model"] = upstream_model

        api_key = os.environ.get(upstream_api_key_env)
        if not api_key:
            raise HTTPException(status_code=500, detail=f"missing env var: {upstream_api_key_env}")

        headers = {
            "Authorization": f"Bearer {api_key}",
        }
        headers.update(upstream_cfg["headers"])

        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            started_at = time.perf_counter()
            resp = await client.post(
                f"{upstream_base_url}/chat/completions",
                headers=headers,
                json=req_json,
            )
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 3)

        raw_json = resp.json()
        final_json, repairs, validation = engine.apply_response(req_json, raw_json, request_patches=request_patches)

        trace_store.write(
            {
                "request_original": original_req_json,
                "request": req_json,
                "raw_response": raw_json,
                "final_response": final_json,
                "repairs": repairs,
                "validation": validation.model_dump(mode="json"),
                "status_code": resp.status_code,
                "latency_ms": elapsed_ms,
                "upstream_profile": upstream_profile,
                "upstream_model": upstream_model,
                "upstream_base_url": upstream_base_url,
                "request_endpoint": "/v1/chat/completions",
            }
        )
        return JSONResponse(content=final_json, status_code=resp.status_code)

    @app.post("/v1/responses")
    async def responses(request: Request) -> JSONResponse:
        original_req_json = await request.json()

        chat_req_json: Dict[str, Any] = {
            "model": original_req_json.get("model"),
            "messages": _responses_input_to_messages(original_req_json.get("input")),
        }
        chat_tools = _responses_tools_to_chat_tools(original_req_json.get("tools"))
        if chat_tools:
            chat_req_json["tools"] = chat_tools
            if isinstance(original_req_json.get("tool_choice"), (str, dict)):
                chat_req_json["tool_choice"] = original_req_json["tool_choice"]

        req_json, request_patches = engine.apply_request(chat_req_json)
        if upstream_model:
            req_json["model"] = upstream_model

        api_key = os.environ.get(upstream_api_key_env)
        if not api_key:
            raise HTTPException(status_code=500, detail=f"missing env var: {upstream_api_key_env}")

        headers = {
            "Authorization": f"Bearer {api_key}",
        }
        headers.update(upstream_cfg["headers"])

        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            started_at = time.perf_counter()
            resp = await client.post(
                f"{upstream_base_url}/chat/completions",
                headers=headers,
                json=req_json,
            )
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 3)

        raw_json = resp.json()
        if resp.status_code >= 400:
            # Keep upstream error payload untouched so BFCL can surface root cause.
            trace_store.write(
                {
                    "request_original": original_req_json,
                    "request": req_json,
                    "raw_response": raw_json,
                    "final_response": raw_json,
                    "repairs": [],
                    "validation": {"issues": [], "rule_hits": [], "request_patches": []},
                    "status_code": resp.status_code,
                    "latency_ms": elapsed_ms,
                    "upstream_profile": upstream_profile,
                    "upstream_model": upstream_model,
                    "upstream_base_url": upstream_base_url,
                    "request_endpoint": "/v1/responses",
                }
            )
            return JSONResponse(content=raw_json, status_code=resp.status_code)

        final_chat_json, repairs, validation = engine.apply_response(req_json, raw_json, request_patches=request_patches)
        final_responses_json = _chat_response_to_responses_payload(final_chat_json)

        trace_store.write(
            {
                "request_original": original_req_json,
                "request": req_json,
                "raw_response": raw_json,
                "final_response": final_responses_json,
                "final_chat_response": final_chat_json,
                "repairs": repairs,
                "validation": validation.model_dump(mode="json"),
                "status_code": resp.status_code,
                "latency_ms": elapsed_ms,
                "upstream_profile": upstream_profile,
                "upstream_model": upstream_model,
                "upstream_base_url": upstream_base_url,
                "request_endpoint": "/v1/responses",
            }
        )
        return JSONResponse(content=final_responses_json, status_code=resp.status_code)

    return app
