#!/usr/bin/env python3
"""Plan RASHE provider protocol debug preflight variants without provider requests."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_rashe_provider_protocol_debug_preflight_packet import DEFAULT_PACKET, SIGNED_VARIANTS


def run_packet_checker(packet: Path) -> tuple[bool, str | None]:
    result = subprocess.run(
        [sys.executable, "scripts/check_rashe_provider_protocol_debug_preflight_packet.py", "--packet", str(packet), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, result.stdout.strip() or result.stderr.strip() or "provider_protocol_debug_preflight_packet_failed"
    return True, None


def variant_plan() -> list[dict[str, Any]]:
    return [
        {
            "variant": variant,
            "planned_only": True,
            "provider_request_executed": False,
            "raw_request_persisted": False,
            "raw_response_persisted": False,
            "raw_headers_persisted": False,
            "raw_body_persisted": False,
            "source_input_read": False,
            "diagnostic_written": False,
            "candidate_generation_authorized": False,
            "scorer_authorized": False,
            "performance_evidence": False,
            "blocker": None,
        }
        for variant in SIGNED_VARIANTS
    ]


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    packet_ok, packet_error = run_packet_checker(args.packet)
    if not packet_ok:
        blockers.append(f"packet_check_failed:{packet_error}")
    if args.execute_debug:
        blockers.append("protocol_debug_execution_not_approved")
    if not (args.dry_run or args.plan_only or args.execute_debug):
        blockers.append("dry_run_or_plan_only_required")
    return {
        "report_scope": "rashe_provider_protocol_debug_preflight_plan",
        "packet_path": str(args.packet),
        "rashe_provider_protocol_debug_preflight_plan_passed": not blockers,
        "dry_run": args.dry_run,
        "plan_only": args.plan_only,
        "execute_debug": args.execute_debug,
        "signed_model": "gpt-4.1",
        "fallback_allowed": False,
        "provider_request_executed": False,
        "endpoint_value_read": False,
        "api_key_value_read": False,
        "source_input_read": False,
        "diagnostic_written": False,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "variants": variant_plan(),
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute-debug", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = build_plan(args)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_provider_protocol_debug_preflight_plan_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
