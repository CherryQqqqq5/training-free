#!/usr/bin/env python3
"""Dry-run or execute sanitized BFCL proxy/preflight failure telemetry."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_proxy_preflight_failure_telemetry_gate import (  # noqa: E402
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    check as check_packet,
)
from scripts.check_bfcl_proxy_preflight_failure_telemetry_artifact import (  # noqa: E402
    check as check_artifact,
)

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_preflight_failure_telemetry_compact.json")
BASELINE_SCRIPT = Path("scripts/run_bfcl_v4_baseline.sh")
DEFAULT_BFCL_MODEL = "gpt-4o-mini-2024-07-18-FC"
DEFAULT_CATEGORIES = "simple,multiple,parallel,parallel_multiple,multi_turn_base,multi_turn_miss_func,multi_turn_miss_param,multi_turn_long_context"
DEFAULT_PORT = "8011"
DEFAULT_CONFIG = "configs/runtime_bfcl_structured.yaml"
DEFAULT_RULES = "rules/baseline_empty"
RunCommand = Callable[..., subprocess.CompletedProcess[Any]]


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    gate_passed = bool(packet_summary.get("bfcl_proxy_preflight_failure_telemetry_gate_passed"))
    return {
        "report_scope": "bfcl_proxy_preflight_failure_telemetry_plan",
        "approval_status": packet_summary.get("approval_status"),
        "authorized": packet_summary.get("authorized"),
        "proxy_live_preflight_authorized": packet_summary.get("proxy_live_preflight_authorized"),
        "provider_request_authorized": packet_summary.get("provider_request_authorized"),
        "bfcl_generate_authorized": packet_summary.get("bfcl_generate_authorized"),
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "planned_attempt_count": 1,
        "sanitized_proxy_preflight_telemetry_only": True,
        "preflight_command_executed": False,
        "preflight_exact_exit_code_class": "not_executed",
        "preflight_failed_check_label": "not_executed",
        "preflight_environment_check_label": "not_checked_dry_run",
        "proxy_health_at_preflight_start": "not_checked_dry_run",
        "preflight_local_request_path_label": "local_proxy_chat_and_responses_paths_planned",
        "preflight_http_status_class": "not_observed_dry_run",
        "preflight_response_shape_label": "not_observed_dry_run",
        "preflight_timeout_or_exception_class": "not_observed_dry_run",
        "preflight_trace_emission_label": "not_observed_dry_run",
        "preflight_report_written_label": "not_written_dry_run",
        "provider_call_started": False,
        "bfcl_generate_started": False,
        "bfcl_evaluate_started": False,
        "scorer_started": False,
        "candidate_specs_inert": True,
        "performance_evidence": False,
        "raw_outputs_removed": True,
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "env_profile_sourced": False,
        "live_preflight_executed": False,
        "bfcl_generate_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "output_artifact_planned": str(output_artifact),
        "compact_fields": list(REQUIRED_COMPACT_FIELDS),
        "stop_gate_triggered": "none",
        "suspected_proxy_preflight_failure_stage": "pending_live_proxy_preflight_telemetry",
        "blockers": [] if gate_passed else packet_summary.get("blockers", []),
    }


def _baseline_args(run_root: Path, trace_dir: Path, artifact_dir: Path) -> list[str]:
    return [
        str(BASELINE_SCRIPT),
        os.environ.get("GRC_BFCL_MODEL", DEFAULT_BFCL_MODEL),
        str(run_root),
        DEFAULT_PORT,
        DEFAULT_CATEGORIES,
        DEFAULT_CONFIG,
        DEFAULT_RULES,
        str(trace_dir),
        str(artifact_dir),
    ]


def _profile_wrapped_command(args: list[str]) -> list[str]:
    return [
        "bash",
        "-lc",
        "set +x; set -a; source /cephfs/qiuyn/.profile >/dev/null 2>&1; set +a; exec \"$@\"",
        "bash",
        *args,
    ]


def _load_stage_events(stage_path: Path) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    if not stage_path.exists():
        return events
    for line in stage_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("event") in {"started", "completed"} and isinstance(item.get("stage"), str):
            events.append({"stage": str(item["stage"]), "event": str(item["event"])})
    return events


def _stage_started(events: list[dict[str, str]], stage: str) -> bool:
    return any(item.get("stage") == stage and item.get("event") == "started" for item in events)


def _stage_completed(events: list[dict[str, str]], stage: str) -> bool:
    return any(item.get("stage") == stage and item.get("event") == "completed" for item in events)


def _exit_code_class(code: int) -> str:
    if code == 0:
        return "zero"
    if code == 1:
        return "nonzero_1"
    return "nonzero_other"


def _load_preflight_report(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _environment_label(report: dict[str, Any] | None) -> str:
    if report is None:
        return "not_observed"
    env_check = report.get("environment_check")
    if not isinstance(env_check, dict):
        return "not_observed"
    if env_check.get("is_set") is True:
        return "ok"
    if env_check.get("is_set") is False:
        return "missing_required_env"
    return "unknown_compact"


def _checks(report: dict[str, Any] | None) -> list[dict[str, Any]]:
    if report is None or not isinstance(report.get("checks"), list):
        return []
    return [item for item in report["checks"] if isinstance(item, dict)]


def _failed_check_label(report: dict[str, Any] | None) -> str:
    if report is None:
        return "preflight_report_missing"
    if _environment_label(report) == "missing_required_env":
        return "environment_check"
    for item in _checks(report):
        if item.get("passed") is False:
            name = str(item.get("name") or "unknown_compact")
            if re.fullmatch(r"[A-Za-z0-9_.-]+", name):
                return name
            return "unknown_compact"
    if report.get("passed") is True:
        return "none_observed"
    return "unknown_compact"


def _local_request_path_label(report: dict[str, Any] | None) -> str:
    checks = _checks(report)
    if not checks:
        return "not_observed"
    path_labels = {str(item.get("request_path_label") or item.get("request_path") or "") for item in checks}
    joined = " ".join(path_labels).lower()
    if "chat" in joined and "responses" in joined:
        return "local_proxy_chat_and_responses_paths"
    if "chat" in joined:
        return "local_proxy_chat_path_only"
    if "responses" in joined:
        return "local_proxy_responses_path_only"
    return "unknown_compact"


def _http_status_class(report: dict[str, Any] | None) -> str:
    codes: list[int] = []
    for item in _checks(report):
        status = item.get("status_code")
        if isinstance(status, int):
            codes.append(status)
    if not codes:
        return "not_observed"
    classes = {f"{code // 100}xx" for code in codes if 100 <= code <= 599}
    if len(classes) == 1:
        return next(iter(classes))
    return "mixed_non2xx"


def _response_shape_label(report: dict[str, Any] | None) -> str:
    failed = _failed_check_label(report)
    if failed == "none_observed":
        return "all_expected_shapes"
    if failed in {"chat_tool_call", "tool_call"}:
        return "missing_tool_call"
    if failed in {"responses_function_call", "function_call"}:
        return "missing_function_call"
    if failed in {"chat_text_response", "text_response"}:
        return "missing_text"
    if failed == "preflight_report_missing":
        return "not_observed"
    return "unknown_compact"


def _trace_label(report: dict[str, Any] | None) -> str:
    failed = _failed_check_label(report)
    if failed == "trace_emission":
        return "trace_missing"
    for item in _checks(report):
        if str(item.get("name")) == "trace_emission" and item.get("passed") is True:
            return "trace_emitted"
    if report is None:
        return "not_observed"
    return "unknown_compact"


def _read_temp_text(*paths: Path) -> str:
    chunks: list[str] = []
    for path in paths:
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8", errors="ignore")[-20000:])
    return "\n".join(chunks)


def _timeout_or_exception_label(text: str, exit_code: int, report: dict[str, Any] | None) -> str:
    lower = text.lower()
    if "timed out" in lower or "timeout" in lower or "readtimeout" in lower:
        return "timeout"
    if "httperror" in lower or "http error" in lower:
        return "http_error"
    if "traceback" in lower or "exception" in lower or "runtimeerror" in lower:
        return "runtime_exception"
    if exit_code == 0 or report is not None:
        return "none_observed"
    return "unknown_compact"


def _proxy_health(events: list[dict[str, str]]) -> str:
    if _stage_started(events, "preflight"):
        return "healthy_preflight_started" if _stage_completed(events, "start_proxy") else "unknown_compact"
    if _stage_started(events, "start_proxy") and not _stage_completed(events, "start_proxy"):
        return "proxy_start_incomplete"
    return "not_reached"


def _stop_gate(record: dict[str, Any]) -> str:
    if record["provider_call_started"]:
        return "provider_call_started"
    if record["bfcl_generate_started"]:
        return "bfcl_generate_started"
    if record["bfcl_evaluate_started"]:
        return "bfcl_evaluate_started"
    if record["scorer_started"]:
        return "scorer_started"
    if record["preflight_exact_exit_code_class"] != "zero":
        return "preflight_exit_nonzero"
    if record["preflight_failed_check_label"] not in {"none_observed", "unknown_compact"}:
        return record["preflight_failed_check_label"]
    return "stopped_after_preflight"


def _suspected_stage(record: dict[str, Any]) -> str:
    if record["provider_call_started"]:
        return "forbidden_provider_call_started"
    if record["bfcl_generate_started"]:
        return "forbidden_bfcl_generate_started"
    if record["bfcl_evaluate_started"] or record["scorer_started"]:
        return "forbidden_post_preflight_stage_started"
    if record["preflight_report_written_label"] == "missing":
        return "preflight_report_missing"
    failed = record["preflight_failed_check_label"]
    if failed not in {"none_observed", "unknown_compact"}:
        return f"preflight_{failed}_failed"
    if record["preflight_exact_exit_code_class"] != "zero":
        return "preflight_nonzero_exit_unknown"
    return "preflight_completed_without_bfcl_generate"


def _compact_record(exit_code: int, stage_path: Path, artifact_dir: Path, exec_log: Path, proxy_log: Path) -> dict[str, Any]:
    events = _load_stage_events(stage_path)
    report = _load_preflight_report(artifact_dir / "preflight_report.json")
    text = _read_temp_text(exec_log, proxy_log)
    record: dict[str, Any] = {
        "preflight_command_executed": True,
        "preflight_exact_exit_code_class": _exit_code_class(exit_code),
        "preflight_failed_check_label": _failed_check_label(report),
        "preflight_environment_check_label": _environment_label(report),
        "proxy_health_at_preflight_start": _proxy_health(events),
        "preflight_local_request_path_label": _local_request_path_label(report),
        "preflight_http_status_class": _http_status_class(report),
        "preflight_response_shape_label": _response_shape_label(report),
        "preflight_timeout_or_exception_class": _timeout_or_exception_label(text, exit_code, report),
        "preflight_trace_emission_label": _trace_label(report),
        "preflight_report_written_label": "written" if report is not None else "missing",
        "provider_call_started": _stage_started(events, "provider_call"),
        "bfcl_generate_started": _stage_started(events, "bfcl_generate"),
        "bfcl_evaluate_started": _stage_started(events, "bfcl_evaluate"),
        "scorer_started": _stage_started(events, "aggregate_bfcl_metrics") or _stage_started(events, "bfcl_evaluate"),
        "candidate_specs_inert": True,
        "performance_evidence": False,
        "raw_outputs_removed": False,
        "stop_gate_triggered": "pending_cleanup",
        "suspected_proxy_preflight_failure_stage": "pending_classification",
    }
    record["stop_gate_triggered"] = _stop_gate(record)
    record["suspected_proxy_preflight_failure_stage"] = _suspected_stage(record)
    return record


def _write_artifact(record: dict[str, Any], output_artifact: Path) -> None:
    payload = {
        "artifact_kind": "bfcl_proxy_preflight_failure_telemetry_compact",
        "measurement_kind": "sanitized_bfcl_proxy_preflight_failure_telemetry",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "raw_outputs_committed": False,
        "records": [{field: record.get(field) for field in REQUIRED_COMPACT_FIELDS}],
    }
    output_artifact.parent.mkdir(parents=True, exist_ok=True)
    output_artifact.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _blocked_execute_summary(blockers: list[str]) -> dict[str, Any]:
    return {
        "report_scope": "bfcl_proxy_preflight_failure_telemetry_execute",
        "preflight_command_executed": False,
        "provider_call_started": False,
        "bfcl_generate_started": False,
        "bfcl_evaluate_started": False,
        "scorer_started": False,
        "live_preflight_executed": False,
        "bfcl_generate_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "env_profile_sourced": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "raw_outputs_removed": True,
        "blockers": sorted(set(blockers)),
    }


def execute_proxy_preflight_telemetry(
    packet_path: Path = DEFAULT_PACKET,
    output_artifact: Path = DEFAULT_OUTPUT,
    *,
    run_command: RunCommand | None = None,
) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_proxy_preflight_failure_telemetry_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("proxy_preflight_telemetry_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    if blockers:
        return _blocked_execute_summary(blockers)

    run_command = run_command or subprocess.run
    record: dict[str, Any] | None = None
    with tempfile.TemporaryDirectory(prefix="bfcl_proxy_preflight_telemetry_") as temp_dir:
        temp = Path(temp_dir)
        run_root = temp / "run_root"
        trace_dir = temp / "traces"
        artifact_dir = temp / "artifacts"
        stage_path = temp / "stage_events.jsonl"
        exec_log = temp / "preflight_execution.log"
        proxy_log = temp / "preflight_proxy.log"
        repairs_out = temp / "repairs.jsonl"
        env = os.environ.copy()
        env.update(
            {
                "GRC_UPSTREAM_PROFILE": "novacode",
                "GRC_UPSTREAM_MODEL": "gpt-4.1",
                "GRC_BFCL_TEST_CATEGORY": DEFAULT_CATEGORIES,
                "GRC_BFCL_USE_RUN_IDS": "0",
                "GRC_BFCL_CLEAN_RUN": "1",
                "GRC_BFCL_NUM_THREADS": "1",
                "GRC_BFCL_STOP_AFTER_PREFLIGHT": "1",
                "GRC_BASELINE_STAGE_TELEMETRY_PATH": str(stage_path),
                "GRC_PROXY_LOG": str(proxy_log),
                "GRC_BFCL_REPAIRS_OUT": str(repairs_out),
            }
        )
        command = _profile_wrapped_command(_baseline_args(run_root, trace_dir, artifact_dir))
        with exec_log.open("wb") as handle:
            result = run_command(command, cwd=REPO_ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT, check=False)
        exit_code = int(getattr(result, "returncode", 1))
        record = _compact_record(exit_code, stage_path, artifact_dir, exec_log, proxy_log)
        shutil.rmtree(run_root, ignore_errors=True)
        shutil.rmtree(trace_dir, ignore_errors=True)
        shutil.rmtree(artifact_dir, ignore_errors=True)
        for raw_temp_path in (exec_log, proxy_log, repairs_out, stage_path):
            raw_temp_path.unlink(missing_ok=True)
        raw_removed = not any(path.exists() for path in (run_root, trace_dir, artifact_dir, exec_log, proxy_log, repairs_out, stage_path))
        record["raw_outputs_removed"] = raw_removed
        _write_artifact(record, output_artifact)

    blockers = []
    if record.get("provider_call_started"):
        blockers.append("provider_call_started")
    if record.get("bfcl_generate_started"):
        blockers.append("bfcl_generate_started")
    if record.get("bfcl_evaluate_started"):
        blockers.append("bfcl_evaluate_started")
    if record.get("scorer_started"):
        blockers.append("scorer_started")
    if not record.get("raw_outputs_removed"):
        blockers.append("raw_output_cleanup_failed")
    artifact_summary = check_artifact(output_artifact)
    if not artifact_summary.get("bfcl_proxy_preflight_failure_telemetry_artifact_passed"):
        blockers.extend(str(blocker) for blocker in artifact_summary.get("blockers", []))
    return {
        "report_scope": "bfcl_proxy_preflight_failure_telemetry_execute",
        **record,
        "live_preflight_executed": True,
        "bfcl_generate_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "endpoint_value_read": True,
        "api_key_value_read": True,
        "env_profile_sourced": True,
        "output_artifact": str(output_artifact),
        "blockers": sorted(set(blockers)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute-proxy-preflight-telemetry", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_proxy_preflight_telemetry:
        summary = execute_proxy_preflight_telemetry(args.packet, args.output_artifact)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
