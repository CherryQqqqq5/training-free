#!/usr/bin/env python3
"""Signed one-ID BFCL live-shape telemetry capture boundary.

The capture factory validates the reviewed one-ID scope, requires explicit
stage observations, and returns a compact record for the telemetry runner.
Without instrumentation for every reviewed stage, it fails closed instead of
inferring provider/proxy/BFCL state from the final result file.
"""

from __future__ import annotations

import contextlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from scripts.check_bfcl_one_id_live_shape_telemetry_gate import ALLOWED_TELEMETRY_FIELDS, SIGNED_IDS

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
    return [field for field in REQUIRED_OBSERVED_FIELDS if field not in record]


def _derive_stage(record: dict[str, Any]) -> str:
    if record.get("protocol_exception_observed") is True:
        return "protocol_exception"
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


def _default_live_executor(request: dict[str, Any]) -> dict[str, Any]:
    # The current BFCL/proxy path has no reviewed stage-observation hook here.
    # Failing before provider/BFCL execution prevents raw temp persistence and
    # avoids inventing provider/engine/parser flags from final result files.
    raise RuntimeError("live_shape_stage_not_instrumented:provider_upstream_response")


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
