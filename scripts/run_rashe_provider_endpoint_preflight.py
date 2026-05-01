#!/usr/bin/env python3
"""Plan the RASHE provider endpoint/model/tool-calling preflight without provider requests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_rashe_provider_endpoint_preflight_packet import (
    DEFAULT_PACKET,
    OPTIONAL_MODEL,
    PRIMARY_MODEL,
    SIGNED_ENDPOINT_ENVS,
    SIGNED_KEY_ENVS,
)

PROBE_FIELDS = [
    "endpoint_present",
    "key_present",
    "https_valid",
    "auth_ok",
    "model_gpt_5_2_available",
    "optional_model_gpt_5_4_observed",
    "tool_calling_supported",
    "tool_choice_supported",
    "tool_calls_returned",
    "raw_payload_persisted",
    "raw_prompt_persisted",
    "candidate_generation_authorized",
    "scorer_authorized",
    "performance_evidence",
    "blocker",
]


def run_packet_checker(packet: Path) -> tuple[bool, str | None]:
    result = subprocess.run(
        [sys.executable, "scripts/check_rashe_provider_endpoint_preflight_packet.py", "--packet", str(packet), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, result.stdout.strip() or result.stderr.strip() or "provider_endpoint_preflight_packet_failed"
    return True, None


def present_by_name(environ: dict[str, str], names: list[str]) -> bool:
    env_names = set(environ)
    return any(name in env_names for name in names)


def build_plan(args: argparse.Namespace, environ: dict[str, str] | None = None) -> dict[str, Any]:
    environ = dict(os.environ if environ is None else environ)
    blockers: list[str] = []
    packet_ok, packet_error = run_packet_checker(args.packet)
    if not packet_ok:
        blockers.append(f"packet_check_failed:{packet_error}")
    if not (args.dry_run or args.plan_only):
        blockers.append("dry_run_or_plan_only_required")

    endpoint_present = present_by_name(environ, SIGNED_ENDPOINT_ENVS)
    key_present = present_by_name(environ, SIGNED_KEY_ENVS)
    capability_observation = {
        "endpoint_present": endpoint_present,
        "key_present": key_present,
        "https_valid": False,
        "auth_ok": False,
        "model_gpt_5_2_available": False,
        "optional_model_gpt_5_4_observed": False,
        "tool_calling_supported": False,
        "tool_choice_supported": False,
        "tool_calls_returned": False,
        "raw_payload_persisted": False,
        "raw_prompt_persisted": False,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "blocker": None,
    }
    return {
        "report_scope": "rashe_provider_endpoint_preflight_plan",
        "packet_path": str(args.packet),
        "rashe_provider_endpoint_preflight_plan_passed": not blockers,
        "dry_run": args.dry_run,
        "plan_only": args.plan_only,
        "provider_request_executed": False,
        "api_key_value_read": False,
        "endpoint_value_read": False,
        "diagnostic_written": False,
        "phase_b_execution_authorized": False,
        "signed_primary_model": PRIMARY_MODEL,
        "optional_capability_observation_model": OPTIONAL_MODEL,
        "route_update_required": False,
        "openai_compatible_chat_adapter_review_required_if_standard_chat_only": True,
        **capability_observation,
        "planned_probe_fields": PROBE_FIELDS,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = build_plan(args)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_provider_endpoint_preflight_plan_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
