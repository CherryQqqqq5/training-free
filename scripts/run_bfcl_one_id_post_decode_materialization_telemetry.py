#!/usr/bin/env python3
"""Dry-run or run one-ID post-decode materialization telemetry."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.bfcl_one_id_live_shape_telemetry_capture import (  # noqa: E402
    SIGNED_ROUTE_MODEL,
    SIGNED_ROUTE_PROFILE,
    _bfcl_generate_subprocess_env,
    _load_latest_trace,
    _one_id_generate_command,
    _result_files_for_run_id,
    _result_observation,
    _start_proxy,
    _sync_fixture_env,
    _temporary_one_id_manifest,
    _temporary_run_root,
    _terminate_proxy,
    _write_one_id_run_ids,
)
from scripts.check_bfcl_one_id_post_decode_materialization_telemetry_artifact import validate as validate_artifact  # noqa: E402
from scripts.check_bfcl_one_id_post_decode_materialization_telemetry_gate import (  # noqa: E402
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    SIGNED_ID,
    check as check_packet,
)
from scripts.run_bfcl_exact_2id_generate_smoke import REPO_ROOT as BFCL_REPO_ROOT, RUNTIME_CONFIG, RULES_DIR  # noqa: E402

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_post_decode_materialization_telemetry_compact.json")


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    return {
        "report_scope": "bfcl_one_id_post_decode_materialization_telemetry_plan",
        "approval_status": packet_summary.get("approval_status"),
        "planned_run_ids": [SIGNED_ID],
        "planned_run_id_count": 1,
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "generate_only": True,
        "stop_after_compact_post_decode_materialization_capture": True,
        "provider_request_executed": False,
        "live_post_decode_telemetry_executed": False,
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
        "blockers": [] if packet_summary.get("bfcl_one_id_post_decode_materialization_telemetry_gate_passed") else packet_summary.get("blockers", []),
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


def _layout_label(result_root: Path, result_files: list[Path]) -> str:
    if not result_files:
        return "missing"
    labels: set[str] = set()
    for path in result_files:
        try:
            rel = path.relative_to(result_root)
        except ValueError:
            labels.add("outside_result_root")
            continue
        parts = rel.parts
        if len(parts) >= 2:
            labels.add("category_nested_json")
        elif len(parts) == 1:
            labels.add("result_root_json")
        else:
            labels.add("unknown_layout")
    return "+".join(sorted(labels)) if labels else "unknown_layout"


def _result_path_class_label(result_root: Path, result_files: list[Path]) -> str:
    if not result_files:
        return "missing"
    if all(path.suffix == ".json" for path in result_files):
        return "bfcl_result_json_under_temp_root"
    return "bfcl_result_mixed_under_temp_root"


def _result_shape_label(result_observation: dict[str, Any]) -> str:
    status = str(result_observation.get("compact_classifier_status") or "missing_result")
    if result_observation.get("result_file_contains_nonempty_shape") is True:
        return "nonempty_tool_or_text_shape"
    if status == "empty_model_response":
        return "empty_model_response_shape"
    if status == "protocol_error":
        return "protocol_error_shape"
    return status


def _derive_stage(record: dict[str, Any]) -> str:
    if record.get("post_decode_exception_observed") is True:
        return "post_decode_exception_after_decode"
    if record.get("bfcl_decode_execute_nonempty") is not True:
        return "decode_not_nonempty"
    if record.get("materialization_called") is not True:
        return "materialization_not_called_after_decode"
    if record.get("materialized_result_written") is not True:
        return "result_layout_or_path_lookup_missing_after_decode"
    if record.get("result_layout_match") is not True:
        return "result_layout_mismatch_after_decode"
    if record.get("materialized_result_nonempty") is not True:
        return "materialization_empty_after_decode"
    if record.get("classifier_detected_nonempty") is not True and record.get("classifier_status") == "protocol_error":
        return "classifier_protocol_error_after_nonempty_decode"
    if record.get("protocol_status_classifier_label") == "protocol_error" and record.get("classifier_detected_nonempty") is True:
        return "protocol_status_classifier_false_error_after_nonempty_decode"
    if record.get("classifier_detected_nonempty") is not True:
        return "classifier_missed_nonempty_after_decode"
    return "live_post_decode_nonempty"


def _record_from_run(run_root: Path, decode_capture_path: Path) -> dict[str, Any]:
    # Load the trace to prove provider/proxy boundary existed, but persist only post-decode fields.
    _load_latest_trace(run_root / "traces")
    result_root = run_root / "bfcl/result"
    result_observation = _result_observation(SIGNED_ID, result_root)
    result_files = _result_files_for_run_id(SIGNED_ID, result_root)
    decode = _load_decode_events(decode_capture_path)
    classifier_status = str(result_observation.get("compact_classifier_status") or "missing_result")
    classifier_nonempty = result_observation.get("result_file_contains_nonempty_shape") is True
    record: dict[str, Any] = {
        "run_id": SIGNED_ID,
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        **decode,
        "materialization_called": decode.get("bfcl_decode_execute_nonempty") is True,
        "materialized_result_written": bool(result_files),
        "materialized_result_nonempty": classifier_nonempty,
        "materialized_result_shape_label": _result_shape_label(result_observation),
        "result_layout_expected_label": "category_nested_json_or_result_root_json",
        "result_layout_observed_label": _layout_label(result_root, result_files),
        "result_layout_match": bool(result_files),
        "result_file_path_class_label": _result_path_class_label(result_root, result_files),
        "classifier_called": True,
        "classifier_detected_nonempty": classifier_nonempty,
        "classifier_status": classifier_status,
        "protocol_status_classifier_called": True,
        "protocol_status_classifier_label": classifier_status if classifier_status in {"protocol_error", "empty_model_response", "generated", "missing_result", "unknown_compact_status"} else "other",
        "compact_result_status": classifier_status,
    }
    record["suspected_post_decode_failure_stage"] = _derive_stage(record)
    return {field: record.get(field) for field in REQUIRED_COMPACT_FIELDS}


def _artifact(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_kind": "bfcl_one_id_post_decode_materialization_telemetry_compact",
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "provider_request_executed": True,
        "live_post_decode_telemetry_executed": True,
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


def execute_live_post_decode_telemetry(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_one_id_post_decode_materialization_telemetry_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("post_decode_materialization_telemetry_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    if blockers:
        return {
            "report_scope": "bfcl_one_id_post_decode_materialization_telemetry_execute",
            "provider_request_executed": False,
            "live_post_decode_telemetry_executed": False,
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
    port = int(os.environ.get("GRC_POST_DECODE_TELEMETRY_PORT") or 8131)
    proxy_proc = None
    runtime_config = BFCL_REPO_ROOT / RUNTIME_CONFIG
    rules_dir = BFCL_REPO_ROOT / RULES_DIR
    with _temporary_run_root(prefix="bfcl_one_id_post_decode_materialization_telemetry_") as run_root:
        _write_one_id_run_ids(run_root)
        _sync_fixture_env(run_root, port)
        decode_capture_path = run_root / "decode_shape_capture.jsonl"
        try:
            with _temporary_one_id_manifest():
                proxy_proc = _start_proxy(port, run_root / "traces", runtime_config, rules_dir, run_root / "proxy.log")
                env = _bfcl_generate_subprocess_env(port)
                env["GRC_BFCL_DECODE_SHAPE_CAPTURE_PATH"] = str(decode_capture_path)
                completed = subprocess.run(
                    _one_id_generate_command(run_root),
                    cwd=BFCL_REPO_ROOT,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            record = _record_from_run(run_root, decode_capture_path)
            artifact = _artifact(record)
            artifact_blockers = validate_artifact(artifact)
            if artifact_blockers:
                return {
                    "report_scope": "bfcl_one_id_post_decode_materialization_telemetry_execute",
                    "provider_request_executed": True,
                    "live_post_decode_telemetry_executed": True,
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
                    "endpoint_value_read": False,
                    "api_key_value_read": False,
                    "diagnostic_written": False,
                    "returncode": completed.returncode,
                    "blockers": artifact_blockers,
                }
            output_artifact.parent.mkdir(parents=True, exist_ok=True)
            output_artifact.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return {
                "report_scope": "bfcl_one_id_post_decode_materialization_telemetry_execute",
                "provider_request_executed": True,
                "live_post_decode_telemetry_executed": True,
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
                "endpoint_value_read": False,
                "api_key_value_read": False,
                "diagnostic_written": True,
                "artifact_path": str(output_artifact),
                "returncode": completed.returncode,
                "blockers": [],
            }
        finally:
            _terminate_proxy(proxy_proc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute-live-post-decode-telemetry", action="store_true")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_live_post_decode_telemetry:
        summary = execute_live_post_decode_telemetry(args.packet, args.output_artifact)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    ok = not summary.get("blockers")
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
