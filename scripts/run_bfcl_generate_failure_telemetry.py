#!/usr/bin/env python3
"""Dry-run or execute sanitized BFCL generate failure telemetry."""

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

from scripts.check_bfcl_generate_failure_telemetry_gate import (  # noqa: E402
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    check as check_packet,
)

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_generate_failure_telemetry_compact.json")
BASELINE_SCRIPT = Path("scripts/run_bfcl_v4_baseline.sh")
DEFAULT_CATEGORIES = "simple,multiple,parallel,parallel_multiple,multi_turn_base,multi_turn_miss_func,multi_turn_miss_param,multi_turn_long_context"
DEFAULT_BFCL_MODEL = "gpt-4o-mini-2024-07-18-FC"
DEFAULT_PORT = "8011"
DEFAULT_CONFIG = "configs/runtime_bfcl_structured.yaml"
DEFAULT_RULES = "rules/baseline_empty"
PROFILE_PATH = Path("/cephfs/qiuyn/.profile")

PROVIDER_STATUS_CLASSES = {"2xx", "3xx", "4xx", "5xx", "timeout", "proxy_unreachable", "connection_error", "not_observed", "unknown_compact"}
PROVIDER_COMPLETION_CLASSES = {"completed_2xx", "completed_non2xx", "timeout", "connection_error", "not_observed", "unknown_compact"}
BFCL_EXCEPTION_CLASSES = {"command_config_error", "import_error", "runtime_exception", "timeout", "result_path_error", "proxy_or_provider_error", "unknown_nonzero", "none_observed"}
BFCL_EXCEPTION_STAGE_LABELS = {"generate_command_setup", "proxy_request", "result_materialization", "unknown_generate", "none_observed"}
OPTIONAL_PREGENERATE_SUBSTAGE_FIELDS = [
    "config_source_exit_class",
    "env_default_expansion_class",
    "category_arg_assembly_shape",
    "category_arg_validation_result",
    "bfcl_cli_import_probe_class_without_generate",
    "bfcl_cli_argument_probe_class_without_generate",
    "pre_generate_marker_boundary_class",
    "last_started_stage",
    "last_completed_stage",
    "suspected_pregenerate_failure_substage",
]

RunCommand = Callable[..., subprocess.CompletedProcess[Any]]


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    gate_passed = bool(packet_summary.get("bfcl_generate_failure_telemetry_gate_passed"))
    return {
        "report_scope": "bfcl_generate_failure_telemetry_plan",
        "approval_status": packet_summary.get("approval_status"),
        "authorized": packet_summary.get("authorized"),
        "provider_request_authorized": packet_summary.get("provider_request_authorized"),
        "bfcl_generate_authorized": packet_summary.get("bfcl_generate_authorized"),
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "planned_attempt_count": 1,
        "sanitized_generate_failure_telemetry_only": True,
        "baseline_command_executed": False,
        "generate_stage_entered": False,
        "generate_exact_exit_code": None,
        "generate_exit_code_class": "not_executed",
        "generate_command_arg_shape_label": "planned_current_system_generate_command_template",
        "category_scope_label": "full_default_categories_comma_list",
        "proxy_health_at_generate_start": "not_checked_dry_run",
        "provider_status_class_during_generate": "not_called_dry_run",
        "provider_call_started": False,
        "provider_call_completed_class": "not_called_dry_run",
        "bfcl_cli_exception_class": "not_executed",
        "bfcl_cli_exception_stage_label": "not_executed",
        "result_file_count_after_generate": None,
        "generated_output_root_present_after_generate": False,
        "compact_metrics_present": False,
        "compact_manifest_present": False,
        "compact_run_manifest_present": False,
        "bfcl_evaluate_started": False,
        "scorer_started": False,
        "raw_outputs_removed": True,
        "candidate_specs_inert": True,
        "scorer_feedback_used": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "env_profile_sourced": False,
        "bfcl_generate_executed": False,
        "bfcl_smoke_executed": False,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "output_artifact_planned": str(output_artifact),
        "compact_fields": list(REQUIRED_COMPACT_FIELDS),
        "stop_gate_triggered": "none",
        "suspected_generate_failure_stage": "pending_live_generate_failure_telemetry",
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
            sanitized = {"stage": str(item["stage"]), "event": str(item["event"])}
            for key in OPTIONAL_PREGENERATE_SUBSTAGE_FIELDS:
                value = item.get(key)
                if isinstance(value, str):
                    sanitized[key] = value
            events.append(sanitized)
    return events


def _stage_started(events: list[dict[str, str]], stage: str) -> bool:
    return any(item.get("stage") == stage and item.get("event") == "started" for item in events)


def _stage_completed(events: list[dict[str, str]], stage: str) -> bool:
    return any(item.get("stage") == stage and item.get("event") == "completed" for item in events)


def _last_stage(events: list[dict[str, str]], event: str) -> str:
    for item in reversed(events):
        if item.get("event") == event:
            return str(item.get("stage") or "not_observed")
    return "not_observed"


def _latest_event_field(events: list[dict[str, str]], field: str, default: str = "not_observed") -> str:
    for item in reversed(events):
        value = item.get(field)
        if isinstance(value, str) and value:
            return value
    return default


def classify_category_arg_shape(category_arg: str) -> str:
    if not category_arg:
        return "empty_test_category_argument"
    if "," in category_arg:
        return "single_comma_joined_test_category_argument"
    return "single_category_argument"


def classify_category_arg_validation(category_arg: str) -> str:
    if not category_arg:
        return "not_validated_without_execution"
    if re.fullmatch(r"[A-Za-z0-9_.-]+(,[A-Za-z0-9_.-]+)*", category_arg):
        return "accepted_by_static_shape"
    return "rejected_by_static_shape"


def classify_pregenerate_substage_labels(events: list[dict[str, str]], *, generate_entered: bool, category_arg: str = DEFAULT_CATEGORIES) -> dict[str, str]:
    labels = {
        "config_source_exit_class": _latest_event_field(events, "config_source_exit_class", "not_observed"),
        "env_default_expansion_class": _latest_event_field(events, "env_default_expansion_class", "not_observed"),
        "category_arg_assembly_shape": _latest_event_field(events, "category_arg_assembly_shape", classify_category_arg_shape(category_arg)),
        "category_arg_validation_result": _latest_event_field(events, "category_arg_validation_result", classify_category_arg_validation(category_arg)),
        "bfcl_cli_import_probe_class_without_generate": _latest_event_field(events, "bfcl_cli_import_probe_class_without_generate", "not_observed"),
        "bfcl_cli_argument_probe_class_without_generate": _latest_event_field(events, "bfcl_cli_argument_probe_class_without_generate", "not_observed"),
        "pre_generate_marker_boundary_class": _latest_event_field(events, "pre_generate_marker_boundary_class", "not_observed"),
        "last_started_stage": _last_stage(events, "started"),
        "last_completed_stage": _last_stage(events, "completed"),
        "suspected_pregenerate_failure_substage": "pending_classification",
    }
    labels["suspected_pregenerate_failure_substage"] = _suspected_pregenerate_substage(labels, generate_entered=generate_entered)
    return labels


def _suspected_pregenerate_substage(labels: dict[str, str], *, generate_entered: bool) -> str:
    if generate_entered:
        return "none_generate_stage_entered"
    if labels["config_source_exit_class"] in {"nonzero", "missing"}:
        return "config_source"
    if labels["env_default_expansion_class"] in {"nonzero", "missing"}:
        return "env_default_expansion"
    if labels["category_arg_validation_result"] == "rejected_by_static_shape":
        return "category_arg_validation"
    started = labels["last_started_stage"]
    completed = labels["last_completed_stage"]
    if started != "not_observed" and started != completed:
        return f"{started}_not_completed"
    if completed == "preflight":
        return "after_preflight_before_pregenerate_substage"
    if completed.startswith("pregenerate_"):
        return f"after_{completed}_before_bfcl_generate"
    return "unknown_pregenerate_substage"


def _exit_code_class(code: int) -> str:
    if code == 0:
        return "zero"
    if code == 1:
        return "nonzero_1"
    return "nonzero_other"


def _proxy_health_label(events: list[dict[str, str]], generate_entered: bool) -> str:
    if not generate_entered:
        if _stage_started(events, "start_proxy") and not _stage_completed(events, "start_proxy"):
            return "proxy_start_incomplete"
        return "not_reached"
    if _stage_completed(events, "preflight"):
        return "healthy_preflight_completed"
    if _stage_completed(events, "start_proxy"):
        return "healthy_proxy_started"
    return "unknown_at_generate_start"


def _count_result_files(result_dir: Path) -> int:
    if not result_dir.exists():
        return 0
    return sum(1 for path in result_dir.rglob("*") if path.is_file())


def _read_temp_text(*paths: Path) -> str:
    chunks: list[str] = []
    for path in paths:
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8", errors="ignore")[-20000:])
    return "\n".join(chunks)


def _status_code_class(text: str) -> str | None:
    for match in re.finditer(r"(?:status(?:\s+code)?|http(?:/\d(?:\.\d)?)?)[^0-9]{0,16}([2-5][0-9][0-9])", text, re.IGNORECASE):
        code = int(match.group(1))
        return f"{code // 100}xx"
    return None


def classify_provider_proxy_status(text: str, *, generate_entered: bool) -> tuple[str, str]:
    lower = text.lower()
    if not generate_entered:
        return "not_observed", "not_observed"
    if "timed out" in lower or "timeout" in lower or "readtimeout" in lower:
        return "timeout", "timeout"
    if "proxy did not respond" in lower or "grc proxy did not respond" in lower or "failed to connect to 127.0.0.1" in lower or "connection refused" in lower and ("127.0.0.1" in lower or "localhost" in lower):
        return "proxy_unreachable", "connection_error"
    if "connectionerror" in lower or "connection reset" in lower or "failed to establish a new connection" in lower or "max retries exceeded" in lower:
        return "connection_error", "connection_error"
    status_class = _status_code_class(text)
    if status_class:
        return status_class, "completed_2xx" if status_class == "2xx" else "completed_non2xx"
    if lower.strip():
        return "unknown_compact", "unknown_compact"
    return "not_observed", "not_observed"


def classify_bfcl_cli_failure(exit_code: int, text: str, *, provider_status_class: str, generate_entered: bool, result_file_count: int) -> tuple[str, str]:
    if exit_code == 0:
        return "none_observed", "none_observed"
    lower = text.lower()
    if "timed out" in lower or "timeout" in lower or "readtimeout" in lower:
        return "timeout", "proxy_request" if generate_entered else "generate_command_setup"
    if "modulenotfounderror" in lower or "importerror" in lower or "no module named" in lower:
        return "import_error", "generate_command_setup"
    if "unrecognized arguments" in lower or "invalid choice" in lower or "usage:" in lower or "error: argument" in lower or "bfcl model alias is empty" in lower:
        return "command_config_error", "generate_command_setup"
    if "result-dir" in lower or "result dir" in lower or "result_path" in lower or "result path" in lower or "permission denied" in lower or "no such file or directory" in lower and "result" in lower:
        return "result_path_error", "result_materialization"
    if provider_status_class in {"4xx", "5xx", "timeout", "proxy_unreachable", "connection_error"}:
        return "proxy_or_provider_error", "proxy_request"
    if "proxy" in lower or "provider" in lower or "connection refused" in lower or "connectionerror" in lower or "max retries exceeded" in lower or _status_code_class(text) in {"4xx", "5xx"}:
        return "proxy_or_provider_error", "proxy_request"
    if "traceback" in lower or "exception" in lower or "runtimeerror" in lower or "error during" in lower:
        return "runtime_exception", "unknown_generate"
    if generate_entered and result_file_count == 0:
        return "result_path_error", "result_materialization"
    return "unknown_nonzero", "unknown_generate"


def _suspected_stage(record: dict[str, Any]) -> str:
    if record["bfcl_evaluate_started"] or record["scorer_started"]:
        return "forbidden_post_generate_stage_started"
    if not record["generate_stage_entered"]:
        return "pre_generate_failure"
    if record["generate_exit_code_class"] != "zero":
        return "bfcl_generate_nonzero_exit"
    if record["result_file_count_after_generate"] == 0:
        return "bfcl_generate_zero_result_files"
    return "generate_stage_completed_before_evaluate"


def _stop_gate(record: dict[str, Any]) -> str:
    if record["bfcl_evaluate_started"]:
        return "bfcl_evaluate_started"
    if record["scorer_started"]:
        return "scorer_started"
    if record["generate_exit_code_class"] != "zero":
        return "bfcl_generate_exit_nonzero"
    if record["result_file_count_after_generate"] == 0:
        return "missing_generate_results"
    return "stopped_after_generate"


def _compact_record(exit_code: int, stage_path: Path, run_root: Path, exec_log: Path, proxy_log: Path) -> dict[str, Any]:
    events = _load_stage_events(stage_path)
    generate_entered = _stage_started(events, "bfcl_generate")
    result_dir = run_root / "bfcl" / "result"
    result_file_count = _count_result_files(result_dir)
    temp_text = _read_temp_text(exec_log, proxy_log)
    provider_status_class, provider_completed_class = classify_provider_proxy_status(temp_text, generate_entered=generate_entered)
    bfcl_exception_class, bfcl_exception_stage = classify_bfcl_cli_failure(
        exit_code,
        temp_text,
        provider_status_class=provider_status_class,
        generate_entered=generate_entered,
        result_file_count=result_file_count,
    )
    pregenerate_labels = classify_pregenerate_substage_labels(events, generate_entered=generate_entered)
    record: dict[str, Any] = {
        "baseline_command_executed": True,
        "generate_stage_entered": generate_entered,
        "generate_exact_exit_code": exit_code,
        "generate_exit_code_class": _exit_code_class(exit_code),
        "generate_command_arg_shape_label": "current_system_generate_stop_after_generate_command",
        "category_scope_label": "full_default_categories_comma_list",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "proxy_health_at_generate_start": _proxy_health_label(events, generate_entered),
        "provider_status_class_during_generate": provider_status_class,
        "provider_call_started": generate_entered,
        "provider_call_completed_class": provider_completed_class,
        "bfcl_cli_exception_class": bfcl_exception_class,
        "bfcl_cli_exception_stage_label": bfcl_exception_stage,
        "result_file_count_after_generate": result_file_count,
        "generated_output_root_present_after_generate": result_dir.exists(),
        "compact_metrics_present": False,
        "compact_manifest_present": False,
        "compact_run_manifest_present": False,
        "bfcl_evaluate_started": _stage_started(events, "bfcl_evaluate"),
        "scorer_started": _stage_started(events, "bfcl_evaluate") or _stage_started(events, "aggregate_bfcl_metrics"),
        "raw_outputs_removed": False,
        "candidate_specs_inert": True,
        "scorer_feedback_used": False,
        "performance_evidence": False,
        "stop_gate_triggered": "pending_cleanup",
        "suspected_generate_failure_stage": "pending_classification",
        **pregenerate_labels,
    }
    record["stop_gate_triggered"] = _stop_gate(record)
    record["suspected_generate_failure_stage"] = _suspected_stage(record)
    return record


def _write_artifact(record: dict[str, Any], output_artifact: Path) -> None:
    payload = {
        "artifact_kind": "bfcl_generate_failure_telemetry_compact",
        "measurement_kind": "sanitized_bfcl_generate_failure_telemetry",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "scorer_feedback_used": False,
        "raw_outputs_committed": False,
        "records": [
            {
                field: record.get(field)
                for field in [*REQUIRED_COMPACT_FIELDS, *OPTIONAL_PREGENERATE_SUBSTAGE_FIELDS]
                if field in record
            }
        ],
    }
    output_artifact.parent.mkdir(parents=True, exist_ok=True)
    output_artifact.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def execute_generate_failure_telemetry(
    packet_path: Path = DEFAULT_PACKET,
    output_artifact: Path = DEFAULT_OUTPUT,
    *,
    run_command: RunCommand | None = None,
) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_generate_failure_telemetry_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("generate_failure_telemetry_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    if blockers:
        return {
            "report_scope": "bfcl_generate_failure_telemetry_execute",
            "baseline_command_executed": False,
            "generate_stage_entered": False,
            "provider_call_started": False,
            "bfcl_generate_executed": False,
            "bfcl_smoke_executed": False,
            "bfcl_evaluate_started": False,
            "bfcl_evaluate_executed": False,
            "scorer_started": False,
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
            "env_profile_sourced": False,
            "raw_outputs_removed": True,
            "blockers": sorted(set(blockers)),
        }

    run_command = run_command or subprocess.run
    record: dict[str, Any] | None = None
    with tempfile.TemporaryDirectory(prefix="bfcl_generate_failure_telemetry_") as temp_dir:
        temp = Path(temp_dir)
        run_root = temp / "run_root"
        trace_dir = temp / "traces"
        artifact_dir = temp / "artifacts"
        stage_path = temp / "stage_events.jsonl"
        exec_log = temp / "generate_execution.log"
        proxy_log = temp / "generate_proxy.log"
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
                "GRC_BFCL_STOP_AFTER_GENERATE": "1",
                "GRC_BASELINE_STAGE_TELEMETRY_PATH": str(stage_path),
                "GRC_PROXY_LOG": str(proxy_log),
                "GRC_BFCL_REPAIRS_OUT": str(repairs_out),
            }
        )
        command = _profile_wrapped_command(_baseline_args(run_root, trace_dir, artifact_dir))
        with exec_log.open("wb") as handle:
            result = run_command(command, cwd=REPO_ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT, check=False)
        exit_code = int(getattr(result, "returncode", 1))
        record = _compact_record(exit_code, stage_path, run_root, exec_log, proxy_log)
        shutil.rmtree(run_root, ignore_errors=True)
        shutil.rmtree(trace_dir, ignore_errors=True)
        shutil.rmtree(artifact_dir, ignore_errors=True)
        for raw_temp_path in (exec_log, proxy_log, repairs_out, stage_path):
            raw_temp_path.unlink(missing_ok=True)
        raw_removed = not any(path.exists() for path in (run_root, trace_dir, artifact_dir, exec_log, proxy_log, repairs_out, stage_path))
        record["raw_outputs_removed"] = raw_removed
        _write_artifact(record, output_artifact)

    summary = {
        "report_scope": "bfcl_generate_failure_telemetry_execute",
        **(record or {}),
        "bfcl_generate_executed": bool(record and record.get("generate_stage_entered")),
        "bfcl_smoke_executed": False,
        "bfcl_evaluate_executed": bool(record and record.get("bfcl_evaluate_started")),
        "scorer_executed": bool(record and record.get("scorer_started")),
        "full_baseline_executed": False,
        "endpoint_value_read": True,
        "api_key_value_read": True,
        "env_profile_sourced": True,
        "output_artifact": str(output_artifact),
        "blockers": [] if record and record.get("raw_outputs_removed") else ["raw_output_cleanup_failed"],
    }
    if summary.get("bfcl_evaluate_started"):
        summary["blockers"].append("bfcl_evaluate_started")
    if summary.get("scorer_started"):
        summary["blockers"].append("scorer_started")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute-generate-failure-telemetry", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_generate_failure_telemetry:
        summary = execute_generate_failure_telemetry(args.packet, args.output_artifact)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
