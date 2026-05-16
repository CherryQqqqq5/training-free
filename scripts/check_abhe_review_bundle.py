#!/usr/bin/env python3
"""Build and validate the ABHE review bundle without granting approval."""

from __future__ import annotations

import argparse
import json
import subprocess
from argparse import Namespace
from pathlib import Path
from typing import Any, Dict, List

from scripts.append_abhe_state_transition import validate as validate_transition
from scripts.check_abhe_approval_chain import build_report as build_approval_chain
from scripts.check_abhe_candidate_spec_drafts import check as check_candidate_spec_drafts
from scripts.check_abhe_dev_smoke_packet import check as check_dev_smoke_packet
from scripts.check_abhe_execution_approval_packet import check as check_execution_approval
from scripts.check_abhe_execution_readiness import build_report as build_execution_readiness
from scripts.check_abhe_fresh_dev_slice_request import check as check_fresh_slice_request
from scripts.check_abhe_no_leakage_boundary import DEFAULT_PATHS, check_paths, scan_value
from scripts.check_abhe_review_request import check as check_review_request
from scripts.check_abhe_trace_cards import check as check_trace_cards
from scripts.check_abhe_trace_extraction_packet import check as check_trace_packet
from scripts.plan_abhe_post_dev_update import build_plan as build_post_dev_plan
from scripts.check_abhe_v0_bfcl_dev_feedback import check as check_bfcl_dev_feedback
from scripts.check_abhe_v0_bfcl_dev_smoke_approval_request import check as check_bfcl_dev_smoke_request
from scripts.check_abhe_v0_bfcl_dev_smoke_result import check as check_bfcl_dev_smoke_result
from scripts.check_abhe_v0_bfcl_execution_readiness import build_report as build_bfcl_execution_readiness
from scripts.check_abhe_v0_bfcl_fresh_dev_slice import check as check_bfcl_fresh_slice
from scripts.check_abhe_v0_bfcl_fresh_slice_review import check as check_bfcl_fresh_slice_review
from scripts.check_abhe_v0_candidate_materialization_plan import check as check_bfcl_candidate_materialization
from scripts.plan_abhe_v0_bfcl_archive_transition import build_plan as build_bfcl_archive_transition
from scripts.plan_abhe_v0_bfcl_archive_transition import synthetic_feedback as bfcl_synthetic_feedback

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_review_bundle.json")
PLANNING_READY_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_planning_ready.json")
FORCED_FALSE_FIELDS = {
    "execution_authorized",
    "trace_extraction_authorized",
    "fresh_dev_slice_authorized",
    "candidate_generation_authorized",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
}


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"artifact_missing": str(path)}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _current_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build_bundle() -> Dict[str, Any]:
    planning_ready = _load_json(PLANNING_READY_PATH)
    execution_readiness = build_execution_readiness()
    review_request = check_review_request()
    trace_packet = check_trace_packet()
    trace_cards = check_trace_cards()
    fresh_slice_request = check_fresh_slice_request()
    dev_smoke_packet = check_dev_smoke_packet()
    execution_approval = check_execution_approval()
    candidate_specs = check_candidate_spec_drafts()
    post_dev_synthetic = build_post_dev_plan(synthetic_fixture_only=True)
    bfcl_fresh_slice = check_bfcl_fresh_slice()
    bfcl_fresh_slice_review = check_bfcl_fresh_slice_review()
    bfcl_candidate_materialization = check_bfcl_candidate_materialization()
    bfcl_dev_smoke_request = check_bfcl_dev_smoke_request()
    bfcl_execution_readiness = build_bfcl_execution_readiness()
    bfcl_dry_run_manifest = check_bfcl_dev_smoke_result(dry_run_manifest=True)
    bfcl_dev_feedback_schema = check_bfcl_dev_feedback(schema_only=True)
    bfcl_archive_transition = build_bfcl_archive_transition(bfcl_synthetic_feedback(), synthetic_fixture_only=True)
    transition_blockers = validate_transition(Namespace(
        entry_id="state_tracking_v0",
        from_status="proposal_ready",
        to_status="dev_smoke_requested",
        reason="review_bundle_dry_run",
        dry_run=True,
        write=False,
    ))
    transition_writer = {
        "report_scope": "abhe_state_transition_dry_run_check",
        "state_transition_dry_run_passed": not transition_blockers,
        "blockers": transition_blockers,
    }
    approval_chain = build_approval_chain()
    leakage = check_paths([path for path in DEFAULT_PATHS if path != DEFAULT_OUTPUT])

    bundle = {
        "report_scope": "abhe_review_bundle",
        "artifact_kind": "abhe_review_bundle",
        "schema_version": "abhe_review_bundle_v0",
        "bundle_is_approval": False,
        "bundle_is_performance_evidence": False,
        "abhe_review_bundle_ready": True,
        "planning_readiness_ready": planning_ready.get("abhe_planning_ready") is True,
        "execution_readiness_ready": execution_readiness.get("execution_readiness_check_passed") is True,
        "review_request_ready": review_request.get("abhe_review_request_passed") is True,
        "trace_extraction_packet_ready": trace_packet.get("abhe_trace_extraction_packet_passed") is True,
        "trace_card_contract_ready": trace_cards.get("abhe_trace_cards_check_passed") is True,
        "fresh_dev_slice_request_ready": fresh_slice_request.get("abhe_fresh_dev_slice_request_passed") is True,
        "dev_smoke_packet_ready": dev_smoke_packet.get("abhe_dev_smoke_packet_passed") is True,
        "execution_approval_schema_ready": execution_approval.get("schema_passed") is True,
        "candidate_spec_drafts_ready": candidate_specs.get("abhe_candidate_spec_drafts_passed") is True,
        "post_dev_synthetic_planner_ready": post_dev_synthetic.get("abhe_post_dev_update_plan_passed") is True,
        "state_transition_dry_run_writer_ready": transition_writer["state_transition_dry_run_passed"],
        "abhe_v0_bfcl_fresh_slice_plan_ready": bfcl_fresh_slice.get("abhe_v0_bfcl_fresh_dev_slice_check_passed") is True,
        "abhe_v0_bfcl_fresh_slice_review_ready": bfcl_fresh_slice_review.get("abhe_v0_bfcl_fresh_slice_review_passed") is True,
        "abhe_v0_candidate_materialization_plan_ready": bfcl_candidate_materialization.get("abhe_v0_candidate_materialization_plan_check_passed") is True,
        "abhe_v0_bfcl_dev_smoke_request_ready": bfcl_dev_smoke_request.get("abhe_v0_bfcl_dev_smoke_approval_request_passed") is True,
        "abhe_v0_bfcl_execution_ready": bfcl_execution_readiness.get("abhe_v0_bfcl_execution_ready") is True,
        "abhe_v0_bfcl_dry_run_manifest_ready": bfcl_dry_run_manifest.get("abhe_v0_bfcl_dev_smoke_result_check_passed") is True,
        "abhe_v0_bfcl_dev_feedback_schema_ready": bfcl_dev_feedback_schema.get("abhe_v0_bfcl_dev_feedback_check_passed") is True,
        "abhe_v0_bfcl_archive_transition_ready": bfcl_archive_transition.get("abhe_v0_bfcl_archive_transition_plan_passed") is True,
        "approval_chain_ready_for_review": approval_chain.get("abhe_approval_chain_ready_for_review") is True,
        "no_leakage_status": leakage.get("abhe_no_leakage_boundary_passed") is True,
        "execution_authorized": False,
        "trace_extraction_authorized": False,
        "fresh_dev_slice_authorized": False,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "component_paths": {
            "planning_ready": str(PLANNING_READY_PATH),
            "execution_readiness": "outputs/artifacts/stage1_bfcl_acceptance/abhe_execution_readiness.json",
            "review_request": str(review_request["request_path"]),
            "trace_extraction_packet": str(trace_packet["packet_path"]),
            "trace_card_schema": str(trace_cards["schema_path"]),
            "fresh_dev_slice_request": str(fresh_slice_request["request_path"]),
            "dev_smoke_packet": str(dev_smoke_packet["packet_path"]),
            "execution_approval_schema": str(execution_approval["schema_path"]),
            "candidate_spec_drafts": "docs/stage1_abhe_*_candidate_spec_draft.md",
            "approval_chain": "outputs/artifacts/stage1_bfcl_acceptance/abhe_approval_chain.json",
            "abhe_v0_bfcl_fresh_dev_slice_plan": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_plan.json",
            "abhe_v0_bfcl_dataset_path_review": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dataset_path_review.json",
            "abhe_v0_bfcl_category_review": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_category_review.json",
            "abhe_v0_bfcl_fresh_dev_slice_review": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_review.json",
            "abhe_v0_bfcl_source_exclusion_proof": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_source_exclusion_proof.json",
            "abhe_v0_candidate_materialization_plan": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_materialization_plan.json",
            "abhe_v0_bfcl_dev_smoke_approval_request": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_request.json",
            "abhe_v0_bfcl_execution_readiness": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_execution_readiness.json",
            "abhe_v0_bfcl_dev_feedback_schema": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_feedback.schema.json",
            "abhe_v0_bfcl_archive_transition_plan": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_archive_transition_plan.json",
        },
        "component_summaries": {
            "planning_ready": planning_ready,
            "execution_readiness": execution_readiness,
            "review_request": review_request,
            "trace_extraction_packet": trace_packet,
            "trace_card_contract": trace_cards,
            "fresh_dev_slice_request": fresh_slice_request,
            "dev_smoke_packet": dev_smoke_packet,
            "execution_approval_schema": execution_approval,
            "candidate_spec_drafts": candidate_specs,
            "post_dev_synthetic_planner": post_dev_synthetic,
            "state_transition_dry_run_writer": transition_writer,
            "approval_chain": approval_chain,
            "abhe_v0_bfcl_fresh_slice": bfcl_fresh_slice,
            "abhe_v0_bfcl_fresh_slice_review": bfcl_fresh_slice_review,
            "abhe_v0_candidate_materialization": bfcl_candidate_materialization,
            "abhe_v0_bfcl_dev_smoke_request": bfcl_dev_smoke_request,
            "abhe_v0_bfcl_execution_readiness": bfcl_execution_readiness,
            "abhe_v0_bfcl_dry_run_manifest": bfcl_dry_run_manifest,
            "abhe_v0_bfcl_dev_feedback_schema": bfcl_dev_feedback_schema,
            "abhe_v0_bfcl_archive_transition": bfcl_archive_transition,
            "no_leakage": leakage,
        },
        "commit": _current_commit(),
        "next_required_action": "request_granular_approval_reviews",
    }
    blockers = validate_bundle(bundle)
    bundle["abhe_review_bundle_ready"] = not blockers
    bundle["blockers"] = blockers
    return bundle


def validate_bundle(bundle: Dict[str, Any]) -> List[str]:
    blockers = []
    if bundle.get("artifact_kind") != "abhe_review_bundle":
        blockers.append("review_bundle_artifact_kind_invalid:%r" % bundle.get("artifact_kind"))
    if bundle.get("schema_version") != "abhe_review_bundle_v0":
        blockers.append("review_bundle_schema_version_invalid:%r" % bundle.get("schema_version"))
    if bundle.get("bundle_is_approval") is not False:
        blockers.append("review_bundle_must_not_be_approval")
    if bundle.get("bundle_is_performance_evidence") is not False:
        blockers.append("review_bundle_must_not_be_performance_evidence")
    for key in sorted(FORCED_FALSE_FIELDS):
        if bundle.get(key) is not False:
            blockers.append("review_bundle_%s_not_false:%r" % (key, bundle.get(key)))
    required_ready = [
        "execution_readiness_ready",
        "review_request_ready",
        "trace_extraction_packet_ready",
        "trace_card_contract_ready",
        "fresh_dev_slice_request_ready",
        "dev_smoke_packet_ready",
        "execution_approval_schema_ready",
        "candidate_spec_drafts_ready",
        "post_dev_synthetic_planner_ready",
        "state_transition_dry_run_writer_ready",
        "abhe_v0_bfcl_fresh_slice_plan_ready",
        "abhe_v0_bfcl_fresh_slice_review_ready",
        "abhe_v0_candidate_materialization_plan_ready",
        "abhe_v0_bfcl_dev_smoke_request_ready",
        "abhe_v0_bfcl_dry_run_manifest_ready",
        "abhe_v0_bfcl_dev_feedback_schema_ready",
        "abhe_v0_bfcl_archive_transition_ready",
        "approval_chain_ready_for_review",
        "no_leakage_status",
    ]
    for key in required_ready:
        if bundle.get(key) is not True:
            blockers.append("review_bundle_component_not_ready:%s" % key)
    blockers.extend(scan_value(bundle, label="review_bundle"))
    return sorted(set(blockers))


def check(output: Path = DEFAULT_OUTPUT) -> Dict[str, Any]:
    # The review bundle is generated from live component checkers. During schema
    # evolution, an older persisted bundle may lack newly added review-only
    # components, so validating stale persisted content would block the very
    # write that updates it. The generated bundle is still validated inside
    # build_bundle before it is returned.
    return build_bundle()


def write_bundle(output: Path, bundle: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        bundle = check(args.output)
        if args.write:
            write_bundle(args.output, bundle)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        bundle = {
            "report_scope": "abhe_review_bundle",
            "abhe_review_bundle_ready": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(bundle, sort_keys=True) if args.compact else json.dumps(bundle, indent=2, sort_keys=True))
    if args.strict and not bundle.get("abhe_review_bundle_ready"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
