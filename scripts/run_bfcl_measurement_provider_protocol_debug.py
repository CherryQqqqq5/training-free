#!/usr/bin/env python3
"""Plan a synthetic BFCL measurement provider protocol debug run.

This runner intentionally supports dry-run/plan-only only. It must not read
endpoint/key environment values or call the provider until a separate execution
authorization updates the packet and this runner.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_measurement_provider_protocol_debug_packet import check as check_packet

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_measurement_provider_protocol_debug_packet.json")
PLANNED_PROBES = [
    "synthetic_empty_response_guard",
    "synthetic_tool_call_required_guard",
    "synthetic_openai_response_shape_guard",
]


def build_plan(packet: Path = PACKET) -> dict:
    packet_summary = check_packet(packet)
    blockers = list(packet_summary["blockers"])
    if packet_summary.get("provider_request_authorized") is not False:
        blockers.append("provider_request_not_fail_closed")
    return {
        "report_scope": "bfcl_measurement_provider_protocol_debug_plan",
        "packet_path": str(packet),
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "openrouter_allowed": False,
        "planned_probes": PLANNED_PROBES,
        "provider_request_executed": False,
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "bfcl_scorer_executed": False,
        "bfcl_smoke_executed": False,
        "bfcl_full_eval_executed": False,
        "source_input_read": False,
        "diagnostic_written": False,
        "raw_provider_payload_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
        "raw_prompt_persisted": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "scorer_feedback_tuning_enabled": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "bfcl_measurement_provider_protocol_debug_plan_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    parser.add_argument("--packet", type=Path, default=PACKET)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = build_plan(args.packet)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_measurement_provider_protocol_debug_plan_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
