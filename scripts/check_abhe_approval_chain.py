#!/usr/bin/env python3
"""Aggregate ABHE approval packets without treating missing approvals as planning failure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_candidate_spec_approval_packet import check as check_candidate_spec_approval
from scripts.check_abhe_execution_approval_packet import check as check_execution_approval
from scripts.check_abhe_execution_readiness import build_report as build_execution_readiness
from scripts.check_abhe_fresh_dev_slice_approval_packet import check as check_fresh_slice_approval
from scripts.check_abhe_review_request import check as check_review_request
from scripts.check_abhe_trace_extraction_approval_packet import check as check_trace_approval
from scripts.check_abhe_v0_bfcl_dev_smoke_approval_request import check as check_bfcl_dev_smoke_request
from scripts.check_abhe_v0_bfcl_execution_readiness import build_report as build_bfcl_execution_readiness
from scripts.check_abhe_v0_bfcl_fresh_slice_review import check as check_bfcl_fresh_slice_review
from scripts.check_abhe_v0_materialized_candidates import check as check_bfcl_materialized_candidates

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_approval_chain.json")
BFCL_DATASET_SELECTION_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dataset_path_selection.json")
BFCL_FRESH_SLICE_REVIEW_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_review.json")
BFCL_SOURCE_EXCLUSION_PROOF_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_source_exclusion_proof.json")
BFCL_FRESH_SLICE_MANIFEST_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_manifest.json")
EXPECTED_MISSING_APPROVAL_BLOCKERS = {
    "trace_extraction_approval_packet_missing",
    "fresh_dev_slice_approval_packet_missing",
    "candidate_spec_approval_packet_missing",
    "execution_approval_packet_missing",
}


def _prefix(prefix: str, blockers: List[str]) -> List[str]:
    return ["%s:%s" % (prefix, blocker) for blocker in blockers]


def _packet_approved(summary: Dict[str, Any]) -> bool:
    return summary.get("packet_present") is True and summary.get("authorized") is True and not summary.get("blockers")


def build_report() -> Dict[str, Any]:
    review_request = check_review_request()
    trace_approval = check_trace_approval()
    fresh_slice_approval = check_fresh_slice_approval()
    candidate_spec_approval = check_candidate_spec_approval()
    execution_approval = check_execution_approval()
    execution_readiness = build_execution_readiness()
    bfcl_dev_smoke_request = check_bfcl_dev_smoke_request()
    bfcl_execution_readiness = build_bfcl_execution_readiness()
    bfcl_fresh_slice_review = check_bfcl_fresh_slice_review()
    bfcl_materialized_candidates = check_bfcl_materialized_candidates()
    bfcl_dataset_selection = json.loads(BFCL_DATASET_SELECTION_PATH.read_text(encoding="utf-8")) if BFCL_DATASET_SELECTION_PATH.exists() else {}
    bfcl_fresh_slice_review_artifact = json.loads(BFCL_FRESH_SLICE_REVIEW_PATH.read_text(encoding="utf-8")) if BFCL_FRESH_SLICE_REVIEW_PATH.exists() else {}
    bfcl_source_exclusion_proof = json.loads(BFCL_SOURCE_EXCLUSION_PROOF_PATH.read_text(encoding="utf-8")) if BFCL_SOURCE_EXCLUSION_PROOF_PATH.exists() else {}
    bfcl_fresh_slice_manifest = json.loads(BFCL_FRESH_SLICE_MANIFEST_PATH.read_text(encoding="utf-8")) if BFCL_FRESH_SLICE_MANIFEST_PATH.exists() else {}

    blockers: List[str] = []
    schema_blockers: List[str] = []

    if not review_request.get("abhe_review_request_passed"):
        blockers.extend(_prefix("review_request", review_request.get("blockers", [])))
    if not bfcl_dev_smoke_request.get("abhe_v0_bfcl_dev_smoke_approval_request_passed"):
        blockers.extend(_prefix("bfcl_dev_smoke_request", bfcl_dev_smoke_request.get("blockers", [])))

    approval_checks = {
        "trace_extraction_approval": trace_approval,
        "fresh_dev_slice_approval": fresh_slice_approval,
        "candidate_spec_approval": candidate_spec_approval,
        "execution_approval": execution_approval,
    }
    for name, summary in approval_checks.items():
        for blocker in summary.get("blockers", []):
            if blocker in EXPECTED_MISSING_APPROVAL_BLOCKERS:
                blockers.append(blocker)
            elif summary.get("schema_passed") is not True:
                schema_blockers.append("%s:%s" % (name, blocker))
            else:
                blockers.append("%s:%s" % (name, blocker))

    execution_schema_ok = execution_approval.get("schema_passed") is True
    schema_ready = (
        trace_approval.get("schema_passed") is True
        and fresh_slice_approval.get("schema_passed") is True
        and candidate_spec_approval.get("schema_passed") is True
        and execution_schema_ok
    )
    approval_chain_ready = review_request.get("abhe_review_request_passed") is True and schema_ready and not schema_blockers

    return {
        "report_scope": "abhe_approval_chain",
        "artifact_kind": "abhe_approval_chain",
        "schema_version": "abhe_approval_chain_v0",
        "abhe_approval_chain_ready_for_review": approval_chain_ready,
        "trace_extraction_approved": _packet_approved(trace_approval),
        "fresh_dev_slice_approved": _packet_approved(fresh_slice_approval),
        "candidate_spec_approved": _packet_approved(candidate_spec_approval),
        "execution_approved": _packet_approved(execution_approval),
        "execution_ready": execution_readiness.get("abhe_execution_ready") is True,
        "abhe_v0_bfcl_execution_ready": bfcl_execution_readiness.get("abhe_v0_bfcl_execution_ready") is True,
        "abhe_v0_bfcl_selected_dataset_path": bfcl_dataset_selection.get("selected_dataset_path"),
        "abhe_v0_bfcl_proposed_selected_case_ids_hash": bfcl_fresh_slice_review_artifact.get("proposed_selected_case_ids_hash"),
        "abhe_v0_bfcl_source_exclusion_status": bfcl_source_exclusion_proof.get("overlap_check_status"),
        "abhe_v0_bfcl_overlap_count": bfcl_source_exclusion_proof.get("overlap_count"),
        "abhe_v0_bfcl_candidate_case_hash_count": bfcl_source_exclusion_proof.get("candidate_case_hash_count"),
        "abhe_v0_bfcl_fresh_slice_materialized": bfcl_fresh_slice_manifest.get("fresh_dev_slice_materialized") is True,
        "abhe_v0_bfcl_selected_case_ids_hash": bfcl_fresh_slice_manifest.get("selected_case_ids_hash"),
        "abhe_v0_candidate_materialization_approved": bfcl_materialized_candidates.get("candidate_materialization_approved") is True,
        "abhe_v0_materialized_candidates_ready": bfcl_materialized_candidates.get("abhe_v0_materialized_candidates_check_passed") is True,
        "execution_authorized": False,
        "trace_extraction_authorized": False,
        "fresh_dev_slice_authorized": False,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "component_summaries": {
            "review_request": review_request,
            "trace_extraction_approval": trace_approval,
            "fresh_dev_slice_approval": fresh_slice_approval,
            "candidate_spec_approval": candidate_spec_approval,
            "execution_approval": execution_approval,
            "execution_readiness": execution_readiness,
            "abhe_v0_bfcl_dev_smoke_request": bfcl_dev_smoke_request,
            "abhe_v0_bfcl_execution_readiness": bfcl_execution_readiness,
            "abhe_v0_bfcl_fresh_slice_review": bfcl_fresh_slice_review,
            "abhe_v0_materialized_candidates": bfcl_materialized_candidates,
        },
        "blockers": sorted(set(blockers + schema_blockers)),
        "expected_missing_approval_blockers": sorted(EXPECTED_MISSING_APPROVAL_BLOCKERS),
        "next_required_action": "request_granular_approval_reviews",
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
            "report_scope": "abhe_approval_chain",
            "abhe_approval_chain_ready_for_review": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    if args.strict and not report.get("abhe_approval_chain_ready_for_review"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
