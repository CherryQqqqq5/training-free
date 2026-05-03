#!/usr/bin/env python3
"""Run an offline compact proxy transport/request capture diff."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_proxy_transport_request_capture_diff_artifact import check as check_artifact
from scripts.check_bfcl_proxy_transport_request_capture_diff_gate import DEFAULT_PACKET, REQUIRED_COMPACT_FIELDS, check as check_packet
from scripts.run_bfcl_proxy_responses_tool_shape import _responses_payload

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_transport_request_capture_diff_compact.json")
PROXY_SOURCE = Path("src/grc/runtime/proxy.py")


def _select_proxy_python_label() -> str:
    if os.environ.get("GRC_PYTHON"):
        return "grc_python_env"
    repo_venv = REPO_ROOT / ".venv" / "bin" / "python"
    if repo_venv.is_file() and os.access(str(repo_venv), os.X_OK):
        return "repo_venv"
    return "caller_python"


def _base_record(*, command_executed: bool = False) -> dict[str, Any]:
    return {
        "preflight_command_executed": command_executed,
        "provider_call_started": False,
        "profile_sourced": False,
        "proxy_live_request_started": False,
        "fake_transport_capture_used": command_executed,
        "raw_outputs_committed": False,
        "raw_temp_outputs_removed": command_executed,
        "transport_client_label": "unknown",
        "client_stack_label": "unknown",
        "body_submission_label": "unknown",
        "json_serialization_label": "unknown",
        "content_type_header_label": "unknown",
        "authorization_header_label": "unknown",
        "auth_scheme_label": "unknown",
        "extra_header_shape_label": "unknown",
        "provider_header_shape_label": "unknown",
        "url_join_label": "unknown",
        "request_target_suffix_label": "unknown",
        "timeout_shape_label": "unknown",
        "payload_shape_match_label": "unknown",
        "payload_shape_label": "unknown",
        "selected_base_url_env_label": "unknown",
        "selected_api_key_env_label": "unknown",
        "proxy_python_label": _select_proxy_python_label(),
        "suspected_403_cause_label": "unknown",
        "direct_transport_client_label": "unknown",
        "direct_body_submission_label": "unknown",
        "direct_json_serialization_label": "unknown",
        "direct_timeout_shape_label": "unknown",
        "direct_header_shape_label": "unknown",
        "bfcl_generate_started": False,
        "bfcl_evaluate_started": False,
        "scorer_started": False,
        "full_baseline_executed": False,
        "candidate_specs_inert": True,
        "source_collection_executed": False,
        "source_diagnostics_executed": False,
        "performance_evidence": False,
        "stop_gate_triggered": "none" if not command_executed else "stopped_after_fake_transport_capture",
        "preflight_failed_check_label": "none_observed",
    }


def _header_shape(has_auth: bool, has_content_type: bool, extra_shape: str) -> str:
    if has_auth and has_content_type and extra_shape == "none":
        return "authorization_content_type_only"
    if has_auth and has_content_type:
        return "authorization_content_type_extra"
    if not has_auth:
        return "missing_authorization"
    if not has_content_type:
        return "missing_content_type"
    return "unknown"


def _headers_to_name_map(headers: Any) -> dict[str, str]:
    if not isinstance(headers, dict):
        return {}
    return {str(key).lower(): str(value) for key, value in headers.items()}


def _extra_header_shape(header_names: set[str]) -> str:
    extra = header_names - {"authorization", "content-type"}
    if not extra:
        return "none"
    if extra.intersection({"http-referer", "x-title"}):
        return "referer_or_title_possible"
    return "other_extra"


def _payload_shape_label(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "unknown"
    messages = payload.get("messages")
    tools = payload.get("tools")
    tool_choice = payload.get("tool_choice")
    if not isinstance(messages, list) or len(messages) != 1 or not isinstance(messages[0], dict) or messages[0].get("role") != "user":
        return "chat_tool_shape_drift"
    if payload.get("model") != "gpt-4.1" or payload.get("temperature") != 0 or payload.get("max_tokens") != 16:
        return "chat_tool_shape_drift"
    if not isinstance(tools, list) or len(tools) != 1 or not isinstance(tools[0], dict):
        return "chat_tool_shape_drift"
    function = tools[0].get("function") if isinstance(tools[0].get("function"), dict) else {}
    if tools[0].get("type") != "function" or not function.get("name"):
        return "chat_tool_shape_drift"
    if not isinstance(tool_choice, dict) or tool_choice.get("type") != "function":
        return "chat_tool_shape_drift"
    choice_function = tool_choice.get("function") if isinstance(tool_choice.get("function"), dict) else {}
    if choice_function.get("name") != function.get("name"):
        return "chat_tool_shape_drift"
    return "chat_tool_direct_aligned"


def _direct_transport_capture_actual() -> dict[str, str]:
    import scripts.run_bfcl_live_provider_preflight as direct_runner

    captured: dict[str, Any] = {}

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
            "synthetic-direct-key",
            direct_runner._chat_tool_payload(),
        )
    finally:
        direct_runner.urllib.request.urlopen = original_urlopen

    request = captured.get("request")
    header_items = dict(request.header_items()) if request is not None else {}
    header_map = {str(key).lower(): str(value) for key, value in header_items.items()}
    header_names = set(header_map)
    has_auth = "authorization" in header_names
    has_content_type = "content-type" in header_names
    extra_shape = _extra_header_shape(header_names)
    data = getattr(request, "data", None)
    target = getattr(request, "full_url", "")
    return {
        "transport_client_label": "urllib_request",
        "client_stack_label": "direct_urllib_manual_bytes",
        "body_submission_label": "urllib_data_bytes" if isinstance(data, (bytes, bytearray)) else "unknown",
        "json_serialization_label": "manual_json_compact_bytes" if isinstance(data, (bytes, bytearray)) else "unknown",
        "content_type_header_label": "present" if has_content_type else "missing",
        "authorization_header_label": "present" if has_auth else "missing",
        "auth_scheme_label": "bearer" if header_map.get("authorization", "").lower().startswith("bearer ") else "missing",
        "extra_header_shape_label": extra_shape,
        "provider_header_shape_label": _header_shape(has_auth, has_content_type, extra_shape),
        "url_join_label": "direct_target_url_supplied",
        "request_target_suffix_label": "chat_completions_suffix" if str(target).endswith("/chat/completions") else "unknown",
        "timeout_shape_label": "urllib_timeout_30" if captured.get("timeout") == 30 else "unknown",
        "payload_shape_label": "chat_tool_direct_aligned" if isinstance(data, (bytes, bytearray)) else "unknown",
    }


class _FakeFastAPI:
    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], Any] = {}

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
    def __init__(self, status_code: int | None = None, detail: str | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _FakeJSONResponse:
    def __init__(self, content: Any = None, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code


class _FakeRequest:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def json(self) -> dict[str, Any]:
        return self._payload


class _FakeRuleEngine:
    apply_request_called = False

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def apply_request(self, request_json: dict[str, Any]) -> tuple[dict[str, Any], list[Any]]:
        type(self).apply_request_called = True
        return request_json, []

    def apply_response(self, request_json: dict[str, Any], raw_json: dict[str, Any], request_patches: list[Any] | None = None) -> tuple[dict[str, Any], list[Any], Any]:
        class Validation:
            def model_dump(self, mode: str = "json") -> dict[str, Any]:
                return {"issues": [], "rule_hits": [], "request_patches": []}
        return raw_json, [], Validation()


class _FakeTraceStore:
    write_called = False

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def write(self, _payload: dict[str, Any]) -> None:
        type(self).write_called = True


def _install_proxy_import_stubs(capture: dict[str, Any]) -> dict[str, Any]:
    original_modules = {name: sys.modules.get(name) for name in (
        "fastapi",
        "fastapi.responses",
        "httpx",
        "yaml",
        "grc",
        "grc.runtime",
        "grc.runtime.engine",
        "grc.runtime.trace_store",
        "grc.utils",
        "grc.utils.tool_schema",
    )}

    fake_fastapi = types.ModuleType("fastapi")
    fake_fastapi.FastAPI = _FakeFastAPI
    fake_fastapi.HTTPException = _FakeHTTPException
    fake_fastapi.Request = _FakeRequest
    fake_responses = types.ModuleType("fastapi.responses")
    fake_responses.JSONResponse = _FakeJSONResponse

    fake_httpx = types.ModuleType("httpx")

    class FakeAsyncClient:
        def __init__(self, timeout: Any = None) -> None:
            capture["timeout"] = timeout

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> bool:
            return False

        async def post(self, url: str, **kwargs: Any) -> Any:
            capture["url_suffix_chat"] = str(url).endswith("/chat/completions")
            capture["headers"] = kwargs.get("headers")
            capture["json"] = kwargs.get("json")
            capture["has_json_kwarg"] = "json" in kwargs
            capture["has_content_kwarg"] = "content" in kwargs
            capture["has_data_kwarg"] = "data" in kwargs
            content = kwargs.get("content")
            if isinstance(content, (bytes, bytearray)):
                try:
                    decoded = json.loads(bytes(content).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    decoded = None
                if isinstance(decoded, dict):
                    capture["json"] = decoded

            class FakeResponse:
                status_code = 200

                def json(self) -> dict[str, Any]:
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

    fake_httpx.AsyncClient = FakeAsyncClient

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

    replacements = {
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
    }
    sys.modules.update(replacements)
    return original_modules


def _restore_modules(original_modules: dict[str, Any]) -> None:
    for name, original in original_modules.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


def _temporary_env(updates: dict[str, str]) -> dict[str, str | None]:
    old: dict[str, str | None] = {}
    for key, value in updates.items():
        old[key] = os.environ.get(key)
        os.environ[key] = value
    return old


def _restore_env(old: dict[str, str | None]) -> None:
    for key, value in old.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _load_proxy_module_with_fake_transport(capture: dict[str, Any]) -> Any:
    original_modules = _install_proxy_import_stubs(capture)
    try:
        spec = importlib.util.spec_from_file_location("proxy_actual_capture_module", REPO_ROOT / PROXY_SOURCE)
        if spec is None or spec.loader is None:
            raise RuntimeError("proxy module spec unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, original_modules
    except Exception:
        _restore_modules(original_modules)
        raise


def _proxy_transport_capture_actual() -> dict[str, str]:
    capture: dict[str, Any] = {}
    _FakeRuleEngine.apply_request_called = False
    _FakeTraceStore.write_called = False
    module, original_modules = _load_proxy_module_with_fake_transport(capture)
    old_env = _temporary_env(
        {
            "GRC_UPSTREAM_PROFILE": "novacode",
            "GRC_UPSTREAM_BASE_URL": "http://capture.invalid/v1",
            "GRC_UPSTREAM_API_KEY_ENV": "CHUANGZHI_API_KEY",
            "CHUANGZHI_API_KEY": "synthetic-proxy-key",
            "GRC_PROXY_RESPONSES_TOOL_SHAPE_DIRECT_ALIGNMENT": "1",
        }
    )
    try:
        app = module.create_app("configs/runtime_bfcl_structured.yaml", "rules/baseline_empty", "/tmp/fake-traces-not-written")
        handler = app.routes[("POST", "/v1/responses")]
        asyncio.run(handler(_FakeRequest(_responses_payload())))
    finally:
        _restore_env(old_env)
        _restore_modules(original_modules)

    headers = _headers_to_name_map(capture.get("headers"))
    header_names = set(headers)
    has_auth = "authorization" in header_names
    has_content_type = "content-type" in header_names
    extra_shape = _extra_header_shape(header_names)
    payload = capture.get("json")
    if capture.get("has_json_kwarg"):
        body_submission = "httpx_json_kwarg"
        json_serialization = "httpx_json_parameter"
    elif capture.get("has_content_kwarg"):
        body_submission = "content_bytes"
        json_serialization = "manual_json_compact_bytes"
    elif capture.get("has_data_kwarg"):
        body_submission = "data_bytes"
        json_serialization = "manual_json_compact_bytes"
    else:
        body_submission = "unknown"
        json_serialization = "unknown"
    if capture.get("has_json_kwarg"):
        client_stack = "proxy_httpx_json_kwarg"
    elif capture.get("has_content_kwarg"):
        client_stack = "proxy_httpx_content_bytes"
    else:
        client_stack = "unknown"
    return {
        "transport_client_label": "httpx_async_client_post",
        "client_stack_label": client_stack,
        "body_submission_label": body_submission,
        "json_serialization_label": json_serialization,
        "content_type_header_label": "present" if has_content_type else "missing",
        "authorization_header_label": "present" if has_auth else "missing",
        "auth_scheme_label": "bearer" if headers.get("authorization", "").lower().startswith("bearer ") else "missing",
        "extra_header_shape_label": extra_shape,
        "provider_header_shape_label": _header_shape(has_auth, has_content_type, extra_shape),
        "url_join_label": "base_url_chat_completions_appended" if capture.get("url_suffix_chat") else "unknown",
        "request_target_suffix_label": "chat_completions_suffix" if capture.get("url_suffix_chat") else "unknown",
        "timeout_shape_label": "config_timeout_sec" if capture.get("timeout") == 120 else "unknown",
        "payload_shape_label": _payload_shape_label(payload),
        "selected_base_url_env_label": "GRC_UPSTREAM_BASE_URL",
        "selected_api_key_env_label": "CHUANGZHI_API_KEY",
        "engine_apply_request_label": "bypassed_for_exact_synthetic" if not _FakeRuleEngine.apply_request_called else "normal_policy_path",
        "trace_write_label": "in_memory_fake_trace_write" if _FakeTraceStore.write_called else "not_observed",
    }


def _payload_match_label(direct: dict[str, str], proxy: dict[str, str]) -> str:
    if direct.get("payload_shape_label") == proxy.get("payload_shape_label") == "chat_tool_direct_aligned":
        return "matched_direct_chat_tool_shape"
    if proxy.get("payload_shape_label") == "unknown":
        return "transport_only_payload_not_compared"
    return "mismatch"


def _suspected_cause(direct: dict[str, str], proxy: dict[str, str], payload_match: str) -> str:
    if proxy.get("provider_header_shape_label") != direct.get("provider_header_shape_label"):
        return "header_shape_drift"
    if payload_match not in {"matched_direct_chat_tool_shape", "transport_only_payload_not_compared"}:
        return "payload_shape_drift"
    if proxy.get("url_join_label") != "base_url_chat_completions_appended":
        return "url_join_or_provider_policy"
    if proxy.get("json_serialization_label") == direct.get("json_serialization_label"):
        return "transport_patch_ready" if proxy.get("transport_client_label") != direct.get("transport_client_label") else "none_observed"
    if proxy.get("transport_client_label") != direct.get("transport_client_label") or proxy.get("json_serialization_label") != direct.get("json_serialization_label"):
        return "transport_stack_or_serialization_drift"
    return "none_observed"


def build_diff_record() -> dict[str, Any]:
    direct = _direct_transport_capture_actual()
    proxy = _proxy_transport_capture_actual()
    payload_match = _payload_match_label(direct, proxy)
    record = _base_record(command_executed=True)
    record.update(
        {
            "transport_client_label": proxy["transport_client_label"],
            "client_stack_label": proxy["client_stack_label"],
            "body_submission_label": proxy["body_submission_label"],
            "json_serialization_label": proxy["json_serialization_label"],
            "content_type_header_label": proxy["content_type_header_label"],
            "authorization_header_label": proxy["authorization_header_label"],
            "auth_scheme_label": proxy["auth_scheme_label"],
            "extra_header_shape_label": proxy["extra_header_shape_label"],
            "provider_header_shape_label": proxy["provider_header_shape_label"],
            "url_join_label": proxy["url_join_label"],
            "request_target_suffix_label": proxy["request_target_suffix_label"],
            "timeout_shape_label": proxy["timeout_shape_label"],
            "payload_shape_match_label": payload_match,
            "payload_shape_label": proxy["payload_shape_label"],
            "selected_base_url_env_label": proxy["selected_base_url_env_label"],
            "selected_api_key_env_label": proxy["selected_api_key_env_label"],
            "direct_transport_client_label": direct["transport_client_label"],
            "direct_body_submission_label": direct["body_submission_label"],
            "direct_json_serialization_label": direct["json_serialization_label"],
            "direct_timeout_shape_label": direct["timeout_shape_label"],
            "direct_header_shape_label": direct["provider_header_shape_label"],
        }
    )
    record["suspected_403_cause_label"] = _suspected_cause(direct, proxy, payload_match)
    return record


def _write_artifact(record: dict[str, Any], output_artifact: Path) -> None:
    payload = {
        "artifact_kind": "bfcl_proxy_transport_request_capture_diff_compact",
        "compact_schema_version": "proxy_transport_request_capture_diff_v1",
        "measurement_kind": "compact_offline_proxy_transport_request_capture_diff",
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


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    return {
        "report_scope": "bfcl_proxy_transport_request_capture_diff_plan",
        "packet_path": str(packet_path),
        "output_artifact_planned": str(output_artifact),
        "approval_status": packet_summary.get("approval_status"),
        "authorized": packet_summary.get("authorized"),
        "provider_request_authorized": packet_summary.get("provider_request_authorized"),
        "proxy_live_request_authorized": packet_summary.get("proxy_live_request_authorized"),
        "profile_source_authorized": packet_summary.get("profile_source_authorized"),
        "compact_only": True,
        "offline_no_provider_only": True,
        "fake_transport_capture_required": True,
        "env_profile_sourced": False,
        "compact_fields": list(REQUIRED_COMPACT_FIELDS),
        **_base_record(command_executed=False),
        "blockers": list(packet_summary.get("blockers", [])),
    }


def execute_transport_capture_diff(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_proxy_transport_request_capture_diff_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("transport_capture_diff_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    if blockers:
        return {
            "report_scope": "bfcl_proxy_transport_request_capture_diff_execute",
            **_base_record(command_executed=False),
            "env_profile_sourced": False,
            "output_artifact": None,
            "blockers": sorted(set(blockers)),
        }
    record = build_diff_record()
    _write_artifact(record, output_artifact)
    artifact_summary = check_artifact(output_artifact)
    if not artifact_summary.get("bfcl_proxy_transport_request_capture_diff_artifact_passed"):
        blockers.extend(str(blocker) for blocker in artifact_summary.get("blockers", []))
    return {
        "report_scope": "bfcl_proxy_transport_request_capture_diff_execute",
        **record,
        "env_profile_sourced": False,
        "output_artifact": str(output_artifact),
        "blockers": sorted(set(blockers)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--execute-transport-capture-diff", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_transport_capture_diff and args.dry_run:
        summary = {"report_scope": "bfcl_proxy_transport_request_capture_diff_execute", "blockers": ["dry_run_and_execute_both_set"]}
    elif args.execute_transport_capture_diff:
        summary = execute_transport_capture_diff(args.packet, args.output_artifact)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
