#!/usr/bin/env python3
"""Signed one-ID BFCL live-shape telemetry capture boundary.

The capture factory validates the reviewed one-ID scope, requires explicit
stage observations, and returns a compact record for the telemetry runner.
Without instrumentation for every reviewed stage, it fails closed instead of
inferring provider/proxy/BFCL state from the final result file.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from scripts.check_bfcl_one_id_live_shape_telemetry_gate import ALLOWED_TELEMETRY_FIELDS, SIGNED_IDS
from scripts.run_bfcl_exact_2id_generate_smoke import (
    BFCL_MODEL_ALIAS,
    REPO_ROOT,
    RUNTIME_CONFIG,
    RULES_DIR,
    _assert_generate_only_command,
    _bfcl_generate_subprocess_env,
    _classify_result_for_run_id,
    _python,
    _start_proxy,
    _sync_fixture_env,
)

SIGNED_ROUTE_PROFILE = "novacode"
SIGNED_ROUTE_MODEL = "gpt-4.1"
SIGNED_CATEGORY = "web_search_base"
SIGNED_ID_MANIFEST = {SIGNED_CATEGORY: [SIGNED_IDS[0]]}
LiveExecutor = Callable[[dict[str, Any]], dict[str, Any]]

REQUEST_SHAPE_FIELDS = (
    "local_proxy_endpoint_path_label",
    "bfcl_handler_class_label",
    "bfcl_api_path_label",
    "request_shape_hash",
    "request_message_count_bucket",
    "request_has_instructions",
    "request_has_tools",
    "request_tool_count",
    "request_tool_choice_shape",
    "request_token_field_shape",
)
STAGE_FIELDS = (
    "provider_status_class",
    "provider_response_empty_bool",
    "provider_response_has_choices",
    "provider_response_has_message",
    "provider_response_has_tool_calls",
    "provider_response_has_nonempty_text",
    "protocol_exception_observed",
    "engine_apply_response_called",
    "engine_final_has_tool_calls",
    "engine_final_has_nonempty_text",
    "engine_final_content_empty",
    "engine_coerced_nonempty_text_to_empty",
    "proxy_responses_output_has_function_call",
    "proxy_responses_output_has_nonempty_text",
    "bfcl_parse_called",
    "bfcl_parse_model_response_empty",
    "bfcl_decode_execute_called",
    "bfcl_decode_execute_nonempty",
    "result_file_written",
    "result_file_contains_nonempty_shape",
    "compact_classifier_status",
    "classifier_false_empty_for_nonempty_result",
    "protocol_exception_converted_to_empty_model_response",
)
REQUIRED_OBSERVED_FIELDS = REQUEST_SHAPE_FIELDS + STAGE_FIELDS
REQUIRED_OBSERVED_GROUPS = (
    ("request_shape", REQUEST_SHAPE_FIELDS),
    (
        "provider_upstream_response",
        (
            "provider_status_class",
            "provider_response_empty_bool",
            "provider_response_has_choices",
            "provider_response_has_message",
            "provider_response_has_tool_calls",
            "provider_response_has_nonempty_text",
            "protocol_exception_observed",
        ),
    ),
    (
        "runtime_engine_apply_response",
        (
            "engine_apply_response_called",
            "engine_final_has_tool_calls",
            "engine_final_has_nonempty_text",
            "engine_final_content_empty",
            "engine_coerced_nonempty_text_to_empty",
        ),
    ),
    (
        "chat_to_responses_proxy_output",
        (
            "proxy_responses_output_has_function_call",
            "proxy_responses_output_has_nonempty_text",
        ),
    ),
    (
        "bfcl_parse_decode",
        (
            "bfcl_parse_called",
            "bfcl_parse_model_response_empty",
            "bfcl_decode_execute_called",
            "bfcl_decode_execute_nonempty",
        ),
    ),
    (
        "result_materialization_classifier",
        (
            "result_file_written",
            "result_file_contains_nonempty_shape",
            "compact_classifier_status",
            "classifier_false_empty_for_nonempty_result",
            "protocol_exception_converted_to_empty_model_response",
        ),
    ),
)
RAW_KEY_RE = re.compile(r"(^|_)(raw|prompt|case_content|provider_payload|provider_request_body|response_body|headers|logs|traces|model_output_text|tool_arguments|gold|reference|expected|scorer_diff|candidate_output|endpoint_value|api_key_value)(_|$)", re.IGNORECASE)
FORBIDDEN_VALUE_RE = re.compile(("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz" + "|" + "boyue" + "richdata"), re.IGNORECASE)


def _request_blockers(request: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if request.get("run_ids") != SIGNED_IDS:
        blockers.append(f"one_id_capture_run_ids_not_signed:{request.get('run_ids')!r}")
    if request.get("route_profile") != SIGNED_ROUTE_PROFILE:
        blockers.append(f"one_id_capture_route_profile_drift:{request.get('route_profile')!r}")
    if request.get("route_model") != SIGNED_ROUTE_MODEL:
        blockers.append(f"one_id_capture_route_model_drift:{request.get('route_model')!r}")
    if request.get("generate_only") is not True:
        blockers.append(f"one_id_capture_generate_only_not_true:{request.get('generate_only')!r}")
    if request.get("raw_persistence_authorized") is not False:
        blockers.append(f"one_id_capture_raw_persistence_not_false:{request.get('raw_persistence_authorized')!r}")
    return blockers


def _manifest_target() -> Path:
    from bfcl_eval.constants import eval_config

    return Path(eval_config.TEST_IDS_TO_GENERATE_PATH)


@contextlib.contextmanager
def _temporary_one_id_manifest(path: Path | None = None):
    target = path or _manifest_target()
    backup = target.read_bytes() if target.exists() else None
    existed = target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(SIGNED_ID_MANIFEST, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        yield target
    finally:
        if existed and backup is not None:
            target.write_bytes(backup)
        else:
            target.unlink(missing_ok=True)


@contextlib.contextmanager
def _temporary_run_root(prefix: str = "bfcl_one_id_live_shape_telemetry_"):
    root = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _audit_run_root_cleaned(run_root: Path) -> dict[str, bool]:
    return {"temp_run_root_absent": not run_root.exists()}


def _scan_raw_or_secret(value: Any, path: tuple[str, ...] = ()) -> list[str]:
    blockers: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if RAW_KEY_RE.search(str(key)):
                blockers.append(f"one_id_capture_raw_or_secret_key:{'.'.join(path + (str(key),))}")
            blockers.extend(_scan_raw_or_secret(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            blockers.extend(_scan_raw_or_secret(child, path + (str(index),)))
    elif isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
        blockers.append(f"one_id_capture_endpoint_or_key_literal:{'.'.join(path)}")
    return blockers


def _missing_instrumentation(record: dict[str, Any]) -> list[str]:
    missing_groups: list[str] = []
    for group_name, fields in REQUIRED_OBSERVED_GROUPS:
        if any(field not in record for field in fields):
            missing_groups.append(group_name)
    return missing_groups


def _derive_stage(record: dict[str, Any]) -> str:
    provider_status = str(record.get("provider_status_class") or "")
    if record.get("protocol_exception_observed") is True:
        return "protocol_exception" if provider_status == "protocol_exception" else "provider_protocol_error"
    if provider_status != "2xx":
        return "provider_protocol_error"
    provider_empty = record.get("provider_response_empty_bool") is True
    provider_tool = record.get("provider_response_has_tool_calls") is True
    provider_text = record.get("provider_response_has_nonempty_text") is True
    engine_tool = record.get("engine_final_has_tool_calls") is True
    engine_empty = record.get("engine_final_content_empty") is True
    engine_coerced = record.get("engine_coerced_nonempty_text_to_empty") is True
    response_function = record.get("proxy_responses_output_has_function_call") is True
    response_text = record.get("proxy_responses_output_has_nonempty_text") is True
    parse_called = record.get("bfcl_parse_called") is True
    parse_empty = record.get("bfcl_parse_model_response_empty") is True
    decode_called = record.get("bfcl_decode_execute_called") is True
    decode_nonempty = record.get("bfcl_decode_execute_nonempty") is True
    result_written = record.get("result_file_written") is True
    result_nonempty = record.get("result_file_contains_nonempty_shape") is True
    false_empty = record.get("classifier_false_empty_for_nonempty_result") is True
    compact_status = record.get("compact_classifier_status")
    if provider_empty and not provider_tool and not provider_text:
        return "provider_true_empty"
    if provider_text and not provider_tool and engine_empty and engine_coerced:
        return "engine_text_coercion"
    if provider_text and not provider_tool:
        return "provider_text_no_tool"
    if provider_tool and not engine_tool:
        return "proxy_engine_tool_loss"
    if engine_tool and not response_function:
        return "responses_envelope_loss"
    if (response_function or response_text) and (not parse_called or parse_empty or not decode_called or not decode_nonempty):
        return "bfcl_parse_decode_loss"
    if decode_nonempty and (not result_written or not result_nonempty or false_empty or compact_status == "empty_model_response"):
        return "materialization_classifier_loss"
    if decode_nonempty and result_written and result_nonempty and not false_empty:
        return "live_path_nonempty"
    return "bfcl_parse_decode_loss"


def _normalize_observed_record(observed: dict[str, Any]) -> dict[str, Any]:
    raw_blockers = _scan_raw_or_secret(observed)
    if raw_blockers:
        raise RuntimeError(";".join(raw_blockers))
    missing = _missing_instrumentation(observed)
    if missing:
        raise RuntimeError(f"live_shape_stage_not_instrumented:{missing[0]}")
    if observed.get("protocol_exception_converted_to_empty_model_response") is True:
        raise RuntimeError("live_shape_protocol_exception_converted_to_empty_forbidden")
    if (
        observed.get("compact_classifier_status") == "empty_model_response"
        and observed.get("provider_response_empty_bool") is not True
        and observed.get("provider_response_has_tool_calls") is not True
        and observed.get("provider_response_has_nonempty_text") is not True
        and observed.get("protocol_exception_observed") is not True
    ):
        raise RuntimeError("live_shape_empty_model_response_without_observed_upstream_empty")
    record = {field: observed[field] for field in ALLOWED_TELEMETRY_FIELDS if field in observed}
    record["run_id"] = SIGNED_IDS[0]
    record["route_profile"] = SIGNED_ROUTE_PROFILE
    record["route_model"] = SIGNED_ROUTE_MODEL
    record["suspected_live_failure_stage"] = _derive_stage(record)
    return record


def _content_text_present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_content_text_present(item) for item in value)
    if isinstance(value, dict):
        for key in ("text", "content", "input_text"):
            if _content_text_present(value.get(key)):
                return True
    return False


def _choices_message(response_json: dict[str, Any]) -> dict[str, Any]:
    choices = response_json.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict):
            return message
    return {}


def _status_class(status_code: Any) -> str:
    try:
        code = int(status_code)
    except (TypeError, ValueError):
        return "unknown"
    return f"{code // 100}xx" if code >= 100 else "unknown"


def _bucket_count(count: int) -> str:
    if count <= 0:
        return "zero"
    if count <= 3:
        return "one_to_three"
    if count <= 8:
        return "four_to_eight"
    return "more_than_eight"


def _tool_choice_shape(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, str):
        return f"{value}_string" if value in {"required", "auto", "none"} else "string"
    if isinstance(value, dict):
        function = value.get("function")
        if value.get("type") == "function" and isinstance(function, dict):
            return "function_object"
        return "object"
    return "other"


def _token_field_shape(request_json: dict[str, Any]) -> str:
    present = [field for field in ("max_output_tokens", "max_tokens", "max_completion_tokens") if field in request_json]
    return "+".join(present) if present else "none"


def _request_shape_hash(parts: dict[str, Any]) -> str:
    encoded = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _shape_from_trace(trace: dict[str, Any]) -> dict[str, Any]:
    request = trace.get("request") if isinstance(trace.get("request"), dict) else {}
    original = trace.get("request_original") if isinstance(trace.get("request_original"), dict) else {}
    messages = request.get("messages") if isinstance(request.get("messages"), list) else []
    tools = request.get("tools") if isinstance(request.get("tools"), list) else []
    role_sequence = [str(item.get("role") or "unknown") for item in messages if isinstance(item, dict)]
    shape_parts = {
        "endpoint": trace.get("request_endpoint"),
        "roles": role_sequence,
        "tool_count": len(tools),
        "tool_choice": _tool_choice_shape(request.get("tool_choice")),
        "token_field": _token_field_shape(request),
    }
    return {
        "local_proxy_endpoint_path_label": "bfcl_generate_local_proxy_responses_v1" if trace.get("request_endpoint") == "/v1/responses" else "unexpected_proxy_endpoint",
        "bfcl_handler_class_label": "openai_responses_handler" if trace.get("request_endpoint") == "/v1/responses" else "unknown_handler",
        "bfcl_api_path_label": "responses" if trace.get("request_endpoint") == "/v1/responses" else "unknown",
        "request_shape_hash": _request_shape_hash(shape_parts),
        "request_message_count_bucket": _bucket_count(len(messages)),
        "request_has_instructions": bool(original.get("instructions")) or any(role in {"system", "developer"} for role in role_sequence),
        "request_has_tools": bool(tools),
        "request_tool_count": len(tools),
        "request_tool_choice_shape": _tool_choice_shape(request.get("tool_choice")),
        "request_token_field_shape": _token_field_shape(request),
    }


def _provider_observation_from_trace(trace: dict[str, Any]) -> dict[str, Any]:
    raw_response = trace.get("raw_response") if isinstance(trace.get("raw_response"), dict) else {}
    message = _choices_message(raw_response)
    choices = raw_response.get("choices")
    has_choices = isinstance(choices, list) and bool(choices)
    has_message = bool(message)
    has_tool_calls = isinstance(message.get("tool_calls"), list) and bool(message.get("tool_calls"))
    has_text = _content_text_present(message.get("content"))
    status_class = _status_class(trace.get("status_code"))
    protocol_exception = str(trace.get("status_code")) == "protocol_exception"
    provider_protocol_error = protocol_exception or status_class != "2xx"
    return {
        "provider_status_class": "protocol_exception" if protocol_exception else status_class,
        "provider_response_empty_bool": not provider_protocol_error and has_choices and has_message and not has_tool_calls and not has_text,
        "provider_response_has_choices": has_choices,
        "provider_response_has_message": has_message,
        "provider_response_has_tool_calls": has_tool_calls,
        "provider_response_has_nonempty_text": has_text,
        "protocol_exception_observed": provider_protocol_error,
    }


def _engine_observation_from_trace(trace: dict[str, Any]) -> dict[str, Any]:
    final_chat = trace.get("final_chat_response") if isinstance(trace.get("final_chat_response"), dict) else None
    if final_chat is None:
        final_chat = trace.get("final_response") if isinstance(trace.get("final_response"), dict) else {}
    message = _choices_message(final_chat)
    tool_calls = message.get("tool_calls") if isinstance(message.get("tool_calls"), list) else []
    has_text = _content_text_present(message.get("content"))
    validation = trace.get("validation") if isinstance(trace.get("validation"), dict) else {}
    repairs = validation.get("repair_kinds") or []
    if not isinstance(repairs, list):
        repairs = []
    return {
        "engine_apply_response_called": isinstance(trace.get("validation"), dict),
        "engine_final_has_tool_calls": bool(tool_calls),
        "engine_final_has_nonempty_text": has_text,
        "engine_final_content_empty": not bool(tool_calls) and not has_text,
        "engine_coerced_nonempty_text_to_empty": "coerce_no_tool_text_to_empty" in {str(item) for item in repairs},
    }


def _responses_output_observation_from_trace(trace: dict[str, Any]) -> dict[str, Any]:
    final_response = trace.get("final_response") if isinstance(trace.get("final_response"), dict) else {}
    output = final_response.get("output") if isinstance(final_response.get("output"), list) else []
    has_function_call = any(isinstance(item, dict) and item.get("type") == "function_call" for item in output)
    has_text = any(isinstance(item, dict) and item.get("type") == "message" and _content_text_present(item.get("content")) for item in output)
    return {
        "proxy_responses_output_has_function_call": has_function_call,
        "proxy_responses_output_has_nonempty_text": has_text,
    }


def _load_latest_trace(trace_dir: Path) -> dict[str, Any]:
    traces = sorted(trace_dir.glob("*.json"), key=lambda path: path.stat().st_mtime)
    if not traces:
        raise RuntimeError("live_shape_stage_not_instrumented:provider_upstream_response")
    try:
        data = json.loads(traces[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("live_shape_stage_not_instrumented:provider_upstream_response") from exc
    if not isinstance(data, dict):
        raise RuntimeError("live_shape_stage_not_instrumented:provider_upstream_response")
    return data


def _result_files_for_run_id(run_id: str, result_root: Path) -> list[Path]:
    files: list[Path] = []
    if not result_root.exists():
        return files
    for path in result_root.rglob("*.json"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if run_id in text:
            files.append(path)
    return files


def _walk_json(value: Any) -> list[Any]:
    items = [value]
    if isinstance(value, dict):
        for child in value.values():
            items.extend(_walk_json(child))
    elif isinstance(value, list):
        for child in value:
            items.extend(_walk_json(child))
    return items


def _result_observation(run_id: str, result_root: Path) -> dict[str, Any]:
    classification = _classify_result_for_run_id(run_id, result_root)
    files = _result_files_for_run_id(run_id, result_root)
    parsed: list[Any] = []
    raw_text = ""
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            raw_text += "\n" + text[:20000]
            parsed.append(json.loads(text))
        except (OSError, json.JSONDecodeError):
            continue
    nodes = [node for payload in parsed for node in _walk_json(payload)]
    keys = {str(key) for node in nodes if isinstance(node, dict) for key in node}
    lowered = raw_text.lower()
    status = str(classification.get("status") or "missing_result")
    tool_or_text_nonempty = bool(classification.get("tool_call_detected") or classification.get("no_tool_text_recorded"))
    decode_called = bool({"model_response_decoded", "model_responses_decoded"} & keys) or "model_response_decoded" in lowered
    parse_called = bool({"model_response", "model_responses", "model_response_decoded", "model_responses_decoded", "content"} & keys) or bool(files)
    decode_nonempty = bool(classification.get("tool_call_detected"))
    return {
        "bfcl_parse_called": parse_called,
        "bfcl_parse_model_response_empty": status == "empty_model_response",
        "bfcl_decode_execute_called": decode_called or status == "empty_model_response",
        "bfcl_decode_execute_nonempty": decode_nonempty,
        "result_file_written": bool(files),
        "result_file_contains_nonempty_shape": tool_or_text_nonempty,
        "compact_classifier_status": status,
        "classifier_false_empty_for_nonempty_result": tool_or_text_nonempty and status == "empty_model_response",
        "protocol_exception_converted_to_empty_model_response": bool(classification.get("protocol_error_detected")) and status == "empty_model_response",
    }


def _one_id_generate_command(run_root: Path) -> list[str]:
    command = [
        _python(),
        str(REPO_ROOT / "scripts/run_bfcl_cli.py"),
        "generate",
        "--model",
        os.environ.get("GRC_BFCL_MODEL", BFCL_MODEL_ALIAS),
        "--skip-server-setup",
        "--num-threads",
        os.environ.get("GRC_BFCL_NUM_THREADS", "1"),
        "--result-dir",
        str(run_root / "bfcl/result"),
        "--allow-overwrite",
        "--run-ids",
        "--test-category",
        SIGNED_CATEGORY,
    ]
    _assert_generate_only_command(command)
    return command


def _write_one_id_run_ids(run_root: Path) -> Path:
    path = run_root / "bfcl/test_case_ids_to_generate.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(SIGNED_ID_MANIFEST, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _terminate_proxy(proc: Any) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def _default_live_executor(request: dict[str, Any]) -> dict[str, Any]:
    run_root = Path(str(request.get("run_root") or tempfile.mkdtemp(prefix="bfcl_one_id_live_shape_telemetry_exec_")))
    port = int(request.get("port") or os.environ.get("GRC_ONE_ID_LIVE_SHAPE_PORT") or 8131)
    trace_dir = run_root / "traces"
    runtime_config = REPO_ROOT / RUNTIME_CONFIG
    rules_dir = REPO_ROOT / RULES_DIR
    _write_one_id_run_ids(run_root)
    _sync_fixture_env(run_root, port)
    proxy_proc = None
    try:
        with _temporary_one_id_manifest():
            proxy_proc = _start_proxy(port, trace_dir, runtime_config, rules_dir, run_root / "proxy.log")
            command = _one_id_generate_command(run_root)
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                env=_bfcl_generate_subprocess_env(port),
                check=False,
            )
        trace = _load_latest_trace(trace_dir)
        observed = {}
        observed.update(_shape_from_trace(trace))
        observed.update(_provider_observation_from_trace(trace))
        observed.update(_engine_observation_from_trace(trace))
        observed.update(_responses_output_observation_from_trace(trace))
        observed.update(_result_observation(SIGNED_IDS[0], run_root / "bfcl/result"))
        if completed.returncode != 0 and observed.get("protocol_exception_observed") is not True and observed.get("result_file_written") is not True:
            raise RuntimeError("live_shape_stage_not_instrumented:bfcl_parse_decode")
        return observed
    finally:
        _terminate_proxy(proxy_proc)


def build_signed_one_id_live_shape_capture(request: dict[str, Any], *, executor: LiveExecutor | None = None) -> LiveExecutor:
    blockers = _request_blockers(request)
    if blockers:
        raise RuntimeError(";".join(blockers))
    selected_executor = executor or _default_live_executor

    def _capture(capture_request: dict[str, Any]) -> dict[str, Any]:
        blockers_inner = _request_blockers(capture_request)
        if blockers_inner:
            raise RuntimeError(";".join(blockers_inner))
        with _temporary_run_root() as run_root:
            capture_with_root = dict(capture_request)
            capture_with_root["run_root"] = str(run_root)
            try:
                observed = selected_executor(capture_with_root)
                if not isinstance(observed, dict):
                    raise RuntimeError("one_id_capture_record_not_object")
                return _normalize_observed_record(observed)
            finally:
                pass
        # Unreachable, but keeps static analyzers aware the context cleans up.

    return _capture
