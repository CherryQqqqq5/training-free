#!/usr/bin/env python3
"""Check whether the approved provider route is green for BFCL execution.

This checker is offline-only. It accepts either the compact
``current_provider_preflight_status.json`` shape or a raw
``run_bfcl_preflight.py`` report, and it classifies the failure mode so the
formal performance gate can fail closed without hiding credential/provider
problems behind a generic red status.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_PROVIDER = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json")
DEFAULT_OUT = Path("outputs/artifacts/stage1_bfcl_acceptance/provider_green_preflight.json")
DEFAULT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/provider_green_preflight.md")
REQUIRED_CHECKS = ("chat_tool_call", "responses_tool_call", "chat_text_response", "trace_emission")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _as_bool(value: Any) -> bool:
    return bool(value is True or str(value).lower() == "true")


def _checks_by_name(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(check.get("name")): check
        for check in report.get("checks") or []
        if isinstance(check, dict) and check.get("name")
    }


def _classify_http_status(status: Any, reason: str = "") -> str | None:
    try:
        code = int(status)
    except (TypeError, ValueError):
        return None
    lowered = reason.lower()
    if code == 401:
        return "provider_auth_401"
    if code == 403:
        return "provider_auth_403"
    if code == 429:
        return "provider_rate_limited_429"
    if code in {404, 410} or "model" in lowered and ("unavailable" in lowered or "not found" in lowered):
        return "provider_model_unavailable"
    if code >= 500:
        return "provider_server_error"
    if code >= 400:
        return f"provider_http_{code}"
    return None


def _failure_class_blocker(value: Any) -> str | None:
    text = str(value or "").lower()
    if not text:
        return None
    if "env" in text or "credential" in text and "missing" in text:
        return "provider_env_missing"
    if "missing_authentication" in text or "invalid_api_key" in text or "unauthorized" in text:
        return "provider_auth_401"
    if "forbidden" in text or "permission" in text:
        return "provider_auth_403"
    if "rate" in text or "quota" in text:
        return "provider_rate_limited_429"
    if "model" in text and ("unavailable" in text or "not_found" in text or "not found" in text):
        return "provider_model_unavailable"
    return None


def evaluate(path: Path = DEFAULT_PROVIDER) -> dict[str, Any]:
    report = _load_json(path, {}) or {}
    checks = _checks_by_name(report)
    environment = report.get("environment_check") if isinstance(report.get("environment_check"), dict) else {}
    required_fields = {
        "source_collection_rerun_ready": _as_bool(report.get("source_collection_rerun_ready")),
        "candidate_evaluation_ready": _as_bool(report.get("candidate_evaluation_ready")),
        "upstream_auth_passed": _as_bool(report.get("upstream_auth_passed")),
        "model_route_available": _as_bool(report.get("model_route_available")),
        "bfcl_compatible_response": _as_bool(report.get("bfcl_compatible_response")),
    }
    required_checks = {
        name: _as_bool((checks.get(name) or {}).get("passed"))
        for name in REQUIRED_CHECKS
    }
    has_structured_required_fields = any(key in report for key in required_fields)
    has_preflight_checks = bool(checks)
    green_by_fields = has_structured_required_fields and all(required_fields.values())
    green_by_checks = _as_bool(report.get("passed")) and has_preflight_checks and all(required_checks.values())

    blockers: list[str] = []
    if not path.exists():
        blockers.append("provider_preflight_status_missing")
    if not isinstance(report, dict) or not report:
        blockers.append("provider_green_evidence_missing")
    if has_structured_required_fields and not all(required_fields.values()):
        blockers.append("provider_required_fields_not_green")
    if has_preflight_checks and not all(required_checks.values()):
        blockers.append("provider_preflight_checks_not_green")
    if has_preflight_checks:
        for name, passed in required_checks.items():
            if not passed and name in checks:
                blockers.append(f"{name}_preflight_failed")
        missing_checks = [name for name in REQUIRED_CHECKS if name not in checks]
        if missing_checks:
            blockers.append("provider_required_preflight_checks_missing")
    if not has_structured_required_fields and not has_preflight_checks:
        blockers.append("provider_green_evidence_missing")
    if environment and not _as_bool(environment.get("is_set")):
        blockers.append("provider_env_missing")
    if report.get("expected_api_key_env") and environment and environment.get("expected_api_key_env") != report.get("expected_api_key_env"):
        blockers.append("provider_expected_api_key_env_mismatch")
    for check in checks.values():
        status = check.get("http_status")
        blocker = _classify_http_status(status, str(check.get("reason") or ""))
        if blocker:
            blockers.append(blocker)
    for attempt in report.get("attempted_provider_profiles") or []:
        if not isinstance(attempt, dict):
            continue
        blocker = _classify_http_status(attempt.get("http_status"), str(attempt.get("failure_class") or attempt.get("result") or ""))
        if blocker:
            blockers.append(blocker)
        failure_blocker = _failure_class_blocker(attempt.get("failure_class"))
        if failure_blocker:
            blockers.append(failure_blocker)
    direct_blocker = _failure_class_blocker(report.get("blocking_condition") or report.get("failure_class"))
    if direct_blocker:
        blockers.append(direct_blocker)

    passed = bool((green_by_fields or green_by_checks) and not blockers)
    blockers = sorted(set(blockers))
    return {
        "report_scope": "provider_green_preflight",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "path": str(path),
        "present": path.exists(),
        "provider_green_preflight_passed": passed,
        "required_fields": required_fields,
        "required_checks": required_checks,
        "expected_api_key_env": report.get("expected_api_key_env") or environment.get("expected_api_key_env"),
        "provider_profile": report.get("provider_profile"),
        "provider_route_policy": report.get("provider_route_policy"),
        "upstream_base_url_sanitized": report.get("upstream_base_url_sanitized"),
        "upstream_model": report.get("upstream_model"),
        "environment_check": environment,
        "blocking_condition": report.get("blocking_condition"),
        "next_required_action": report.get("next_required_action"),
        "blockers": blockers,
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Provider Green Preflight",
        "",
        f"- Provider green preflight passed: `{report['provider_green_preflight_passed']}`",
        f"- Required fields: `{report['required_fields']}`",
        f"- Required checks: `{report['required_checks']}`",
        f"- Expected API key env: `{report['expected_api_key_env']}`",
        f"- Provider profile: `{report.get('provider_profile')}`",
        f"- Provider route policy: `{report.get('provider_route_policy')}`",
        f"- Upstream base URL: `{report.get('upstream_base_url_sanitized')}`",
        f"- Upstream model: `{report.get('upstream_model')}`",
        f"- Blockers: `{report['blockers']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "This checker is offline-only and does not run BFCL, a model, or a scorer.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-status", type=Path, default=DEFAULT_PROVIDER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.provider_status)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report if not args.compact else {
        "provider_green_preflight_passed": report["provider_green_preflight_passed"],
        "blockers": report["blockers"],
        "next_required_action": report["next_required_action"],
    }, indent=2, sort_keys=True))
    if args.strict and not report["provider_green_preflight_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
