#!/usr/bin/env python3
"""Aggregate ABHE planning checkers into one fail-closed readiness report."""

from __future__ import annotations

import argparse
import json
from argparse import Namespace
from pathlib import Path
from typing import Any, Dict, List

from scripts.append_abhe_state_transition import validate as validate_transition
from scripts.check_abhe_approval_chain import build_report as build_approval_chain
from scripts.check_abhe_archive_policy import check as check_archive_policy
from scripts.check_abhe_candidate_spec_approval_packet import check as check_candidate_spec_approval_packet
from scripts.check_abhe_candidate_spec_drafts import check as check_candidate_spec_drafts
from scripts.check_abhe_dev_feedback import check as check_dev_feedback
from scripts.check_abhe_dev_smoke_dry_run_manifest import check as check_dry_run_manifest
from scripts.check_abhe_dev_smoke_packet import check as check_dev_smoke_packet
from scripts.check_abhe_execution_approval_packet import check as check_execution_approval_packet
from scripts.check_abhe_fresh_dev_slice_approval_packet import check as check_fresh_slice_approval_packet
from scripts.check_abhe_fresh_dev_slice_request import check as check_fresh_slice_request
from scripts.check_abhe_no_leakage_boundary import DEFAULT_PATHS, check_paths
from scripts.check_abhe_review_bundle import check as check_review_bundle
from scripts.check_abhe_review_request import check as check_review_request
from scripts.check_abhe_trace_cards import check as check_trace_cards
from scripts.check_abhe_trace_extraction_approval_packet import check as check_trace_extraction_approval_packet
from scripts.check_abhe_trace_extraction_packet import check as check_trace_packet
from scripts.plan_abhe_post_dev_update import build_plan as build_post_dev_plan
from scripts.check_abhe_v0_bfcl_dev_feedback import check as check_bfcl_dev_feedback
from scripts.check_abhe_v0_bfcl_case_delta_analysis import check as check_bfcl_case_delta
from scripts.check_abhe_v0_bfcl_dev_smoke_approval_request import check as check_bfcl_dev_smoke_request
from scripts.check_abhe_v0_bfcl_dev_smoke_result import check as check_bfcl_dev_smoke_result
from scripts.check_abhe_v0_bfcl_execution_readiness import build_report as build_bfcl_execution_readiness
from scripts.check_abhe_v0_bfcl_fresh_dev_slice import check as check_bfcl_fresh_slice
from scripts.check_abhe_v0_bfcl_fresh_slice_review import check as check_bfcl_fresh_slice_review
from scripts.check_abhe_v0_candidate_materialization_plan import check as check_bfcl_candidate_materialization
from scripts.check_abhe_v0_materialized_candidates import check as check_bfcl_materialized_candidates
from scripts.check_abhe_v0_runtime_candidate_adapter import check as check_bfcl_runtime_candidate_adapter
from scripts.check_abhe_v0_bfcl_same_slice_rerun_stability import check as check_bfcl_same_slice_stability
from scripts.check_abhe_v0_expanded_dev_smoke_request import check as check_bfcl_expanded_dev_smoke_request
from scripts.check_abhe_v0_runtime_slot_observability_plan import check as check_runtime_slot_observability_plan
from scripts.check_abhe_v0_runtime_slot_observability_fixture import check as check_runtime_slot_observability_fixture
from scripts.check_abhe_v0_runtime_slot_observability_review import check as check_runtime_slot_observability_review
from scripts.plan_abhe_v0_bfcl_archive_transition import build_plan as build_bfcl_archive_transition
from scripts.plan_abhe_v0_bfcl_archive_transition import synthetic_feedback as bfcl_synthetic_feedback

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_planning_ready.json")


def _prefixed(prefix: str, blockers: List[str]) -> List[str]:
    return ["%s:%s" % (prefix, blocker) for blocker in blockers]


def _summary(report: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    summary = {key: report.get(key) for key in keys if key in report}
    if "blockers" in report:
        summary["blockers"] = report.get("blockers", [])
    return summary


def build_report() -> Dict[str, Any]:
    archive = check_archive_policy()
    trace_packet = check_trace_packet()
    dev_smoke_packet = check_dev_smoke_packet()
    dev_feedback = check_dev_feedback()
    trace_cards = check_trace_cards()
    fresh_slice = check_fresh_slice_request()
    dry_run_manifest = check_dry_run_manifest()
    review_request = check_review_request()
    trace_extraction_approval = check_trace_extraction_approval_packet()
    fresh_slice_approval = check_fresh_slice_approval_packet()
    candidate_spec_approval = check_candidate_spec_approval_packet()
    execution_approval = check_execution_approval_packet()
    candidate_specs = check_candidate_spec_drafts()
    post_dev_synthetic = build_post_dev_plan(synthetic_fixture_only=True)
    bfcl_fresh_slice = check_bfcl_fresh_slice()
    bfcl_fresh_slice_review = check_bfcl_fresh_slice_review()
    bfcl_candidate_materialization = check_bfcl_candidate_materialization()
    bfcl_materialized_candidates = check_bfcl_materialized_candidates()
    bfcl_runtime_candidate_adapter = check_bfcl_runtime_candidate_adapter()
    bfcl_dev_smoke_request = check_bfcl_dev_smoke_request()
    bfcl_execution_readiness = build_bfcl_execution_readiness()
    bfcl_dry_run_manifest = check_bfcl_dev_smoke_result(dry_run_manifest=True)
    bfcl_dev_smoke_result = check_bfcl_dev_smoke_result()
    bfcl_dev_feedback_schema = check_bfcl_dev_feedback(schema_only=True)
    bfcl_dev_feedback = check_bfcl_dev_feedback()
    bfcl_case_delta = check_bfcl_case_delta()
    bfcl_same_slice_stability = check_bfcl_same_slice_stability()
    bfcl_expanded_dev_smoke_request = check_bfcl_expanded_dev_smoke_request()
    runtime_slot_observability_plan = check_runtime_slot_observability_plan()
    runtime_slot_observability_fixture = check_runtime_slot_observability_fixture()
    runtime_slot_observability_review = check_runtime_slot_observability_review()
    bfcl_archive_transition = build_bfcl_archive_transition(bfcl_synthetic_feedback(), synthetic_fixture_only=True)
    transition_blockers = validate_transition(Namespace(
        entry_id="state_tracking_v0",
        from_status="proposal_ready",
        to_status="dev_smoke_requested",
        reason="planning_ready_dry_run",
        dry_run=True,
        write=False,
    ))
    transition_writer = {
        "report_scope": "abhe_state_transition_dry_run_check",
        "state_transition_dry_run_passed": not transition_blockers,
        "blockers": transition_blockers,
    }
    approval_chain = build_approval_chain()
    review_bundle = check_review_bundle()
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
    if not review_request["abhe_review_request_passed"]:
        blockers.extend(_prefixed("review_request", review_request["blockers"]))
    if not approval_chain.get("abhe_approval_chain_ready_for_review"):
        blockers.extend(_prefixed("approval_chain", [blocker for blocker in approval_chain["blockers"] if not blocker.endswith("_approval_packet_missing")]))
    if not review_bundle.get("abhe_review_bundle_ready"):
        blockers.extend(_prefixed("review_bundle", review_bundle["blockers"]))
    if not trace_extraction_approval.get("schema_passed"):
        blockers.extend(_prefixed("trace_extraction_approval_schema", [blocker for blocker in trace_extraction_approval["blockers"] if blocker != "trace_extraction_approval_packet_missing"]))
    if not fresh_slice_approval.get("schema_passed"):
        blockers.extend(_prefixed("fresh_dev_slice_approval_schema", [blocker for blocker in fresh_slice_approval["blockers"] if blocker != "fresh_dev_slice_approval_packet_missing"]))
    if not candidate_spec_approval.get("schema_passed"):
        blockers.extend(_prefixed("candidate_spec_approval_schema", [blocker for blocker in candidate_spec_approval["blockers"] if blocker != "candidate_spec_approval_packet_missing"]))
    if not execution_approval.get("schema_passed"):
        blockers.extend(_prefixed("execution_approval_schema", [blocker for blocker in execution_approval["blockers"] if blocker != "execution_approval_packet_missing"]))
    if not candidate_specs["abhe_candidate_spec_drafts_passed"]:
        blockers.extend(_prefixed("candidate_specs", candidate_specs["blockers"]))
    if not post_dev_synthetic.get("abhe_post_dev_update_plan_passed"):
        blockers.extend(_prefixed("post_dev_synthetic", post_dev_synthetic["blockers"]))
    if not transition_writer["state_transition_dry_run_passed"]:
        blockers.extend(_prefixed("state_transition_writer", transition_writer["blockers"]))
    if not bfcl_fresh_slice.get("abhe_v0_bfcl_fresh_dev_slice_check_passed"):
        blockers.extend(_prefixed("bfcl_fresh_slice", bfcl_fresh_slice.get("blockers", [])))
    if not bfcl_fresh_slice_review.get("abhe_v0_bfcl_fresh_slice_review_passed"):
        blockers.extend(_prefixed("bfcl_fresh_slice_review", bfcl_fresh_slice_review.get("blockers", [])))
    if not bfcl_candidate_materialization.get("abhe_v0_candidate_materialization_plan_check_passed"):
        blockers.extend(_prefixed("bfcl_candidate_materialization", bfcl_candidate_materialization.get("blockers", [])))
    if not bfcl_materialized_candidates.get("abhe_v0_materialized_candidates_check_passed"):
        blockers.extend(_prefixed("bfcl_materialized_candidates", bfcl_materialized_candidates.get("blockers", [])))
    if not bfcl_runtime_candidate_adapter.get("adapter_ready"):
        blockers.extend(_prefixed("bfcl_runtime_candidate_adapter", bfcl_runtime_candidate_adapter.get("blockers", [])))
    if not bfcl_dev_smoke_request.get("abhe_v0_bfcl_dev_smoke_approval_request_passed"):
        blockers.extend(_prefixed("bfcl_dev_smoke_request", bfcl_dev_smoke_request.get("blockers", [])))
    if not bfcl_execution_readiness.get("execution_readiness_check_passed"):
        blockers.extend(_prefixed("bfcl_execution_readiness", bfcl_execution_readiness.get("blockers", [])))
    if not bfcl_dry_run_manifest.get("abhe_v0_bfcl_dev_smoke_result_check_passed"):
        blockers.extend(_prefixed("bfcl_dry_run_manifest", bfcl_dry_run_manifest.get("blockers", [])))
    if not bfcl_dev_feedback_schema.get("abhe_v0_bfcl_dev_feedback_check_passed"):
        blockers.extend(_prefixed("bfcl_dev_feedback_schema", bfcl_dev_feedback_schema.get("blockers", [])))
    if not bfcl_dev_smoke_result.get("abhe_v0_bfcl_dev_smoke_result_check_passed"):
        blockers.extend(_prefixed("bfcl_dev_smoke_result", bfcl_dev_smoke_result.get("blockers", [])))
    if not bfcl_dev_feedback.get("abhe_v0_bfcl_dev_feedback_check_passed"):
        blockers.extend(_prefixed("bfcl_dev_feedback", bfcl_dev_feedback.get("blockers", [])))
    if not bfcl_archive_transition.get("abhe_v0_bfcl_archive_transition_plan_passed"):
        blockers.extend(_prefixed("bfcl_archive_transition", bfcl_archive_transition.get("blockers", [])))
    if not bfcl_case_delta.get("abhe_v0_bfcl_case_delta_analysis_check_passed"):
        blockers.extend(_prefixed("bfcl_case_delta_analysis", bfcl_case_delta.get("blockers", [])))
    if not bfcl_same_slice_stability.get("same_slice_rerun_stability_check_passed"):
        blockers.extend(_prefixed("bfcl_same_slice_stability", bfcl_same_slice_stability.get("blockers", [])))
    if not bfcl_expanded_dev_smoke_request.get("abhe_v0_expanded_dev_smoke_request_passed"):
        blockers.extend(_prefixed("bfcl_expanded_dev_smoke_request", bfcl_expanded_dev_smoke_request.get("blockers", [])))
    if not runtime_slot_observability_plan.get("observability_plan_check_passed"):
        blockers.extend(_prefixed("runtime_slot_observability_plan", runtime_slot_observability_plan.get("blockers", [])))
    if not runtime_slot_observability_fixture.get("observability_fixture_check_passed"):
        blockers.extend(_prefixed("runtime_slot_observability_fixture", runtime_slot_observability_fixture.get("blockers", [])))
    if not runtime_slot_observability_review.get("observability_review_check_passed"):
        blockers.extend(_prefixed("runtime_slot_observability_review", runtime_slot_observability_review.get("blockers", [])))

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
        "review_request_ready": review_request["abhe_review_request_passed"],
        "review_bundle_ready": review_bundle.get("abhe_review_bundle_ready") is True,
        "approval_chain_ready_for_review": approval_chain.get("abhe_approval_chain_ready_for_review") is True,
        "trace_extraction_approval_schema_ready": trace_extraction_approval.get("schema_passed") is True,
        "fresh_dev_slice_approval_schema_ready": fresh_slice_approval.get("schema_passed") is True,
        "candidate_spec_approval_schema_ready": candidate_spec_approval.get("schema_passed") is True,
        "execution_approval_schema_ready": execution_approval.get("schema_passed") is True,
        "execution_approval_packet_present": execution_approval.get("packet_present") is True,
        "candidate_spec_drafts_ready": candidate_specs["abhe_candidate_spec_drafts_passed"],
        "post_dev_synthetic_planner_ready": post_dev_synthetic.get("abhe_post_dev_update_plan_passed") is True,
        "state_transition_dry_run_ready": transition_writer["state_transition_dry_run_passed"],
        "abhe_v0_bfcl_fresh_slice_plan_ready": bfcl_fresh_slice.get("abhe_v0_bfcl_fresh_dev_slice_check_passed") is True,
        "abhe_v0_bfcl_fresh_slice_review_ready": bfcl_fresh_slice_review.get("abhe_v0_bfcl_fresh_slice_review_passed") is True,
        "abhe_v0_candidate_materialization_plan_ready": bfcl_candidate_materialization.get("abhe_v0_candidate_materialization_plan_check_passed") is True,
        "abhe_v0_candidate_materialization_approved": bfcl_materialized_candidates.get("candidate_materialization_approved") is True,
        "abhe_v0_materialized_candidates_ready": bfcl_materialized_candidates.get("abhe_v0_materialized_candidates_check_passed") is True,
        "abhe_v0_runtime_candidate_adapter_ready": bfcl_runtime_candidate_adapter.get("adapter_ready") is True,
        "abhe_v0_bfcl_dev_smoke_request_ready": bfcl_dev_smoke_request.get("abhe_v0_bfcl_dev_smoke_approval_request_passed") is True,
        "abhe_v0_bfcl_execution_ready": bfcl_execution_readiness.get("abhe_v0_bfcl_execution_ready") is True,
        "abhe_v0_bfcl_dry_run_manifest_ready": bfcl_dry_run_manifest.get("abhe_v0_bfcl_dev_smoke_result_check_passed") is True,
        "abhe_v0_bfcl_dev_smoke_result_ready": bfcl_dev_smoke_result.get("abhe_v0_bfcl_dev_smoke_result_check_passed") is True,
        "abhe_v0_bfcl_dev_feedback_ready": bfcl_dev_feedback.get("abhe_v0_bfcl_dev_feedback_check_passed") is True,
        "abhe_v0_bfcl_dev_feedback_schema_ready": bfcl_dev_feedback_schema.get("abhe_v0_bfcl_dev_feedback_check_passed") is True,
        "abhe_v0_bfcl_archive_transition_ready": bfcl_archive_transition.get("abhe_v0_bfcl_archive_transition_plan_passed") is True,
        "abhe_v0_bfcl_case_delta_analysis_ready": bfcl_case_delta.get("abhe_v0_bfcl_case_delta_analysis_check_passed") is True,
        "abhe_v0_bfcl_same_slice_rerun_stability_ready": bfcl_same_slice_stability.get("same_slice_rerun_stability_check_passed") is True,
        "abhe_v0_expanded_dev_smoke_request_ready": bfcl_expanded_dev_smoke_request.get("abhe_v0_expanded_dev_smoke_request_passed") is True,
        "abhe_v0_runtime_slot_observability_plan_ready": runtime_slot_observability_plan.get("observability_plan_check_passed") is True,
        "abhe_v0_runtime_slot_observability_fixture_ready": runtime_slot_observability_fixture.get("observability_fixture_check_passed") is True,
        "abhe_v0_runtime_slot_observability_review_ready": runtime_slot_observability_review.get("observability_review_check_passed") is True,
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
        "next_required_action": "request_bounded_bfcl_rerun_approval_with_observability_enabled",
        "component_paths": {
            "trace_packet": str(trace_packet["packet_path"]),
            "dev_smoke_packet": str(dev_smoke_packet["packet_path"]),
            "trace_card_schema": str(trace_cards["schema_path"]),
            "dev_feedback_schema": str(dev_feedback["schema_path"]),
            "fresh_dev_slice_request": str(fresh_slice["request_path"]),
            "dry_run_manifest": str(dry_run_manifest["manifest_path"]),
            "review_request": str(review_request["request_path"]),
            "review_bundle": "outputs/artifacts/stage1_bfcl_acceptance/abhe_review_bundle.json",
            "approval_chain": "outputs/artifacts/stage1_bfcl_acceptance/abhe_approval_chain.json",
            "trace_extraction_approval_schema": str(trace_extraction_approval["schema_path"]),
            "fresh_dev_slice_approval_schema": str(fresh_slice_approval["schema_path"]),
            "candidate_spec_approval_schema": str(candidate_spec_approval["schema_path"]),
            "execution_approval_schema": str(execution_approval["schema_path"]),
            "abhe_v0_bfcl_fresh_dev_slice_plan": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_plan.json",
            "abhe_v0_bfcl_dataset_path_review": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dataset_path_review.json",
            "abhe_v0_bfcl_category_review": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_category_review.json",
            "abhe_v0_bfcl_fresh_dev_slice_review": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_review.json",
            "abhe_v0_bfcl_source_exclusion_proof": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_source_exclusion_proof.json",
            "abhe_v0_candidate_materialization_plan": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_materialization_plan.json",
            "abhe_v0_candidate_materialization_approval_packet": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_materialization_approval_packet.json",
            "abhe_v0_materialized_candidates": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_materialized_candidates.json",
            "abhe_v0_bfcl_dev_smoke_approval_request": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_request.json",
            "abhe_v0_bfcl_dev_smoke_approval_packet": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_packet.json",
            "abhe_v0_bfcl_dev_smoke_execution_failure": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_execution_failure.json",
            "abhe_v0_runtime_candidate_adapter": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_candidate_adapter.json",
            "abhe_v0_provider_preflight": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_provider_preflight.json",
            "abhe_v0_bfcl_execution_readiness": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_execution_readiness.json",
            "abhe_v0_bfcl_dev_smoke_dry_run_manifest": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_dry_run_manifest.json",
            "abhe_v0_bfcl_dev_smoke_result": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_result.json",
            "abhe_v0_bfcl_dev_feedback": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_feedback.json",
            "abhe_v0_bfcl_case_delta_analysis": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_case_delta_analysis.json",
            "abhe_v0_bfcl_dev_feedback_schema": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_feedback.schema.json",
            "abhe_v0_bfcl_same_slice_rerun_stability": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_same_slice_rerun_stability.json",
            "abhe_v0_expanded_dev_smoke_request": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_expanded_dev_smoke_request.json",
            "abhe_v0_next_trace_audit": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_next_trace_audit.json",
            "abhe_v0_bfcl_archive_transition_plan": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_archive_transition_plan.json",
            "abhe_v0_runtime_slot_observability_plan": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_observability_plan.json",
            "abhe_v0_runtime_slot_observability_fixture": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_observability_fixture.json",
            "abhe_v0_runtime_slot_observability_review": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_observability_review.json",
        },
        "component_summaries": {
            "archive_policy": archive,
            "trace_packet": trace_packet,
            "trace_cards": trace_cards,
            "dev_smoke_packet": dev_smoke_packet,
            "dev_feedback": dev_feedback,
            "fresh_slice_request": fresh_slice,
            "dry_run_manifest": dry_run_manifest,
            "review_request": review_request,
            "review_bundle": review_bundle,
            "approval_chain": approval_chain,
            "trace_extraction_approval_schema": trace_extraction_approval,
            "fresh_dev_slice_approval_schema": fresh_slice_approval,
            "candidate_spec_approval_schema": candidate_spec_approval,
            "execution_approval": execution_approval,
            "candidate_specs": candidate_specs,
            "post_dev_synthetic": post_dev_synthetic,
            "state_transition_writer": transition_writer,
            "abhe_v0_bfcl_fresh_slice": bfcl_fresh_slice,
            "abhe_v0_bfcl_fresh_slice_review": bfcl_fresh_slice_review,
            "abhe_v0_candidate_materialization": bfcl_candidate_materialization,
            "abhe_v0_materialized_candidates": bfcl_materialized_candidates,
            "abhe_v0_runtime_candidate_adapter": bfcl_runtime_candidate_adapter,
            "abhe_v0_bfcl_dev_smoke_request": bfcl_dev_smoke_request,
            "abhe_v0_bfcl_execution_readiness": bfcl_execution_readiness,
            "abhe_v0_bfcl_dry_run_manifest": bfcl_dry_run_manifest,
            "abhe_v0_bfcl_dev_smoke_result": bfcl_dev_smoke_result,
            "abhe_v0_bfcl_dev_feedback": bfcl_dev_feedback,
            "abhe_v0_bfcl_case_delta_analysis": bfcl_case_delta,
            "abhe_v0_bfcl_dev_feedback_schema": bfcl_dev_feedback_schema,
            "abhe_v0_bfcl_same_slice_rerun_stability": bfcl_same_slice_stability,
            "abhe_v0_expanded_dev_smoke_request": bfcl_expanded_dev_smoke_request,
            "abhe_v0_bfcl_archive_transition": bfcl_archive_transition,
            "abhe_v0_runtime_slot_observability_plan": runtime_slot_observability_plan,
            "abhe_v0_runtime_slot_observability_fixture": runtime_slot_observability_fixture,
            "abhe_v0_runtime_slot_observability_review": runtime_slot_observability_review,
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
