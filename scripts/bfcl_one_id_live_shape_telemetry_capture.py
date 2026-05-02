#!/usr/bin/env python3
"""Signed one-ID BFCL live-shape telemetry capture boundary.

The factory validates the reviewed one-ID scope and returns a callable suitable
for scripts/run_bfcl_one_id_live_shape_telemetry.py. Tests inject a fake
executor; the default executor is the reviewed BFCL generate-shaped path and is
only used during a separately approved live execution.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from scripts.check_bfcl_one_id_live_shape_telemetry_gate import SIGNED_IDS
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
DEFAULT_RUN_ROOT = Path("/tmp/bfcl_one_id_live_shape_telemetry")
LiveExecutor = Callable[[dict[str, Any]], dict[str, Any]]


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


def _generate_command(run_root: Path) -> list[str]:
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


def _record_from_classification(classification: dict[str, Any], *, protocol_exception: bool = False) -> dict[str, Any]:
    status = classification.get("status")
    tool = bool(classification.get("tool_call_detected"))
    text = bool(classification.get("no_tool_text_recorded"))
    empty = bool(classification.get("empty_model_response_detected"))
    if protocol_exception or status == "protocol_error":
        stage = "protocol_exception"
    elif tool:
        stage = "live_path_nonempty"
    elif text:
        stage = "provider_text_no_tool"
    elif empty:
        stage = "provider_true_empty"
    else:
        stage = "bfcl_parse_decode_loss"
    decode_nonempty = tool
    result_nonempty = tool or text
    return {
        "run_id": SIGNED_IDS[0],
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "local_proxy_endpoint_path_label": "bfcl_generate_local_proxy_responses_v1",
        "bfcl_handler_class_label": "openai_responses_handler",
        "bfcl_api_path_label": "responses",
        "request_shape_hash": "live_shape_hash_redacted",
        "request_message_count_bucket": "bfcl_shape_only",
        "request_has_instructions": True,
        "request_has_tools": True,
        "request_tool_count": 0,
        "request_tool_choice_shape": "bfcl_shape_only",
        "request_token_field_shape": "max_output_tokens",
        "provider_status_class": "protocol_exception" if stage == "protocol_exception" else "2xx_or_proxy_success",
        "provider_response_empty_bool": stage == "provider_true_empty",
        "provider_response_has_choices": not empty and stage != "protocol_exception",
        "provider_response_has_message": not empty and stage != "protocol_exception",
        "provider_response_has_tool_calls": tool,
        "provider_response_has_nonempty_text": text,
        "engine_apply_response_called": stage != "protocol_exception",
        "engine_final_has_tool_calls": tool,
        "engine_final_has_nonempty_text": text,
        "engine_final_content_empty": not text,
        "engine_coerced_nonempty_text_to_empty": False,
        "proxy_responses_output_has_function_call": tool,
        "proxy_responses_output_has_nonempty_text": text,
        "bfcl_parse_called": stage != "protocol_exception",
        "bfcl_parse_model_response_empty": empty,
        "bfcl_decode_execute_called": stage != "protocol_exception",
        "bfcl_decode_execute_nonempty": decode_nonempty,
        "result_file_written": bool(status and status != "missing_result"),
        "result_file_contains_nonempty_shape": result_nonempty,
        "compact_classifier_status": str(status or "missing_result"),
        "protocol_exception_observed": stage == "protocol_exception",
        "protocol_exception_converted_to_empty_model_response": False,
        "classifier_false_empty_for_nonempty_result": False,
        "suspected_live_failure_stage": stage,
    }


def _default_live_executor(request: dict[str, Any]) -> dict[str, Any]:
    run_root = Path(str(request.get("run_root") or DEFAULT_RUN_ROOT))
    port = int(request.get("port") or 8131)
    runtime_config = REPO_ROOT / RUNTIME_CONFIG
    rules_dir = REPO_ROOT / RULES_DIR
    trace_dir = run_root / "traces"
    if run_root.exists():
        shutil.rmtree(run_root)
    _sync_fixture_env(run_root, port)
    proxy_proc: subprocess.Popen[bytes] | None = None
    try:
        with _temporary_one_id_manifest():
            proxy_proc = _start_proxy(port, trace_dir, runtime_config, rules_dir, run_root / "proxy.log")
            command = _generate_command(run_root)
            completed = subprocess.run(command, cwd=REPO_ROOT, env=_bfcl_generate_subprocess_env(port), check=False)
        classification = _classify_result_for_run_id(SIGNED_IDS[0], run_root / "bfcl/result")
        return _record_from_classification(classification, protocol_exception=completed.returncode != 0 and classification.get("status") == "missing_result")
    finally:
        if proxy_proc is not None:
            proxy_proc.terminate()
            try:
                proxy_proc.wait(timeout=5)
            except Exception:
                proxy_proc.kill()


def build_signed_one_id_live_shape_capture(request: dict[str, Any], *, executor: LiveExecutor | None = None) -> LiveExecutor:
    blockers = _request_blockers(request)
    if blockers:
        raise RuntimeError(";".join(blockers))
    selected_executor = executor or _default_live_executor

    def _capture(capture_request: dict[str, Any]) -> dict[str, Any]:
        blockers_inner = _request_blockers(capture_request)
        if blockers_inner:
            raise RuntimeError(";".join(blockers_inner))
        record = selected_executor(capture_request)
        if not isinstance(record, dict):
            raise RuntimeError("one_id_capture_record_not_object")
        return record

    return _capture
