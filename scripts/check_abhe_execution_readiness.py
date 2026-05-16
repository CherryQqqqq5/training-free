#!/usr/bin/env python3
"""Report executable ABHE readiness separately from planning readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_dev_smoke_dry_run_manifest import check as check_dry_run_manifest
from scripts.check_abhe_dev_smoke_packet import DEFAULT_PACKET as DEFAULT_DEV_SMOKE_PACKET
from scripts.check_abhe_dev_smoke_packet import check as check_dev_smoke_packet
from scripts.check_abhe_candidate_spec_approval_packet import check as check_candidate_spec_approval_packet
from scripts.check_abhe_execution_approval_packet import check as check_execution_approval_packet
from scripts.check_abhe_fresh_dev_slice_approval_packet import check as check_fresh_slice_approval_packet
from scripts.check_abhe_fresh_dev_slice_request import check as check_fresh_slice_request
from scripts.check_abhe_trace_extraction_approval_packet import check as check_trace_extraction_approval_packet
from scripts.check_abhe_v0_bfcl_execution_readiness import build_report as build_bfcl_execution_readiness

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_execution_readiness.json")


def _load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def build_report(dev_smoke_packet_path: Path = DEFAULT_DEV_SMOKE_PACKET) -> Dict[str, Any]:
    fresh_slice = check_fresh_slice_request()
    dry_run_manifest = check_dry_run_manifest()
    dev_smoke_packet = check_dev_smoke_packet(dev_smoke_packet_path)
    trace_extraction_approval = check_trace_extraction_approval_packet()
    fresh_slice_approval = check_fresh_slice_approval_packet()
    candidate_spec_approval = check_candidate_spec_approval_packet()
    execution_approval = check_execution_approval_packet()
    packet = _load_json(dev_smoke_packet_path) if dev_smoke_packet_path.exists() else {}
    bfcl_execution_readiness = build_bfcl_execution_readiness()

    blockers: List[str] = []
    if not fresh_slice["abhe_fresh_dev_slice_request_passed"]:
        blockers.extend("fresh_slice_request:%s" % blocker for blocker in fresh_slice["blockers"])
    if not dry_run_manifest["abhe_dev_smoke_dry_run_manifest_passed"]:
        blockers.extend("dry_run_manifest:%s" % blocker for blocker in dry_run_manifest["blockers"])
    if not dev_smoke_packet["abhe_dev_smoke_packet_passed"]:
        blockers.extend("dev_smoke_packet:%s" % blocker for blocker in dev_smoke_packet["blockers"])
    if not trace_extraction_approval.get("schema_passed"):
        blockers.extend("trace_extraction_approval:%s" % blocker for blocker in trace_extraction_approval["blockers"] if blocker != "trace_extraction_approval_packet_missing")
    if not fresh_slice_approval.get("schema_passed"):
        blockers.extend("fresh_slice_approval:%s" % blocker for blocker in fresh_slice_approval["blockers"] if blocker != "fresh_dev_slice_approval_packet_missing")
    if not candidate_spec_approval.get("schema_passed"):
        blockers.extend("candidate_spec_approval:%s" % blocker for blocker in candidate_spec_approval["blockers"] if blocker != "candidate_spec_approval_packet_missing")
    approval_missing = "execution_approval_packet_missing" in execution_approval.get("blockers", [])
    if not execution_approval.get("schema_passed"):
        blockers.extend("execution_approval:%s" % blocker for blocker in execution_approval["blockers"] if blocker != "execution_approval_packet_missing")

    if "trace_extraction_approval_packet_missing" in trace_extraction_approval.get("blockers", []):
        blockers.append("trace_extraction_approval_missing")
    if "fresh_dev_slice_approval_packet_missing" in fresh_slice_approval.get("blockers", []):
        blockers.append("fresh_dev_slice_approval_missing")
    if "candidate_spec_approval_packet_missing" in candidate_spec_approval.get("blockers", []):
        blockers.append("candidate_spec_approval_missing")
    if packet.get("runner_materialized") is not True:
        blockers.append("dry_run_runner_not_materialized")
    if packet.get("fresh_slice_materialized") is not True:
        blockers.append("fresh_dev_slice_not_materialized")
    if packet.get("authorized") is not True:
        blockers.append("execution_approval_missing")
    if packet.get("candidate_generation_authorized") is not True or packet.get("candidate_rule_path") == "pending_review_no_candidate_rule_generated":
        blockers.append("candidate_rule_not_generated_or_authorized")
    if packet.get("runtime_config_path") == "pending_review_no_runtime_config_selected":
        blockers.append("runtime_config_not_selected")
    if packet.get("scorer_authorized") is not True:
        blockers.append("scorer_authorization_false")
    if approval_missing:
        blockers.append("execution_approval_missing")

    expected_fail_closed_blockers = {
        "trace_extraction_approval_missing",
        "fresh_dev_slice_approval_missing",
        "candidate_spec_approval_missing",
        "fresh_dev_slice_not_materialized",
        "execution_approval_missing",
        "candidate_rule_not_generated_or_authorized",
        "runtime_config_not_selected",
        "scorer_authorization_false",
    }
    execution_readiness_check_passed = (
        expected_fail_closed_blockers.issubset(set(blockers))
        and trace_extraction_approval.get("schema_passed") is True
        and fresh_slice_approval.get("schema_passed") is True
        and candidate_spec_approval.get("schema_passed") is True
        and execution_approval.get("schema_passed") is True
    )

    return {
        "report_scope": "abhe_execution_readiness",
        "artifact_kind": "abhe_execution_readiness",
        "schema_version": "abhe_execution_readiness_v0",
        "abhe_execution_ready": False if blockers else True,
        "execution_readiness_check_passed": execution_readiness_check_passed,
        "planning_ready_is_not_execution_ready": True,
        "dry_run_runner_materialized": packet.get("runner_materialized") is True,
        "fresh_dev_slice_materialized": packet.get("fresh_slice_materialized") is True,
        "execution_authorized": packet.get("authorized") is True,
        "scorer_authorized": packet.get("scorer_authorized") is True,
        "performance_evidence": False,
        "candidate_generation_authorized": packet.get("candidate_generation_authorized") is True,
        "component_summaries": {
            "abhe_v0_bfcl_execution_readiness": bfcl_execution_readiness,
            "fresh_slice_request": fresh_slice,
            "dry_run_manifest": dry_run_manifest,
            "dev_smoke_packet": dev_smoke_packet,
            "trace_extraction_approval": trace_extraction_approval,
            "fresh_slice_approval": fresh_slice_approval,
            "candidate_spec_approval": candidate_spec_approval,
            "execution_approval": execution_approval,
        },
        "blockers": sorted(set(blockers)),
    }


def write_report(output: Path, report: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dev-smoke-packet", type=Path, default=DEFAULT_DEV_SMOKE_PACKET)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.dev_smoke_packet)
        if args.write:
            write_report(args.output, report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {
            "report_scope": "abhe_execution_readiness",
            "abhe_execution_ready": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    if args.strict and not report.get("execution_readiness_check_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
