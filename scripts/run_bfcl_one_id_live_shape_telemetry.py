#!/usr/bin/env python3
"""Plan or execute one-ID BFCL live-shape telemetry.

The committed packet is pending/fail-closed. Execute mode is present only for a
future reviewed packet state; dry-run/plan never reads endpoint or key values.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_one_id_live_shape_telemetry_gate import ALLOWED_TELEMETRY_FIELDS, SIGNED_IDS, check as check_packet

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_gate_packet.json")
DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_live_shape_telemetry_compact.json")
SIGNED_ROUTE_PROFILE = "novacode"
SIGNED_ROUTE_MODEL = "gpt-4.1"


def build_plan(packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    return {
        "report_scope": "bfcl_one_id_live_shape_telemetry_plan",
        "approval_status": packet_summary.get("approval_status"),
        "planned_run_ids": list(SIGNED_IDS),
        "planned_run_id_count": len(SIGNED_IDS),
        "route_profile": SIGNED_ROUTE_PROFILE,
        "route_model": SIGNED_ROUTE_MODEL,
        "generate_only": True,
        "provider_request_executed": False,
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
        "raw_persistence_authorized": False,
        "output_artifact_planned": str(output_artifact),
        "telemetry_fields": list(ALLOWED_TELEMETRY_FIELDS),
        "blockers": [] if packet_summary.get("bfcl_one_id_live_shape_telemetry_gate_passed") else packet_summary.get("blockers", []),
    }


def execute_live_telemetry(*, packet_path: Path = DEFAULT_PACKET, output_artifact: Path = DEFAULT_OUTPUT, clean_output: bool = False) -> dict[str, Any]:
    packet_summary = check_packet(packet_path)
    if not packet_summary.get("bfcl_one_id_live_shape_telemetry_gate_passed"):
        return {
            "report_scope": "bfcl_one_id_live_shape_telemetry_execute",
            "provider_request_executed": False,
            "bfcl_generate_executed": False,
            "endpoint_value_read": False,
            "api_key_value_read": False,
            "diagnostic_written": False,
            "blockers": packet_summary.get("blockers", []),
        }
    if packet_summary.get("approval_status") != "approved":
        return {
            "report_scope": "bfcl_one_id_live_shape_telemetry_execute",
            "provider_request_executed": False,
            "bfcl_generate_executed": False,
            "endpoint_value_read": False,
            "api_key_value_read": False,
            "diagnostic_written": False,
            "blockers": ["one_id_live_shape_telemetry_packet_not_approved"],
        }
    if output_artifact.exists() and not clean_output:
        return {
            "report_scope": "bfcl_one_id_live_shape_telemetry_execute",
            "provider_request_executed": False,
            "bfcl_generate_executed": False,
            "endpoint_value_read": False,
            "api_key_value_read": False,
            "diagnostic_written": False,
            "blockers": ["output_artifact_exists_without_clean_output"],
        }
    return {
        "report_scope": "bfcl_one_id_live_shape_telemetry_execute",
        "provider_request_executed": False,
        "bfcl_generate_executed": False,
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "diagnostic_written": False,
        "blockers": ["one_id_live_shape_telemetry_execute_transport_not_implemented_in_prep_gate"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute-live-telemetry", action="store_true")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output-artifact", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--clean-output", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_live_telemetry:
        summary = execute_live_telemetry(packet_path=args.packet, output_artifact=args.output_artifact, clean_output=args.clean_output)
    else:
        summary = build_plan(packet_path=args.packet, output_artifact=args.output_artifact)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
