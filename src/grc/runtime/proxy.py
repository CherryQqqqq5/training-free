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


def create_app(config_path: str, rules_dir: str, trace_dir: str) -> FastAPI:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    engine = RuleEngine(rules_dir)
    trace_store = TraceStore(trace_dir)

    upstream_cfg = cfg["upstream"]
    upstream_base_url = os.environ.get("GRC_UPSTREAM_BASE_URL", upstream_cfg["base_url"]).rstrip("/")
    upstream_api_key_env = os.environ.get("GRC_UPSTREAM_API_KEY_ENV", upstream_cfg["api_key_env"])
    upstream_model = os.environ.get("GRC_UPSTREAM_MODEL", upstream_cfg.get("model"))
    timeout_sec = cfg.get("timeout_sec", 120)

    if not upstream_base_url or "YOUR_UPSTREAM_OPENAI_COMPATIBLE_ENDPOINT" in upstream_base_url:
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
            "Content-Type": "application/json",
        }

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
            }
        )
        return JSONResponse(content=final_json, status_code=resp.status_code)

    return app
