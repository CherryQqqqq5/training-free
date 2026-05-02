#!/usr/bin/env python3
"""Plan-only BFCL live-shape telemetry runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_live_shape_telemetry_packet import SIGNED_IDS, check as check_packet


def build_plan() -> dict[str, object]:
    packet_summary = check_packet()
    return {
        "report_scope": "bfcl_live_shape_telemetry_plan",
        "approval_status": packet_summary.get("approval_status"),
        "planned_run_ids": SIGNED_IDS,
        "planned_run_id_count": len(SIGNED_IDS),
        "route_model": "gpt-4.1",
        "active_profile": "novacode",
        "provider_request_executed": False,
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "bfcl_smoke_executed": False,
        "bfcl_scorer_executed": False,
        "candidate_runtime_activation_authorized": False,
        "performance_evidence": False,
        "raw_persistence_authorized": False,
        "output_artifact_planned": "outputs/artifacts/stage1_bfcl_acceptance/bfcl_live_shape_telemetry_compact.json",
        "telemetry_fields": [
            "endpoint_path_label",
            "request_shape_label",
            "response_shape_label",
            "status_code_class",
            "output_empty",
            "tool_call_present",
            "parser_decode_path_label",
            "token_forwarding_label",
            "tool_choice_forwarding_label",
            "instructions_forwarding_label",
            "engine_content_empty_label",
            "engine_coercion_label",
        ],
        "blockers": [] if packet_summary.get("bfcl_live_shape_telemetry_packet_passed") else packet_summary.get("blockers", []),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute-telemetry", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_telemetry:
        summary = {
            "report_scope": "bfcl_live_shape_telemetry_plan",
            "provider_request_executed": False,
            "endpoint_value_read": False,
            "api_key_value_read": False,
            "bfcl_smoke_executed": False,
            "blockers": ["live_shape_telemetry_execution_not_authorized"],
        }
        print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
        return 1 if args.strict else 0
    summary = build_plan()
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and summary.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
