#!/usr/bin/env python3
"""Dry-run or execute one-ID protocol-error telemetry."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.bfcl_one_id_live_shape_telemetry_capture import (  # noqa: E402
    _load_latest_trace,
    _provider_observation_from_trace,
    _result_files_for_run_id,
    _result_observation,
    _terminate_proxy,
)
from scripts.check_bfcl_one_id_protocol_error_telemetry_gate import (  # noqa: E402
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    SIGNED_ID,
    check as check_packet,
)
from scripts.run_bfcl_exact_2id_generate_smoke import (  # noqa: E402
    BFCL_MODEL_ALIAS,
    REPO_ROOT as BFCL_REPO_ROOT,
    RUNTIME_CONFIG,
    RULES_DIR,
    _assert_generate_only_command,
    _bfcl_generate_subprocess_env,
    _bfcl_package_run_ids_path,
    _python,
    _start_proxy,
    _sync_fixture_env,
)

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_protocol_error_telemetry_compact.json")
DEFAULT_RUN_ROOT = Path("/tmp/bfcl_one_id_protocol_error_telemetry")
SIGNED_CATEGORY = "multi_turn_long_context"
SIGNED_ID_MANIFEST = {SIGNED_CATEGORY: [SIGNED_ID]}
SIGNED_ROUTE_PROFILE = "novacode"
SIGNED_ROUTE_MODEL = "gpt-4.1"


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    return {
        "report_scope": "bfcl_one_id_protocol_error_telemetry_plan",
        "approval_status": packet_summary.get("approval_status"),
        "planned_run_ids": [SIGNED_ID],
        "planned_run_id_count": 1,
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "candidate_specs_inert": True,
        "generate_only": True,
        "stop_after_compact_protocol_error_capture": True,
        "provider_request_executed": False,
        "live_protocol_error_telemetry_executed": False,
        "bfcl_generate_executed": False,
        "bfcl_smoke_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "output_artifact_planned": str(output_artifact),
        "compact_fields": list(REQUIRED_COMPACT_FIELDS),
        "blockers": [] if packet_summary.get("bfcl_one_id_protocol_error_telemetry_gate_passed") else packet_summary.get("blockers", []),
    }


def _write_run_ids(run_root: Path) -> Path:
    path = run_root / "bfcl/test_case_ids_to_generate.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(SIGNED_ID_MANIFEST, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


@contextlib.contextmanager
def _temporary_protocol_error_manifest(path: Path | None = None):
    target = path or _bfcl_package_run_ids_path()
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
        str(BFCL_REPO_ROOT / "scripts/run_bfcl_cli.py"),
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


def _execute_preflight_blockers(packet_path: Path, output_artifact: Path) -> list[str]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_one_id_protocol_error_telemetry_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("one_id_protocol_error_telemetry_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    return sorted(set(blockers))


def _empty_execute_summary(output_artifact: Path, blockers: list[str]) -> dict[str, Any]:
    return {
        "report_scope": "bfcl_one_id_protocol_error_telemetry_execute",
        "planned_run_ids": [SIGNED_ID],
        "planned_run_id_count": 1,
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "provider_request_executed": False,
        "live_protocol_error_telemetry_executed": False,
        "bfcl_generate_executed": False,
        "bfcl_smoke_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "diagnostic_written": False,
        "output_artifact_planned": str(output_artifact),
        "blockers": sorted(set(blockers)),
    }


def _load_decode_events(path: Path) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    decode_events = [event for event in events if event.get("event") == "bfcl_decode"]
    decode = decode_events[-1] if decode_events else {}
    output_count = int(decode.get("bfcl_decode_output_count") or 0)
    exception_class = str(decode.get("bfcl_decode_exception_class") or "not_observed")
    return {
        "bfcl_decode_execute_nonempty": bool(decode.get("bfcl_decode_execute_nonempty")),
        "bfcl_decode_output_count": output_count,
        "bfcl_decode_output_shape_label": "execution_list_nonempty" if output_count > 0 else "empty_list",
        "post_decode_exception_observed": exception_class not in {"none", "not_observed"},
        "post_decode_exception_class": exception_class,
    }


def _result_shape_label(result_observation: dict[str, Any]) -> str:
    status = str(result_observation.get("compact_classifier_status") or "missing_result")
    if result_observation.get("result_file_contains_nonempty_shape") is True:
        return "nonempty_tool_or_text_shape"
    if status == "empty_model_response":
        return "empty_model_response_shape"
    if status == "protocol_error":
        return "protocol_error_shape"
    return status


def _derive_protocol_stage(record: dict[str, Any]) -> str:
    if record.get("post_decode_exception_observed") is True:
        return "post_decode_exception"
    if record.get("provider_response_has_tool_calls") is not True and record.get("provider_response_has_nonempty_text") is not True:
        return "provider_no_tool_or_text"
    if record.get("bfcl_decode_execute_nonempty") is not True:
        return "decode_not_nonempty"
    if record.get("materialization_called") is not True:
        return "materialization_not_called_after_decode"
    if record.get("materialized_result_written") is not True:
        return "materialization_missing_after_decode"
    if record.get("result_layout_match") is not True:
        return "result_layout_mismatch_after_decode"
    if record.get("classifier_status") == "protocol_error" or record.get("protocol_status_classifier_label") == "protocol_error":
        return "protocol_status_after_nonempty_decode"
    if record.get("classifier_status") == "unknown_compact_status":
        return "unknown_compact_status_after_decode"
    if record.get("compact_result_status") == "generated":
        return "protocol_error_not_reproduced"
    return "protocol_error_stage_unresolved"


def _record_from_run(
    run_root: Path,
    decode_capture_path: Path,
    *,
    load_trace: Callable[[Path], dict[str, Any]] | None = None,
    result_observer: Callable[[str, Path], dict[str, Any]] | None = None,
    result_files_finder: Callable[[str, Path], list[Path]] | None = None,
) -> dict[str, Any]:
    trace = (load_trace or _load_latest_trace)(run_root / "traces")
    provider = _provider_observation_from_trace(trace)
    result_root = run_root / "bfcl/result"
    result_observation = (result_observer or _result_observation)(SIGNED_ID, result_root)
    result_files = (result_files_finder or _result_files_for_run_id)(SIGNED_ID, result_root)
    decode = _load_decode_events(decode_capture_path)
    if decode["bfcl_decode_output_count"] == 0 and result_observation.get("bfcl_decode_execute_nonempty") is True:
        decode = {
            "bfcl_decode_execute_nonempty": True,
            "bfcl_decode_output_count": 1,
            "bfcl_decode_output_shape_label": "execution_list_nonempty",
            "post_decode_exception_observed": False,
            "post_decode_exception_class": "not_observed",
        }
    classifier_status = str(result_observation.get("compact_classifier_status") or "missing_result")
    materialized_nonempty = result_observation.get("result_file_contains_nonempty_shape") is True
    record: dict[str, Any] = {
        "run_id": SIGNED_ID,
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "candidate_specs_inert": True,
        "provider_response_has_tool_calls": provider.get("provider_response_has_tool_calls") is True,
        "provider_response_has_nonempty_text": provider.get("provider_response_has_nonempty_text") is True,
        **decode,
        "materialization_called": decode.get("bfcl_decode_execute_nonempty") is True,
        "materialized_result_written": bool(result_files),
        "materialized_result_nonempty": materialized_nonempty,
        "materialized_result_shape_label": _result_shape_label(result_observation),
        "result_layout_match": bool(result_files),
        "classifier_called": True,
        "classifier_detected_nonempty": materialized_nonempty,
        "classifier_status": classifier_status,
        "protocol_status_classifier_called": True,
        "protocol_status_classifier_label": classifier_status if classifier_status in {"protocol_error", "generated", "empty_model_response", "missing_result", "unknown_compact_status"} else "other",
        "compact_result_status": classifier_status,
    }
    record["suspected_protocol_error_stage"] = _derive_protocol_stage(record)
    return {field: record.get(field) for field in REQUIRED_COMPACT_FIELDS}


def _artifact(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_kind": "bfcl_one_id_protocol_error_telemetry_compact",
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "candidate_specs_inert": True,
        "provider_request_executed": True,
        "live_protocol_error_telemetry_executed": True,
        "bfcl_generate_executed": True,
        "bfcl_smoke_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "gpt_5_2_active": False,
        "openrouter_allowed": False,
        "run_ids": [SIGNED_ID],
        "records": [record],
    }


def execute_one_id_protocol_error_telemetry(
    packet_path: Path = DEFAULT_PACKET,
    output_artifact: Path = DEFAULT_OUTPUT,
    run_root: Path = DEFAULT_RUN_ROOT,
    port: int = 8131,
    *,
    start_proxy: Callable[..., Any] | None = None,
    run_generate: Callable[[list[str], dict[str, str]], subprocess.CompletedProcess[Any]] | None = None,
    sync_fixture_env: Callable[[Path, int], None] | None = None,
    manifest_context: Callable[[], Any] | None = None,
    load_trace: Callable[[Path], dict[str, Any]] | None = None,
    result_observer: Callable[[str, Path], dict[str, Any]] | None = None,
    result_files_finder: Callable[[str, Path], list[Path]] | None = None,
) -> dict[str, Any]:
    blockers = _execute_preflight_blockers(packet_path, output_artifact)
    if blockers:
        return _empty_execute_summary(output_artifact, blockers)
    endpoint_read = bool(os.environ.get("CHUANGZHI_NOVACODE_ENDPOINT") or os.environ.get("NOVACODE_ENDPOINT") or os.environ.get("NOVACODE_BASE_URL"))
    api_key_read = bool(os.environ.get("CHUANGZHI_API_KEY") or os.environ.get("NOVACODE_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    runtime_config = BFCL_REPO_ROOT / RUNTIME_CONFIG
    rules_dir = BFCL_REPO_ROOT / RULES_DIR
    proxy_proc = None
    completed: subprocess.CompletedProcess[Any] | None = None
    try:
        if run_root.exists():
            shutil.rmtree(run_root)
        trace_dir = run_root / "traces"
        _write_run_ids(run_root)
        (sync_fixture_env or _sync_fixture_env)(run_root, port)
        decode_capture_path = run_root / "decode_shape_capture.jsonl"
        with (manifest_context or _temporary_protocol_error_manifest)():
            proxy_proc = (start_proxy or _start_proxy)(port, trace_dir, runtime_config, rules_dir, run_root / "proxy.log")
            command = _generate_command(run_root)
            _assert_generate_only_command(command)
            env = _bfcl_generate_subprocess_env(port)
            env["GRC_BFCL_DECODE_SHAPE_CAPTURE_PATH"] = str(decode_capture_path)
            if run_generate is None:
                completed = subprocess.run(command, cwd=BFCL_REPO_ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                completed = run_generate(command, env)
        record = _record_from_run(
            run_root,
            decode_capture_path,
            load_trace=load_trace,
            result_observer=result_observer,
            result_files_finder=result_files_finder,
        )
        artifact = _artifact(record)
        output_artifact.parent.mkdir(parents=True, exist_ok=True)
        output_artifact.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {
            "report_scope": "bfcl_one_id_protocol_error_telemetry_execute",
            "planned_run_ids": [SIGNED_ID],
            "planned_run_id_count": 1,
            "route_profile": SIGNED_ROUTE_PROFILE,
            "route_model": SIGNED_ROUTE_MODEL,
            "provider_request_executed": completed.returncode == 0,
            "live_protocol_error_telemetry_executed": completed.returncode == 0,
            "bfcl_generate_executed": completed.returncode == 0,
            "bfcl_smoke_executed": False,
            "bfcl_evaluate_executed": False,
            "scorer_executed": False,
            "full_baseline_executed": False,
            "candidate_runtime_activation_authorized": False,
            "candidate_jsonl_authorized": False,
            "candidate_pool_ready": False,
            "performance_evidence": False,
            "sota_3pp_claim_ready": False,
            "huawei_acceptance_ready": False,
            "endpoint_value_read": endpoint_read,
            "api_key_value_read": api_key_read,
            "diagnostic_written": True,
            "artifact_path": str(output_artifact),
            "returncode": completed.returncode,
            "compact_result_status": record.get("compact_result_status"),
            "suspected_protocol_error_stage": record.get("suspected_protocol_error_stage"),
            "blockers": [] if completed.returncode == 0 else ["bfcl_generate_failed"],
        }
    finally:
        _terminate_proxy(proxy_proc)
        shutil.rmtree(run_root, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute-one-id-protocol-error-telemetry", action="store_true")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--port", type=int, default=8131)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_one_id_protocol_error_telemetry:
        summary = execute_one_id_protocol_error_telemetry(args.packet, args.output_artifact, args.run_root, args.port)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    ok = not summary.get("blockers")
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
