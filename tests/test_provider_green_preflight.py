from __future__ import annotations

import json
from pathlib import Path

from scripts.check_provider_green_preflight import evaluate


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_provider_green_preflight_blocks_401(tmp_path: Path) -> None:
    path = tmp_path / "provider.json"
    _write(
        path,
        {
            "passed": False,
            "checks": [
                {"name": "chat_tool_call", "passed": False, "http_status": 401},
                {"name": "responses_tool_call", "passed": False, "http_status": 401},
                {"name": "chat_text_response", "passed": False, "http_status": 401},
                {"name": "trace_emission", "passed": True},
            ],
        },
    )

    report = evaluate(path)

    assert report["provider_green_preflight_passed"] is False
    assert "provider_auth_401" in report["blockers"]


def test_provider_green_preflight_accepts_structured_green_fields(tmp_path: Path) -> None:
    path = tmp_path / "provider.json"
    _write(
        path,
        {
            "source_collection_rerun_ready": True,
            "candidate_evaluation_ready": True,
            "upstream_auth_passed": True,
            "model_route_available": True,
            "bfcl_compatible_response": True,
        },
    )

    report = evaluate(path)

    assert report["provider_green_preflight_passed"] is True
    assert report["blockers"] == []
