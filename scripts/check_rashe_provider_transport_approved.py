#!/usr/bin/env python3
"""Strict approved-provider-transport gate for RASHE Phase B."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_rashe_provider_transport_approval_packet import DEFAULT_PACKET, check as check_packet


def check(packet_path: Path = DEFAULT_PACKET) -> dict:
    summary = check_packet(packet_path)
    blockers = list(summary.get("blockers", []))
    if summary.get("approval_status") != "approved":
        blockers.append(f"provider_transport_not_approved:{summary.get('approval_status')!r}")
    for key in ["authorized", "provider_transport_authorized", "source_diagnostic_execution_authorized", "provider_calls_authorized"]:
        if summary.get(key) is not True:
            blockers.append(f"provider_transport_gate_{key}_not_true:{summary.get(key)!r}")
    return {
        **summary,
        "report_scope": "rashe_provider_transport_approved_check",
        "rashe_provider_transport_approved_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check(args.packet)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_provider_transport_approved_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
