#!/usr/bin/env python3
"""Run an offline compact prepared-request/wire-fingerprint diff for proxy diagnostics."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import sys
import types
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_proxy_wire_fingerprint_diff_artifact import check as check_artifact
from scripts.check_bfcl_proxy_wire_fingerprint_diff_gate import DEFAULT_PACKET, REQUIRED_COMPACT_FIELDS, check as check_packet
from scripts.run_bfcl_proxy_responses_tool_shape import _responses_payload

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_wire_fingerprint_diff_compact.json")
PROXY_SOURCE = Path("src/grc/runtime/proxy.py")
HTTPX_DEFAULT_HEADER_NAMES = {"user-agent", "accept", "accept-encoding", "connection"}
PROXY_ENV_NAMES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")


def _base_record(command_executed: bool = False) -> Dict[str, Any]:
    return {
        "preflight_command_executed": command_executed,
        "provider_call_started": False,
        "profile_sourced": False,
        "proxy_live_request_started": False,
        "fake_transport_capture_used": command_executed,
        "prepared_request_capture_used": command_executed,
        "direct_client_stack_label": "unknown",
        "proxy_client_stack_label": "unknown",
        "method_label": "unknown",
        "url_suffix_label": "unknown",
        "wire_request_target_label": "unknown",
        "header_name_set_label": "unknown",
        "direct_header_name_set_label": "unknown",
        "default_header_shape_label": "unknown",
        "wire_user_agent_label": "unknown",
        "wire_accept_label": "unknown",
        "wire_accept_encoding_label": "unknown",
        "wire_connection_label": "unknown",
        "content_length_shape_label": "unknown",
        "transfer_encoding_label": "unknown",
        "body_bytes_shape_match_label": "unknown",
        "proxy_env_presence_label": _proxy_env_presence_label(),
        "trust_env_label": "unknown",
        "http2_config_label": "unknown",
        "timeout_shape_label": "unknown",
        "tls_context_source_label": "not_observed",
        "raw_outputs_committed": False,
        "raw_temp_outputs_removed": command_executed,
        "suspected_403_cause_label": "unknown",
        "bfcl_generate_started": False,
        "bfcl_evaluate_started": False,
        "scorer_started": False,
        "full_baseline_executed": False,
        "candidate_specs_inert": True,
        "source_collection_executed": False,
        "source_diagnostics_executed": False,
        "performance_evidence": False,
        "stop_gate_triggered": "none" if not command_executed else "stopped_after_prepared_request_capture",
        "preflight_failed_check_label": "none_observed",
    }


def _proxy_env_presence_label() -> str:
    return "proxy_env_names_present" if any(os.environ.get(name) for name in PROXY_ENV_NAMES) else "proxy_env_names_absent"


def _header_name_label(names: set) -> str:
    lower = {str(name).lower() for name in names}
    if {"authorization", "content-type", "content-length"}.issubset(lower) and HTTPX_DEFAULT_HEADER_NAMES.issubset(lower):
        return "authorization_content_type_content_length_httpx_defaults"
    if lower == {"authorization", "content-type"} or {"authorization", "content-type"}.issubset(lower) and not (HTTPX_DEFAULT_HEADER_NAMES & lower) and "content-length" not in lower:
        return "authorization_content_type_only"
    return "unknown"


def _presence_diff(proxy_headers: set, direct_headers: set, header_name: str) -> str:
    proxy_present = header_name in proxy_headers
    direct_present = header_name in direct_headers
    if proxy_present and not direct_present:
        return "proxy_present_direct_not_observed"
    if proxy_present:
        return "present"
    if direct_present:
        return "absent"
    return "not_observed"


def _suffix_label(target: Any) -> str:
    return "chat_completions_suffix" if str(target).endswith("/chat/completions") else "unknown"


def _target_label(target: Any) -> str:
    return "chat_completions_target" if str(target).endswith("/chat/completions") else "unknown"


def _nonzero_bytes(value: Any) -> bool:
    return isinstance(value, (bytes, bytearray)) and len(value) > 0


def _direct_prepared_capture() -> Dict[str, Any]:
    import scripts.run_bfcl_live_provider_preflight as direct_runner

    captured: Dict[str, Any] = {}

    class FakeUrlopenResponse:
        status = 200

        def __enter__(self) -> "FakeUrlopenResponse":
            return self

        def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> bool:
            return False

        def read(self) -> bytes:
            return b"{}"

    def fake_urlopen(request: Any, timeout: Any = None) -> FakeUrlopenResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeUrlopenResponse()

    original_urlopen = direct_runner.urllib.request.urlopen
    try:
        direct_runner.urllib.request.urlopen = fake_urlopen
        direct_runner._default_post_json(
            "http://capture.invalid/chat/completions",
            "synthetic-direct-token",
            direct_runner._chat_tool_payload(),
        )
    finally:
        direct_runner.urllib.request.urlopen = original_urlopen

    request = captured.get("request")
    header_items = dict(request.header_items()) if request is not None else {}
    headers = {str(key).lower() for key in header_items}
    body = getattr(request, "data", b"") if request is not None else b""
    target = getattr(request, "full_url", "") if request is not None else ""
    method = getattr(request, "get_method", lambda: "")()
    return {
        "client_stack_label": "urllib_request",
        "method_label": "post" if str(method).upper() == "POST" else "unknown",
        "url_suffix_label": _suffix_label(target),
        "wire_request_target_label": _target_label(target),
        "header_names": headers,
        "header_name_set_label": _header_name_label(headers),
        "body_nonzero": _nonzero_bytes(body),
        "timeout": captured.get("timeout"),
    }


class _FakeFastAPI:
    def __init__(self) -> None:
        self.routes: Dict[Tuple[str, str], Any] = {}

    def get(self, path: str, *_args: Any, **_kwargs: Any) -> Any:
        def decorator(func: Any) -> Any:
            self.routes[("GET", path)] = func
            return func
        return decorator

    def post(self, path: str, *_args: Any, **_kwargs: Any) -> Any:
        def decorator(func: Any) -> Any:
            self.routes[("POST", path)] = func
            return func
        return decorator


class _FakeHTTPException(Exception):
    def __init__(self, status_code: Any = None, detail: Any = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _FakeJSONResponse:
    def __init__(self, content: Any = None, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code


class _FakeRequest:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = payload

    async def json(self) -> Dict[str, Any]:
        return self._payload


class _FakeRuleEngine:
    apply_request_called = False

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def apply_request(self, request_json: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Any]]:
        type(self).apply_request_called = True
        return request_json, []

    def apply_response(self, request_json: Dict[str, Any], response_json: Dict[str, Any], request_patches: Any = None) -> Tuple[Dict[str, Any], List[Any], Any]:
        class Validation:
            def model_dump(self, mode: str = "json") -> Dict[str, Any]:
                return {"issues": [], "rule_hits": [], "request_patches": []}
        return response_json, [], Validation()


class _FakeTraceStore:
    write_called = False

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def write(self, _payload: Dict[str, Any]) -> None:
        type(self).write_called = True


class _PreparedRequestCapture:
    def __init__(self, method: str, url: str, headers: Dict[str, str], body: bytes, timeout: Any, trust_env: bool, http2: bool) -> None:
        self.method = method
        self.url = url
        self.header_names = {str(name).lower() for name in headers}
        self.body_nonzero = len(body) > 0
        self.timeout = timeout
        self.trust_env = trust_env
        self.http2 = http2


class _FakeAsyncClient:
    capture: Dict[str, Any] = {}

    def __init__(self, timeout: Any = None, trust_env: bool = True, http2: bool = False, **_kwargs: Any) -> None:
        self.timeout = timeout
        self.trust_env = trust_env
        self.http2 = http2

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> bool:
        return False

    async def post(self, url: str, **kwargs: Any) -> Any:
        headers = {"accept": "", "accept-encoding": "", "connection": "", "user-agent": ""}
        parsed = urllib.parse.urlparse(str(url))
        if parsed.netloc:
            headers["host"] = ""
        passed_headers = kwargs.get("headers") if isinstance(kwargs.get("headers"), dict) else {}
        for key in passed_headers:
            headers[str(key).lower()] = ""
        body = b""
        if isinstance(kwargs.get("content"), (bytes, bytearray)):
            body = bytes(kwargs.get("content"))
        elif "json" in kwargs:
            body = json.dumps(kwargs.get("json"), separators=(",", ":")).encode("utf-8")
        elif isinstance(kwargs.get("data"), (bytes, bytearray)):
            body = bytes(kwargs.get("data"))
        if body:
            headers["content-length"] = ""
        prepared = _PreparedRequestCapture("POST", str(url), headers, body, self.timeout, self.trust_env, self.http2)
        type(self).capture["prepared_request"] = prepared

        class FakeResponse:
            status_code = 200

            def json(self) -> Dict[str, Any]:
                return {
                    "id": "synthetic",
                    "model": "gpt-4.1",
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {
                                        "id": "synthetic_call",
                                        "type": "function",
                                        "function": {"name": "synthetic_proxy_responses_tool_shape_ping", "arguments": "{}"},
                                    }
                                ]
                            }
                        }
                    ],
                }

        return FakeResponse()


def _install_proxy_import_stubs() -> Dict[str, Any]:
    names = (
        "fastapi", "fastapi.responses", "httpx", "yaml", "grc", "grc.runtime", "grc.runtime.engine",
        "grc.runtime.trace_store", "grc.utils", "grc.utils.tool_schema",
    )
    original_modules = {name: sys.modules.get(name) for name in names}
    fake_fastapi = types.ModuleType("fastapi")
    fake_fastapi.FastAPI = _FakeFastAPI
    fake_fastapi.HTTPException = _FakeHTTPException
    fake_fastapi.Request = _FakeRequest
    fake_responses = types.ModuleType("fastapi.responses")
    fake_responses.JSONResponse = _FakeJSONResponse
    fake_httpx = types.ModuleType("httpx")
    fake_httpx.AsyncClient = _FakeAsyncClient
    fake_yaml = types.ModuleType("yaml")
    fake_yaml.safe_load = lambda _text: {
        "timeout_sec": 120,
        "runtime_policy": {"bfcl_measurement_responses_to_chat_tool_choice_normalization": True},
        "upstream": {
            "active_profile": "novacode",
            "base_url": "ENV_ONLY",
            "api_key_env": "OPENAI_API_KEY",
            "model": "gpt-4.1",
            "profiles": {
                "novacode": {
                    "base_url_env": "NOVACODE_BASE_URL",
                    "base_url": "ENV_ONLY_NOVACODE_BASE_URL",
                    "api_key_env": "NOVACODE_API_KEY",
                    "model": "gpt-4.1",
                }
            },
            "base_url_env": "NOVACODE_BASE_URL",
        },
    }
    fake_grc = types.ModuleType("grc")
    fake_grc.__path__ = []
    fake_runtime = types.ModuleType("grc.runtime")
    fake_runtime.__path__ = []
    fake_engine = types.ModuleType("grc.runtime.engine")
    fake_engine.RuleEngine = _FakeRuleEngine
    fake_trace = types.ModuleType("grc.runtime.trace_store")
    fake_trace.TraceStore = _FakeTraceStore
    fake_utils = types.ModuleType("grc.utils")
    fake_utils.__path__ = []
    fake_tool_schema = types.ModuleType("grc.utils.tool_schema")
    fake_tool_schema.tool_map_from_tools_payload = lambda _tools: {}
    sys.modules.update({
        "fastapi": fake_fastapi,
        "fastapi.responses": fake_responses,
        "httpx": fake_httpx,
        "yaml": fake_yaml,
        "grc": fake_grc,
        "grc.runtime": fake_runtime,
        "grc.runtime.engine": fake_engine,
        "grc.runtime.trace_store": fake_trace,
        "grc.utils": fake_utils,
        "grc.utils.tool_schema": fake_tool_schema,
    })
    return original_modules


def _restore_modules(original_modules: Dict[str, Any]) -> None:
    for name, original in original_modules.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


def _temporary_env(updates: Dict[str, str]) -> Dict[str, Any]:
    old = {}
    for key, value in updates.items():
        old[key] = os.environ.get(key)
        os.environ[key] = value
    return old


def _restore_env(old: Dict[str, Any]) -> None:
    for key, value in old.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _proxy_prepared_capture() -> Dict[str, Any]:
    _FakeRuleEngine.apply_request_called = False
    _FakeTraceStore.write_called = False
    _FakeAsyncClient.capture = {}
    original_modules = _install_proxy_import_stubs()
    old_env = _temporary_env({
        "GRC_UPSTREAM_PROFILE": "novacode",
        "GRC_UPSTREAM_BASE_URL": "http://capture.invalid/v1",
        "GRC_UPSTREAM_API_KEY_ENV": "CHUANGZHI_API_KEY",
        "CHUANGZHI_API_KEY": "synthetic-proxy-token",
        "GRC_PROXY_RESPONSES_TOOL_SHAPE_DIRECT_ALIGNMENT": "1",
    })
    try:
        spec = importlib.util.spec_from_file_location("proxy_wire_fingerprint_capture_module", REPO_ROOT / PROXY_SOURCE)
        if spec is None or spec.loader is None:
            raise RuntimeError("proxy module spec unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        app = module.create_app("configs/runtime_bfcl_structured.yaml", "rules/baseline_empty", "/tmp/proxy-wire-fingerprint-fake-traces")
        handler = app.routes[("POST", "/v1/responses")]
        asyncio.run(handler(_FakeRequest(_responses_payload())))
    finally:
        _restore_env(old_env)
        _restore_modules(original_modules)
    prepared = _FakeAsyncClient.capture.get("prepared_request")
    if prepared is None:
        return {
            "client_stack_label": "unknown",
            "method_label": "unknown",
            "url_suffix_label": "unknown",
            "wire_request_target_label": "unknown",
            "header_names": set(),
            "header_name_set_label": "unknown",
            "body_nonzero": False,
            "timeout": None,
            "trust_env": None,
            "http2": None,
        }
    return {
        "client_stack_label": "httpx_async_client",
        "method_label": "post" if prepared.method == "POST" else "unknown",
        "url_suffix_label": _suffix_label(prepared.url),
        "wire_request_target_label": _target_label(prepared.url),
        "header_names": prepared.header_names,
        "header_name_set_label": _header_name_label(prepared.header_names),
        "body_nonzero": prepared.body_nonzero,
        "timeout": prepared.timeout,
        "trust_env": prepared.trust_env,
        "http2": prepared.http2,
    }


def build_diff_record() -> Dict[str, Any]:
    direct = _direct_prepared_capture()
    proxy = _proxy_prepared_capture()
    direct_headers = direct.get("header_names", set())
    proxy_headers = proxy.get("header_names", set())
    body_shape = "both_compact_json_nonzero" if direct.get("body_nonzero") and proxy.get("body_nonzero") else "mismatch_or_not_observed"
    content_length_label = "both_nonzero" if direct.get("body_nonzero") and proxy.get("body_nonzero") else "missing"
    default_shape = "proxy_httpx_defaults_present_direct_not_observed" if HTTPX_DEFAULT_HEADER_NAMES.issubset(proxy_headers) and not (HTTPX_DEFAULT_HEADER_NAMES & direct_headers) else "not_observed"
    transfer_label = "present" if "transfer-encoding" in proxy_headers else "absent"
    cause = "httpx_default_header_context_diff" if default_shape == "proxy_httpx_defaults_present_direct_not_observed" else "none_observed"
    timeout_label = "proxy_config_timeout_direct_urllib_timeout" if proxy.get("timeout") == 120 and direct.get("timeout") == 30 else "not_observed"
    record = _base_record(command_executed=True)
    record.update({
        "direct_client_stack_label": direct["client_stack_label"],
        "proxy_client_stack_label": proxy["client_stack_label"],
        "method_label": "post" if direct.get("method_label") == proxy.get("method_label") == "post" else "unknown",
        "url_suffix_label": "chat_completions_suffix" if direct.get("url_suffix_label") == proxy.get("url_suffix_label") == "chat_completions_suffix" else "unknown",
        "wire_request_target_label": "chat_completions_target" if direct.get("wire_request_target_label") == proxy.get("wire_request_target_label") == "chat_completions_target" else "unknown",
        "header_name_set_label": proxy["header_name_set_label"],
        "direct_header_name_set_label": direct["header_name_set_label"],
        "default_header_shape_label": default_shape,
        "wire_user_agent_label": _presence_diff(proxy_headers, direct_headers, "user-agent"),
        "wire_accept_label": _presence_diff(proxy_headers, direct_headers, "accept"),
        "wire_accept_encoding_label": _presence_diff(proxy_headers, direct_headers, "accept-encoding"),
        "wire_connection_label": _presence_diff(proxy_headers, direct_headers, "connection"),
        "content_length_shape_label": content_length_label,
        "transfer_encoding_label": transfer_label,
        "body_bytes_shape_match_label": body_shape,
        "proxy_env_presence_label": _proxy_env_presence_label(),
        "trust_env_label": "true" if proxy.get("trust_env") is True else ("false" if proxy.get("trust_env") is False else "not_observed"),
        "http2_config_label": "true" if proxy.get("http2") is True else ("false" if proxy.get("http2") is False else "not_observed"),
        "timeout_shape_label": timeout_label,
        "tls_context_source_label": "not_observed",
        "suspected_403_cause_label": cause,
    })
    return record


def _write_artifact(record: Dict[str, Any], output_artifact: Path) -> None:
    payload = {
        "artifact_kind": "bfcl_proxy_wire_fingerprint_diff_compact",
        "compact_schema_version": "proxy_wire_fingerprint_diff_v1",
        "measurement_kind": "compact_offline_proxy_prepared_request_wire_fingerprint_diff",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "provider_call_executed": False,
        "proxy_live_request_executed": False,
        "profile_sourced_summary": False,
        "bfcl_generate_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "source_collection_executed": False,
        "source_diagnostics_executed": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "raw_outputs_committed": False,
        "records": [{field: record.get(field) for field in REQUIRED_COMPACT_FIELDS}],
    }
    output_artifact.parent.mkdir(parents=True, exist_ok=True)
    output_artifact.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _blocked_summary(blockers: List[str]) -> Dict[str, Any]:
    return {
        "report_scope": "bfcl_proxy_wire_fingerprint_diff_execute",
        **_base_record(command_executed=False),
        "output_artifact": None,
        "blockers": sorted(set(blockers)),
    }


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> Dict[str, Any]:
    packet_summary = check_packet(packet_path)
    return {
        "report_scope": "bfcl_proxy_wire_fingerprint_diff_plan",
        "packet_path": str(packet_path),
        "output_artifact_planned": str(output_artifact),
        "approval_status": packet_summary.get("approval_status"),
        "authorized": packet_summary.get("authorized"),
        "planned_attempt_count": 1,
        "compact_only": True,
        "synthetic_probe_only": True,
        "compact_fields": list(REQUIRED_COMPACT_FIELDS),
        **_base_record(command_executed=False),
        "blockers": list(packet_summary.get("blockers", [])),
    }


def execute_wire_fingerprint_diff(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> Dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved" or packet_summary.get("authorized") is not True:
        blockers.append("wire_fingerprint_diff_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    if blockers:
        return _blocked_summary(blockers)
    record = build_diff_record()
    _write_artifact(record, output_artifact)
    artifact_summary = check_artifact(output_artifact)
    summary = {
        "report_scope": "bfcl_proxy_wire_fingerprint_diff_execute",
        **record,
        "output_artifact": str(output_artifact),
        "artifact_check_passed": artifact_summary.get("bfcl_proxy_wire_fingerprint_diff_artifact_passed"),
        "blockers": list(artifact_summary.get("blockers", [])),
    }
    return summary


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--execute-wire-fingerprint-diff", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_wire_fingerprint_diff:
        summary = execute_wire_fingerprint_diff(args.packet, args.output_artifact)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    if args.strict and args.execute_wire_fingerprint_diff and not summary.get("artifact_check_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
