#!/usr/bin/env python3
"""Dry-run ABHE state transition writer skeleton."""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List

ALLOWED_DRY_RUN_TRANSITIONS = {
    ("proposal_ready", "dev_smoke_requested"),
    ("dev_smoke_requested", "dev_smoke_authorized"),
    ("dev_smoke_authorized", "dev_smoke_executed"),
    ("dev_smoke_executed", "dev_passed"),
    ("dev_smoke_executed", "narrow_router_requested"),
    ("dev_smoke_executed", "split_requested"),
    ("dev_smoke_executed", "demoted_no_mechanism_signal"),
    ("dev_smoke_executed", "demoted_regression_not_controlled"),
    ("dev_smoke_executed", "rejected_boundary_failure"),
}
FORBIDDEN_DIRECT_TRANSITIONS = {("proposal_ready", "dev_passed")}


def build_transition(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "artifact_kind": "abhe_state_transition_dry_run",
        "entry_id": args.entry_id,
        "from_status": args.from_status,
        "to_status": args.to_status,
        "reason": args.reason,
        "dry_run": True,
        "archive_written": False,
        "performance_evidence": False,
        "authorization_scope": "dry_run_only",
    }


def validate(args: argparse.Namespace) -> List[str]:
    blockers = []
    transition = (args.from_status, args.to_status)
    if transition in FORBIDDEN_DIRECT_TRANSITIONS:
        blockers.append("direct_proposal_ready_to_dev_passed_forbidden")
    if transition not in ALLOWED_DRY_RUN_TRANSITIONS:
        blockers.append("transition_not_allowed_in_dry_run:%s_to_%s" % transition)
    if not args.dry_run:
        blockers.append("non_dry_run_requires_future_explicit_approval_artifact")
    if args.write:
        blockers.append("archive_write_not_supported_in_current_skeleton")
    return blockers


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry-id", required=True)
    parser.add_argument("--from-status", required=True)
    parser.add_argument("--to-status", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    blockers = validate(args)
    summary = {
        "report_scope": "abhe_state_transition_dry_run",
        "state_transition_dry_run_passed": not blockers,
        "proposed_transition": build_transition(args) if not blockers else None,
        "blockers": sorted(set(blockers)),
    }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and blockers:
        return 1
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
