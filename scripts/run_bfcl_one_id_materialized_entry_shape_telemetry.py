#!/usr/bin/env python3
"""Dry-run gate harness for one-ID materialized-entry shape telemetry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_one_id_materialized_entry_shape_telemetry_gate import (  # noqa: E402
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    SIGNED_ID,
    check as check_packet,
)

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_materialized_entry_shape_telemetry_compact.json")
SIGNED_ROUTE_PROFILE = "novacode"
SIGNED_ROUTE_MODEL = "gpt-4.1"


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    return {
        "report_scope": "bfcl_one_id_materialized_entry_shape_telemetry_plan",
        "approval_status": packet_summary.get("approval_status"),
        "planned_run_ids": [SIGNED_ID],
        "planned_run_id_count": 1,
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "candidate_specs_inert": True,
        "generate_only": True,
        "stop_after_compact_materialized_entry_shape_capture": True,
        "provider_request_executed": False,
        "live_materialized_entry_shape_telemetry_executed": False,
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
        "blockers": [] if packet_summary.get("bfcl_one_id_materialized_entry_shape_telemetry_gate_passed") else packet_summary.get("blockers", []),
    }


def execute_live_materialized_entry_shape_telemetry(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    blockers = [] if packet_summary.get("bfcl_one_id_materialized_entry_shape_telemetry_gate_passed") else list(packet_summary.get("blockers", []))
    if packet_summary.get("approval_status") != "approved":
        blockers.append("one_id_materialized_entry_shape_telemetry_packet_not_approved")
    blockers.append("one_id_materialized_entry_shape_telemetry_live_execution_not_configured")
    return {
        "report_scope": "bfcl_one_id_materialized_entry_shape_telemetry_execute",
        "planned_run_ids": [SIGNED_ID],
        "planned_run_id_count": 1,
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "provider_request_executed": False,
        "live_materialized_entry_shape_telemetry_executed": False,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute-one-id-materialized-entry-shape-telemetry", action="store_true")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_one_id_materialized_entry_shape_telemetry:
        summary = execute_live_materialized_entry_shape_telemetry(args.packet, args.output_artifact)
    else:
        summary = build_plan(args.packet, args.output_artifact)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
