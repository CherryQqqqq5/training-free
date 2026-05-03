#!/usr/bin/env python3
"""Dry-run harness for sanitized BFCL baseline failure telemetry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_baseline_live_failure_telemetry_gate import (  # noqa: E402
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    check as check_packet,
)

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_baseline_live_failure_telemetry_compact.json")


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


def execute_live_failure_telemetry(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_baseline_live_failure_telemetry_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("baseline_live_failure_telemetry_packet_not_approved")
    if output_artifact.exists():
        blockers.append("output_artifact_exists")
    # This gate-preparation commit intentionally does not execute the baseline command.
    blockers.append("baseline_live_failure_telemetry_execution_not_enabled_in_gate_preparation")
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
