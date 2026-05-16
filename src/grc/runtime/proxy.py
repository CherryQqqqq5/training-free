from __future__ import annotations

import json
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
from grc.utils.tool_schema import tool_map_from_tools_payload


PROXY_RESPONSES_TOOL_SHAPE_DIAGNOSTIC_TOOL = "synthetic_proxy_responses_tool_shape_ping"
PROXY_RESPONSES_TOOL_SHAPE_DIAGNOSTIC_MODEL = "gpt-4.1"
PROXY_RESPONSES_TOOL_SHAPE_DIAGNOSTIC_MAX_OUTPUT_TOKENS = 16


def _is_proxy_responses_tool_shape_diagnostic_request(request_json: Dict[str, Any]) -> bool:
    if not isinstance(request_json, dict):
        return False
    if request_json.get("model") != PROXY_RESPONSES_TOOL_SHAPE_DIAGNOSTIC_MODEL:
        return False
    if "instructions" in request_json:
        return False
    input_value = request_json.get("input")
    if not isinstance(input_value, list) or len(input_value) != 1:
        return False
    input_item = input_value[0]
    if not isinstance(input_item, dict) or input_item.get("role") != "user":
        return False
    tools = request_json.get("tools")
    if not isinstance(tools, list) or len(tools) != 1:
        return False
    tool = tools[0]
    if not isinstance(tool, dict):
        return False
    if tool.get("type") != "function" or tool.get("name") != PROXY_RESPONSES_TOOL_SHAPE_DIAGNOSTIC_TOOL:
        return False
    tool_choice = request_json.get("tool_choice")
    if not isinstance(tool_choice, dict):
        return False
    choice_function = tool_choice.get("function")
    if tool_choice.get("type") != "function" or not isinstance(choice_function, dict):
        return False
    if choice_function.get("name") != PROXY_RESPONSES_TOOL_SHAPE_DIAGNOSTIC_TOOL:
        return False
    temperature = request_json.get("temperature")
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or temperature != 0:
        return False
    if request_json.get("max_output_tokens") != PROXY_RESPONSES_TOOL_SHAPE_DIAGNOSTIC_MAX_OUTPUT_TOKENS:
        return False
    return True


def _should_direct_align_proxy_responses_tool_shape(request_json: Dict[str, Any]) -> bool:
    return (
        os.environ.get("GRC_PROXY_RESPONSES_TOOL_SHAPE_DIRECT_ALIGNMENT") == "1"
        and _is_proxy_responses_tool_shape_diagnostic_request(request_json)
    )


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


def _responses_json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _responses_function_call_to_chat_tool_call(item: Dict[str, Any], index: int) -> Dict[str, Any] | None:
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        return None

    call_id = item.get("call_id") or item.get("id") or f"resp_call_{index}"
    return {
        "id": str(call_id),
        "type": "function",
        "function": {
            "name": name.strip(),
            "arguments": _responses_json_text(item.get("arguments", "{}")),
        },
    }


def _responses_instructions_to_messages(instructions: Any) -> list[Dict[str, Any]]:
    text = _responses_content_to_text(instructions)
    if not text.strip():
        return []
    return [{"role": "developer", "content": text}]


def _responses_input_to_messages(input_value: Any, instructions: Any = None) -> list[Dict[str, Any]]:
    prefix_messages = _responses_instructions_to_messages(instructions)
    if isinstance(input_value, str):
        return [*prefix_messages, {"role": "user", "content": input_value}]

    if isinstance(input_value, list):
        messages: list[Dict[str, Any]] = list(prefix_messages)
        pending_assistant_index: int | None = None
        for index, item in enumerate(input_value):
            if isinstance(item, str):
                messages.append({"role": "user", "content": item})
                pending_assistant_index = None
                continue
            if not isinstance(item, dict):
                continue

            item_type = item.get("type")
            if item_type == "function_call":
                tool_call = _responses_function_call_to_chat_tool_call(item, index)
                if tool_call is None:
                    pending_assistant_index = None
                    continue
                if pending_assistant_index is None:
                    messages.append({"role": "assistant", "content": "", "tool_calls": [tool_call]})
                    pending_assistant_index = len(messages) - 1
                else:
                    assistant_message = messages[pending_assistant_index]
                    assistant_message.setdefault("tool_calls", []).append(tool_call)
                continue

            if item_type == "function_call_output":
                call_id = item.get("call_id") or item.get("id")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(call_id or f"resp_call_{index}"),
                        "content": _responses_json_text(item.get("output")),
                    }
                )
                pending_assistant_index = None
                continue

            role = item.get("role") or "user"
            # Responses API sometimes uses {"type":"message", ...}
            if item_type == "message":
                role = item.get("role") or role

            text = _responses_content_to_text(item.get("content"))
            if text or item_type == "message":
                messages.append({"role": role, "content": text})
                pending_assistant_index = len(messages) - 1 if role == "assistant" else None

        if len(messages) > len(prefix_messages):
            return messages

    return [*prefix_messages, {"role": "user", "content": ""}]


def _responses_token_fields_to_chat_fields(request_json: Dict[str, Any]) -> Dict[str, Any]:
    forwarded: Dict[str, Any] = {}
    if "max_tokens" in request_json:
        forwarded["max_tokens"] = request_json["max_tokens"]
    elif "max_output_tokens" in request_json:
        forwarded["max_tokens"] = request_json["max_output_tokens"]
    elif "max_completion_tokens" in request_json:
        forwarded["max_tokens"] = request_json["max_completion_tokens"]
    return forwarded


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



def _responses_tool_choice_to_chat_tool_choice(
    tool_choice: Any,
    chat_tools: list[Dict[str, Any]],
    *,
    normalize_missing_none_to_required: bool = False,
) -> Any:
    if not chat_tools:
        return None
    if normalize_missing_none_to_required and (tool_choice is None or tool_choice == "none"):
        return "required"
    if isinstance(tool_choice, (str, dict)):
        return tool_choice
    return None



def _load_abhe_v0_runtime_candidate_adapter() -> Dict[str, Any] | None:
    adapter_path = os.environ.get("ABHE_V0_RUNTIME_CANDIDATE_ADAPTER")
    if not adapter_path:
        return None
    try:
        data = json.loads(Path(adapter_path).read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("adapter_ready") is not True:
        return None
    if data.get("candidate_jsonl_generated") is not False:
        return None
    if data.get("candidate_rule_generated") is not False:
        return None
    if data.get("candidate_yaml_generated") is not False:
        return None
    return data



def _abhe_v0_projection_guidance(projection: Dict[str, Any]) -> str:
    entry_id = projection.get("entry_id")
    candidate_type = projection.get("candidate_type")
    if entry_id == "state_tracking_v0" and candidate_type == "state_summary_injection":
        return (
            "For selected multi-turn state carryover cases, preserve prior-turn entities, "
            "constraints, and selected options when later turns refer back to them. "
            "Do not mutate state, do not activate on single-turn cases, and do not activate "
            "for search or memory watch behavior."
        )
    if entry_id == "hallucination_abstain_v0" and candidate_type == "evidence_boundary_verifier":
        return (
            "For selected answerability-boundary cases, do not fabricate unsupported or "
            "irrelevant answers. If evidence or tool capability is insufficient, use an "
            "insufficient-evidence boundary response. Do not suppress valid actionable tool calls, "
            "and preserve false-abstain telemetry boundaries."
        )
    return ""


def _abhe_v0_active_projection(adapter: Dict[str, Any]) -> tuple[Dict[str, Any] | None, str]:
    projections = [projection for projection in adapter.get("runtime_projection", []) if isinstance(projection, dict)]
    requested_entry = os.environ.get("ABHE_V0_RUNTIME_ACTIVATION_ENTRY", "").strip()
    requested_categories = {
        item.strip()
        for item in os.environ.get("ABHE_V0_RUNTIME_ACTIVATION_CATEGORIES", "").split(",")
        if item.strip()
    }
    if requested_entry:
        for projection in projections:
            if projection.get("entry_id") == requested_entry:
                return projection, "entry_env_match"
        return None, "entry_env_no_projection_match"
    if requested_categories:
        for projection in projections:
            categories = set(projection.get("activation_categories") or [])
            if categories.intersection(requested_categories):
                return projection, "category_env_match"
        return None, "category_env_no_projection_match"
    return None, "bfcl_request_context_missing"


def _apply_abhe_v0_adapter_guidance(chat_req_json: Dict[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    adapter = _load_abhe_v0_runtime_candidate_adapter()
    if adapter is None:
        return chat_req_json, []
    projection, reason = _abhe_v0_active_projection(adapter)
    if projection is None:
        return chat_req_json, [f"abhe_v0_runtime_candidate_adapter_guidance_skipped:{reason}"]
    guidance_fragment = _abhe_v0_projection_guidance(projection)
    if not guidance_fragment:
        return chat_req_json, ["abhe_v0_runtime_candidate_adapter_guidance_skipped:empty_projection_guidance"]
    patched = dict(chat_req_json)
    messages = list(patched.get("messages") or [])
    entry_id = str(projection.get("entry_id"))
    guidance = "ABHE-v0 bounded dev smoke candidate guidance. " + guidance_fragment
    messages.insert(0, {"role": "developer", "content": guidance})
    patched["messages"] = messages
    return patched, [f"abhe_v0_runtime_candidate_adapter_guidance:{entry_id}"]

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
    runtime_policy = cfg.get("runtime_policy") if isinstance(cfg.get("runtime_policy"), dict) else {}
    engine = RuleEngine(rules_dir, runtime_policy=runtime_policy)
    trace_store = TraceStore(trace_dir)
    normalize_responses_tool_choice_required = bool(
        runtime_policy.get("bfcl_measurement_responses_to_chat_tool_choice_normalization")
    )

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
        adapter_req_json, adapter_patches = _apply_abhe_v0_adapter_guidance(original_req_json)
        req_json, request_patches = engine.apply_request(adapter_req_json)
        request_patches = list(request_patches) + adapter_patches

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
        tool_schema_snapshot = tool_map_from_tools_payload(req_json.get("tools", []))

        trace_store.write(
            {
                "request_original": original_req_json,
                "request": req_json,
                "tool_schema_snapshot": tool_schema_snapshot,
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

        diagnostic_direct_shape = _should_direct_align_proxy_responses_tool_shape(original_req_json)
        chat_req_json: Dict[str, Any] = {
            "model": original_req_json.get("model"),
            "messages": _responses_input_to_messages(
                original_req_json.get("input"),
                instructions=original_req_json.get("instructions"),
            ),
            **_responses_token_fields_to_chat_fields(original_req_json),
        }
        if diagnostic_direct_shape and "temperature" in original_req_json:
            chat_req_json["temperature"] = original_req_json["temperature"]
        chat_tools = _responses_tools_to_chat_tools(original_req_json.get("tools"))
        if chat_tools:
            chat_req_json["tools"] = chat_tools
            chat_tool_choice = _responses_tool_choice_to_chat_tool_choice(
                original_req_json.get("tool_choice"),
                chat_tools,
                normalize_missing_none_to_required=normalize_responses_tool_choice_required,
            )
            if chat_tool_choice is not None:
                chat_req_json["tool_choice"] = chat_tool_choice

        if diagnostic_direct_shape:
            req_json = chat_req_json
            request_patches = []
        else:
            adapter_chat_req_json, adapter_patches = _apply_abhe_v0_adapter_guidance(chat_req_json)
            req_json, request_patches = engine.apply_request(adapter_chat_req_json)
            request_patches = list(request_patches) + adapter_patches
        if upstream_model:
            req_json["model"] = upstream_model

        api_key = os.environ.get(upstream_api_key_env)
        if not api_key:
            raise HTTPException(status_code=500, detail=f"missing env var: {upstream_api_key_env}")

        headers = {
            "Authorization": f"Bearer {api_key}",
        }
        headers.update(upstream_cfg["headers"])

        post_kwargs: Dict[str, Any] = {"headers": headers}
        if diagnostic_direct_shape:
            post_kwargs["content"] = json.dumps(req_json, separators=(",", ":")).encode("utf-8")
        else:
            post_kwargs["json"] = req_json

        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            started_at = time.perf_counter()
            resp = await client.post(
                f"{upstream_base_url}/chat/completions",
                **post_kwargs,
            )
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 3)

        raw_json = resp.json()
        tool_schema_snapshot = tool_map_from_tools_payload(req_json.get("tools", []))
        if resp.status_code >= 400:
            # Keep upstream error payload untouched so BFCL can surface root cause.
            trace_store.write(
                {
                    "request_original": original_req_json,
                    "request": req_json,
                    "tool_schema_snapshot": tool_schema_snapshot,
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
                "tool_schema_snapshot": tool_schema_snapshot,
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
