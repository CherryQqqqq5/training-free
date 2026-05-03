#!/usr/bin/env python3
"""Dry-run or execute sanitized BFCL baseline failure telemetry."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_baseline_live_failure_telemetry_gate import (  # noqa: E402
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    check as check_packet,
)

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_baseline_live_failure_telemetry_compact.json")
PLAN_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_current_system_baseline_execution_plan.json")
RUN_ROOT = Path("outputs/bfcl_v4/current_system_baseline")
ARTIFACT_DIR = RUN_ROOT / "artifacts"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"
RUN_MANIFEST_PATH = ARTIFACT_DIR / "run_manifest.json"
COMPACT_MANIFEST_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_current_system_baseline_compact_manifest.json")

RunCommand = Callable[..., subprocess.CompletedProcess[Any]]


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain JSON object")
    return data


def _baseline_command(plan_path: Path = PLAN_PATH) -> list[str]:
    plan = _load_json(plan_path)
    command = plan.get("runner_command_template")
    if not isinstance(command, list) or "scripts/run_bfcl_v4_baseline.sh" not in command:
        raise ValueError("baseline_runner_template_missing")
    categories = "simple,multiple,parallel,parallel_multiple,multi_turn_base,multi_turn_miss_func,multi_turn_miss_param,multi_turn_long_context"
    return [
        "bash",
        "scripts/run_bfcl_v4_baseline.sh",
        os.environ.get("GRC_BFCL_MODEL", "gpt-4o-mini-2024-07-18-FC"),
        "outputs/bfcl_v4/current_system_baseline",
        "8011",
        categories,
        "configs/runtime_bfcl_structured.yaml",
        "rules/baseline_empty",
    ]


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    gate_passed = bool(packet_summary.get("bfcl_baseline_live_failure_telemetry_gate_passed"))
    return {
        "report_scope": "bfcl_baseline_live_failure_telemetry_plan",
        "approval_status": packet_summary.get("approval_status"),
        "authorized": packet_summary.get("authorized"),
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "planned_attempt_count": 1,
        "current_commit_baseline_only": True,
        "sanitized_failure_telemetry_only": True,
        "baseline_command_executed": False,
        "provider_call_started": False,
        "bfcl_generate_started": False,
        "bfcl_generate_completed": False,
        "bfcl_evaluate_started": False,
        "bfcl_evaluate_completed": False,
        "scorer_started": False,
        "scorer_completed": False,
        "compact_metrics_present": False,
        "compact_manifest_present": False,
        "compact_run_manifest_present": False,
        "run_root_present": False,
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
        "output_artifact_planned": str(output_artifact),
        "compact_fields": list(REQUIRED_COMPACT_FIELDS),
        "blockers": [] if gate_passed else packet_summary.get("blockers", []),
    }


def _load_stage_events(stage_path: Path) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    if not stage_path.exists():
        return events
    for line in stage_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and isinstance(item.get("stage"), str) and item.get("event") in {"started", "completed"}:
            events.append({"stage": item["stage"], "event": item["event"]})
    return events


def _last_stage(events: list[dict[str, str]], event: str) -> str:
    for item in reversed(events):
        if item.get("event") == event:
            return item.get("stage") or "none"
    return "none"


def _stage_completed(events: list[dict[str, str]], stage: str) -> bool:
    return any(item.get("stage") == stage and item.get("event") == "completed" for item in events)


def _stage_started(events: list[dict[str, str]], stage: str) -> bool:
    return any(item.get("stage") == stage and item.get("event") == "started" for item in events)


def _exit_code_class(code: int) -> str:
    if code == 0:
        return "zero"
    if code == 1:
        return "nonzero_1"
    return "nonzero_other"


def _failed_stage(events: list[dict[str, str]], exit_code: int) -> str:
    if exit_code == 0:
        return "none"
    last_started = _last_stage(events, "started")
    last_completed = _last_stage(events, "completed")
    if last_started != "none" and last_started != last_completed:
        return last_started
    return "baseline_command"


def _compact_record(exit_code: int, stage_path: Path, raw_removed: bool) -> dict[str, Any]:
    events = _load_stage_events(stage_path)
    failed_stage = _failed_stage(events, exit_code)
    metrics_present = METRICS_PATH.exists()
    compact_manifest_present = COMPACT_MANIFEST_PATH.exists()
    run_manifest_present = RUN_MANIFEST_PATH.exists()
    stop_gate = "none"
    if exit_code != 0:
        stop_gate = "baseline_command_exit_nonzero"
    elif not (metrics_present and run_manifest_present):
        stop_gate = "missing_compact_metrics_or_manifest"
    return {
        "baseline_command_executed": True,
        "baseline_exit_code_class": _exit_code_class(exit_code),
        "last_started_stage": _last_stage(events, "started"),
        "last_completed_stage": _last_stage(events, "completed"),
        "failed_stage": failed_stage,
        "stage_failure_class": "none" if exit_code == 0 else _exit_code_class(exit_code),
        "provider_call_started": _stage_started(events, "bfcl_generate"),
        "bfcl_generate_started": _stage_started(events, "bfcl_generate"),
        "bfcl_generate_completed": _stage_completed(events, "bfcl_generate"),
        "bfcl_evaluate_started": _stage_started(events, "bfcl_evaluate"),
        "bfcl_evaluate_completed": _stage_completed(events, "bfcl_evaluate"),
        "scorer_started": _stage_started(events, "bfcl_evaluate") or _stage_started(events, "aggregate_bfcl_metrics"),
        "scorer_completed": _stage_completed(events, "bfcl_evaluate") or _stage_completed(events, "aggregate_bfcl_metrics"),
        "compact_metrics_present": metrics_present,
        "compact_manifest_present": compact_manifest_present,
        "compact_run_manifest_present": run_manifest_present,
        "run_root_present": RUN_ROOT.exists(),
        "raw_outputs_removed": raw_removed,
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "candidate_specs_inert": True,
        "scorer_feedback_used": False,
        "performance_evidence": False,
        "stop_gate_triggered": stop_gate,
    }


def _write_artifact(record: dict[str, Any], output_artifact: Path) -> None:
    payload = {
        "artifact_kind": "bfcl_baseline_live_failure_telemetry_compact",
        "measurement_kind": "sanitized_baseline_live_failure_telemetry",
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
        "records": [{field: record.get(field) for field in REQUIRED_COMPACT_FIELDS}],
    }
    output_artifact.parent.mkdir(parents=True, exist_ok=True)
    output_artifact.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def execute_live_failure_telemetry(
    packet_path: Path = DEFAULT_PACKET,
    output_artifact: Path = DEFAULT_OUTPUT,
    *,
    run_command: RunCommand | None = None,
) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_baseline_live_failure_telemetry_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("baseline_live_failure_telemetry_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    if blockers:
        return {
            "report_scope": "bfcl_baseline_live_failure_telemetry_execute",
            "baseline_command_executed": False,
            "provider_call_started": False,
            "bfcl_generate_started": False,
            "bfcl_generate_completed": False,
            "bfcl_evaluate_started": False,
            "bfcl_evaluate_completed": False,
            "scorer_started": False,
            "scorer_completed": False,
            "candidate_runtime_activation_authorized": False,
            "candidate_jsonl_authorized": False,
            "candidate_pool_ready": False,
            "performance_evidence": False,
            "sota_3pp_claim_ready": False,
            "huawei_acceptance_ready": False,
            "endpoint_value_read": False,
            "api_key_value_read": False,
            "raw_outputs_removed": True,
            "blockers": sorted(set(blockers)),
        }

    run_command = run_command or subprocess.run
    raw_removed = False
    with tempfile.TemporaryDirectory(prefix="bfcl_baseline_live_failure_telemetry_") as temp_dir:
        temp = Path(temp_dir)
        stage_path = temp / "stage_events.jsonl"
        exec_log = temp / "baseline_execution.log"
        proxy_log = temp / "baseline_proxy.log"
        repairs_out = temp / "repairs.jsonl"
        env = os.environ.copy()
        env.update(
            {
                "GRC_UPSTREAM_PROFILE": "novacode",
                "GRC_UPSTREAM_MODEL": "gpt-4.1",
                "GRC_BFCL_TEST_CATEGORY": "simple,multiple,parallel,parallel_multiple,multi_turn_base,multi_turn_miss_func,multi_turn_miss_param,multi_turn_long_context",
                "GRC_BFCL_USE_RUN_IDS": "0",
                "GRC_BFCL_CLEAN_RUN": "1",
                "GRC_BFCL_NUM_THREADS": "1",
                "GRC_BASELINE_STAGE_TELEMETRY_PATH": str(stage_path),
                "GRC_PROXY_LOG": str(proxy_log),
                "GRC_BFCL_REPAIRS_OUT": str(repairs_out),
            }
        )
        command = _baseline_command()
        with exec_log.open("wb") as handle:
            result = run_command(command, cwd=REPO_ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT, check=False)
        exit_code = int(getattr(result, "returncode", 1))
        record = _compact_record(exit_code, stage_path, raw_removed=False)
        shutil.rmtree(RUN_ROOT, ignore_errors=True)
        for raw_temp_path in (exec_log, proxy_log, repairs_out):
            raw_temp_path.unlink(missing_ok=True)
        raw_removed = not RUN_ROOT.exists() and not exec_log.exists() and not proxy_log.exists() and not repairs_out.exists()
        record["run_root_present"] = RUN_ROOT.exists()
        record["raw_outputs_removed"] = raw_removed
        _write_artifact(record, output_artifact)

    return {
        "report_scope": "bfcl_baseline_live_failure_telemetry_execute",
        **record,
        "endpoint_value_read": True,
        "api_key_value_read": True,
        "output_artifact": str(output_artifact),
        "blockers": [] if raw_removed else ["raw_output_cleanup_failed"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute-live-baseline-failure-telemetry", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_live_baseline_failure_telemetry:
        summary = execute_live_failure_telemetry(args.packet, args.output_artifact)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
