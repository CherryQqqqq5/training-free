#!/usr/bin/env python3
"""Run a redacted ABHE-v0 provider preflight for the approved toolcallingfunction route."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_provider_preflight.json")
PROFILE_PATH = Path("/cephfs/qiuyn/.profile")
API_KEY_ENV = "TOOLCALLINGFUNCTION_API_KEY"
ENDPOINT_ENVS = ["TOOLCALLINGFUNCTION_BASE_URL", "FC_BASE_URL", "NOVACODE_BASE_URL", "NOVACODE_ENDPOINT", "CHUANGZHI_NOVACODE_ENDPOINT"]
EXPECTED_PROVIDER = "ToolCallingFunction/OpenAICompatible"
EXPECTED_PROFILE = "toolcallingfunction"
EXPECTED_MODEL = "gpt-4.1"
EXPECTED_ROUTE_POLICY = "toolcallingfunction_openai_compatible_only_openrouter_disabled"


def _read_profile_env() -> Dict[str, str]:
    if not PROFILE_PATH.exists():
        return {}
    names = [API_KEY_ENV, *ENDPOINT_ENVS, "FC_API_KEY", "TOOLCALLINGFUNCTION_MODEL", "OPENAI_API_KEY"]
    py = "import os,json; names=%r; print(json.dumps({n: os.environ.get(n, '') for n in names}))" % names
    cmd = ["bash", "-lc", "set +x; source /cephfs/qiuyn/.profile >/dev/null 2>&1 || true; %s -c %s" % (sys.executable, json.dumps(py))]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return {k: str(v) for k, v in data.items() if v}


def load_provider_env() -> Tuple[Dict[str, str], Dict[str, bool]]:
    env = dict(os.environ)
    profile_env = _read_profile_env()
    for key, value in profile_env.items():
        env.setdefault(key, value)
    endpoint_status = {name: bool(env.get(name)) for name in ENDPOINT_ENVS}
    status = {
        "api_key_env_present": bool(env.get(API_KEY_ENV)),
        "endpoint_env_present": any(endpoint_status.values()),
        "profile_loaded": bool(profile_env),
    }
    return env, status


def _endpoint(env: Dict[str, str]) -> str:
    for name in ENDPOINT_ENVS:
        value = env.get(name)
        if value:
            return value.strip().rstrip("/")
    return ""


def _preflight_url(base: str) -> str:
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def _attempt_preflight(env: Dict[str, str], timeout_sec: float = 20.0) -> Dict[str, Any]:
    key = env.get(API_KEY_ENV, "")
    base = _endpoint(env)
    if not key or not base:
        return {"attempted": False, "passed": False, "status_code_class": None, "latency_ms": None, "error_class": None}
    payload = {
        "model": EXPECTED_MODEL,
        "messages": [{"role": "user", "content": "Reply OK."}],
        "max_tokens": 4,
        "temperature": 0,
    }
    req = urllib.request.Request(
        _preflight_url(base),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            _ = resp.read(4096)
            status = int(resp.status)
            return {"attempted": True, "passed": 200 <= status < 300, "status_code_class": "%dxx" % (status // 100), "latency_ms": round((time.perf_counter() - started) * 1000, 3), "error_class": None}
    except urllib.error.HTTPError as exc:
        _ = exc.read(4096)
        return {"attempted": True, "passed": False, "status_code_class": "%dxx" % (int(exc.code) // 100), "latency_ms": round((time.perf_counter() - started) * 1000, 3), "error_class": "HTTPError"}
    except Exception as exc:
        return {"attempted": True, "passed": False, "status_code_class": None, "latency_ms": round((time.perf_counter() - started) * 1000, 3), "error_class": exc.__class__.__name__}


def build_report(*, run_live_preflight: bool = True) -> Dict[str, Any]:
    env, env_status = load_provider_env()
    blockers: List[str] = []
    if not env_status["api_key_env_present"]:
        blockers.append("provider_api_key_env_missing")
    if not env_status["endpoint_env_present"]:
        blockers.append("provider_endpoint_env_missing")
    preflight = {"attempted": False, "passed": False, "status_code_class": None, "latency_ms": None, "error_class": None}
    if not blockers and run_live_preflight:
        preflight = _attempt_preflight(env)
        if not preflight.get("passed"):
            blockers.append("provider_preflight_failed")
    elif not blockers:
        blockers.append("provider_preflight_not_run")
    report = {
        "artifact_kind": "abhe_v0_provider_preflight",
        "schema_version": "abhe_v0_provider_preflight_v0",
        "provider": EXPECTED_PROVIDER,
        "profile": EXPECTED_PROFILE,
        "model": EXPECTED_MODEL,
        "route_policy": EXPECTED_ROUTE_POLICY,
        "api_key_env_present": env_status["api_key_env_present"],
        "endpoint_env_present": env_status["endpoint_env_present"],
        "endpoint_env_candidates": ENDPOINT_ENVS,
        "endpoint_env_status_redacted": {name: bool(env.get(name)) for name in ENDPOINT_ENVS},
        "profile_source_checked": True,
        "profile_loaded": env_status["profile_loaded"],
        "provider_calls_made": bool(preflight.get("attempted")),
        "provider_preflight_passed": bool(preflight.get("passed")),
        "preflight_status_code_class": preflight.get("status_code_class"),
        "preflight_latency_ms": preflight.get("latency_ms"),
        "preflight_error_class": preflight.get("error_class"),
        "secret_values_persisted": False,
        "endpoint_value_persisted": False,
        "raw_provider_payload_committed": False,
        "performance_evidence": False,
        "blockers": sorted(set(blockers)),
        "next_required_action": "check_execution_readiness" if not blockers else "restore_provider_env_or_route_before_execution",
    }
    report["blockers"] = sorted(set(report["blockers"] + scan_value(report, label="abhe_v0_provider_preflight")))
    report["provider_preflight_passed"] = report["provider_preflight_passed"] and not report["blockers"]
    return report


def write_report(output: Path, report: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-live-preflight", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_report(run_live_preflight=not args.no_live_preflight)
        write_report(args.output, report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {"report_scope": "abhe_v0_provider_preflight", "provider_preflight_passed": False, "provider_calls_made": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report.get("provider_preflight_passed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
