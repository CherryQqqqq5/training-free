#!/usr/bin/env python3
"""Dry-run or execute sanitized BFCL proxy/preflight failure telemetry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_proxy_preflight_failure_telemetry_gate import (  # noqa: E402
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    check as check_packet,
)

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_preflight_failure_telemetry_compact.json")


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


def execute_proxy_preflight_telemetry(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_proxy_preflight_failure_telemetry_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("proxy_preflight_telemetry_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    if blockers:
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
    return {
        "report_scope": "bfcl_proxy_preflight_failure_telemetry_execute",
        "preflight_command_executed": False,
        "provider_call_started": False,
        "bfcl_generate_started": False,
        "bfcl_evaluate_started": False,
        "scorer_started": False,
        "live_preflight_executed": False,
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "env_profile_sourced": False,
        "raw_outputs_removed": True,
        "blockers": ["proxy_preflight_telemetry_live_execution_not_enabled_in_gate_preparation"],
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
