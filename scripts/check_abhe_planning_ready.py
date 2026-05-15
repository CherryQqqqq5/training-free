#!/usr/bin/env python3
"""Aggregate ABHE planning checkers into one fail-closed readiness report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_archive_policy import check as check_archive_policy
from scripts.check_abhe_dev_feedback import check as check_dev_feedback
from scripts.check_abhe_dev_smoke_dry_run_manifest import check as check_dry_run_manifest
from scripts.check_abhe_dev_smoke_packet import check as check_dev_smoke_packet
from scripts.check_abhe_fresh_dev_slice_request import check as check_fresh_slice_request
from scripts.check_abhe_no_leakage_boundary import DEFAULT_PATHS, check_paths
from scripts.check_abhe_trace_cards import check as check_trace_cards
from scripts.check_abhe_trace_extraction_packet import check as check_trace_packet

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_planning_ready.json")


def _prefixed(prefix: str, blockers: List[str]) -> List[str]:
    return ["%s:%s" % (prefix, blocker) for blocker in blockers]


def build_report() -> Dict[str, Any]:
    archive = check_archive_policy()
    trace_packet = check_trace_packet()
    dev_smoke_packet = check_dev_smoke_packet()
    dev_feedback = check_dev_feedback()
    trace_cards = check_trace_cards()
    fresh_slice = check_fresh_slice_request()
    dry_run_manifest = check_dry_run_manifest()
    leakage_paths = [path for path in DEFAULT_PATHS if path != DEFAULT_OUTPUT]
    leakage = check_paths(leakage_paths)

    blockers: List[str] = []
    if not archive["abhe_archive_policy_passed"]:
        blockers.extend(_prefixed("archive_policy", archive["blockers"]))
    if not leakage["abhe_no_leakage_boundary_passed"]:
        blockers.extend(_prefixed("no_leakage", leakage["blockers"]))
    if not trace_packet["abhe_trace_extraction_packet_passed"]:
        blockers.extend(_prefixed("trace_packet", trace_packet["blockers"]))
    if not dev_smoke_packet["abhe_dev_smoke_packet_passed"]:
        blockers.extend(_prefixed("dev_smoke_packet", dev_smoke_packet["blockers"]))
    if not dev_feedback["abhe_dev_feedback_check_passed"]:
        blockers.extend(_prefixed("dev_feedback", dev_feedback["blockers"]))
    if not trace_cards["abhe_trace_cards_check_passed"]:
        blockers.extend(_prefixed("trace_cards", trace_cards["blockers"]))
    if not fresh_slice["abhe_fresh_dev_slice_request_passed"]:
        blockers.extend(_prefixed("fresh_slice_request", fresh_slice["blockers"]))
    if not dry_run_manifest["abhe_dev_smoke_dry_run_manifest_passed"]:
        blockers.extend(_prefixed("dry_run_manifest", dry_run_manifest["blockers"]))

    execution_authorized = False
    scorer_authorized = False
    performance_evidence = False

    return {
        "report_scope": "abhe_planning_ready",
        "artifact_kind": "abhe_planning_ready",
        "schema_version": "abhe_planning_ready_v0",
        "abhe_planning_ready": not blockers,
        "archive_policy_ready": archive["abhe_archive_policy_passed"],
        "trace_packet_ready_for_review": trace_packet["abhe_trace_extraction_packet_passed"],
        "trace_card_contract_ready": trace_cards["abhe_trace_cards_check_passed"],
        "dev_smoke_packet_ready_for_review": dev_smoke_packet["abhe_dev_smoke_packet_passed"],
        "post_dev_feedback_contract_ready": dev_feedback["abhe_dev_feedback_check_passed"],
        "fresh_dev_slice_request_ready_for_review": fresh_slice["abhe_fresh_dev_slice_request_passed"],
        "dry_run_runner_materialized": dry_run_manifest["abhe_dev_smoke_dry_run_manifest_passed"],
        "no_leakage_boundary_passed": leakage["abhe_no_leakage_boundary_passed"],
        "execution_authorized": execution_authorized,
        "scorer_authorized": scorer_authorized,
        "performance_evidence": performance_evidence,
        "provider_calls_authorized": False,
        "bfcl_generate_authorized": False,
        "bfcl_evaluate_authorized": False,
        "candidate_generation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "next_required_action": "request_trace_extraction_review_or_dev_smoke_review",
        "component_paths": {
            "trace_packet": str(trace_packet["packet_path"]),
            "dev_smoke_packet": str(dev_smoke_packet["packet_path"]),
            "trace_card_schema": str(trace_cards["schema_path"]),
            "dev_feedback_schema": str(dev_feedback["schema_path"]),
            "fresh_dev_slice_request": str(fresh_slice["request_path"]),
            "dry_run_manifest": str(dry_run_manifest["manifest_path"]),
        },
        "component_summaries": {
            "archive_policy": archive,
            "trace_packet": trace_packet,
            "trace_cards": trace_cards,
            "dev_smoke_packet": dev_smoke_packet,
            "dev_feedback": dev_feedback,
            "fresh_slice_request": fresh_slice,
            "dry_run_manifest": dry_run_manifest,
            "no_leakage": leakage,
        },
        "blockers": sorted(set(blockers)),
    }


def write_report(output: Path, report: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_report()
        if args.write:
            write_report(args.output, report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {
            "report_scope": "abhe_planning_ready",
            "abhe_planning_ready": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    if args.strict and not report["abhe_planning_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
