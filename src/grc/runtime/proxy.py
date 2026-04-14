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
            }
        )
        return JSONResponse(content=final_json, status_code=resp.status_code)

    return app
