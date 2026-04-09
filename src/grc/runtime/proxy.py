from __future__ import annotations

import os
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

    upstream_base_url = cfg["upstream"]["base_url"].rstrip("/")
    upstream_api_key_env = cfg["upstream"]["api_key_env"]
    upstream_model = cfg["upstream"].get("model")
    timeout_sec = cfg.get("timeout_sec", 120)

    app = FastAPI()

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {"ok": True}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> JSONResponse:
        req_json = await request.json()
        req_json = engine.apply_request(req_json)

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
            resp = await client.post(
                f"{upstream_base_url}/chat/completions",
                headers=headers,
                json=req_json,
            )

        raw_json = resp.json()
        final_json, repairs = engine.apply_response(req_json, raw_json)

        trace_store.write(
            {
                "request": req_json,
                "raw_response": raw_json,
                "final_response": final_json,
                "repairs": repairs,
                "status_code": resp.status_code,
            }
        )
        return JSONResponse(content=final_json, status_code=resp.status_code)

    return app

