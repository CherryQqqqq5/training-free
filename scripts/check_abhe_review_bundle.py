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
from scripts.check_abhe_v0_bfcl_case_delta_analysis import check as check_bfcl_case_delta
from scripts.check_abhe_v0_bfcl_dev_smoke_approval_request import check as check_bfcl_dev_smoke_request
from scripts.check_abhe_v0_bfcl_dev_smoke_approval_packet import check as check_bfcl_dev_smoke_approval_packet
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
from scripts.plan_abhe_v0_bfcl_archive_transition import build_plan as build_bfcl_archive_transition
from scripts.plan_abhe_v0_bfcl_archive_transition import synthetic_feedback as bfcl_synthetic_feedback

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_review_bundle.json")
PLANNING_READY_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_planning_ready.json")
BFCL_DATASET_SELECTION_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dataset_path_selection.json")
BFCL_FRESH_SLICE_REVIEW_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_review.json")
BFCL_SOURCE_EXCLUSION_PROOF_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_source_exclusion_proof.json")
BFCL_FRESH_SLICE_MANIFEST_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_manifest.json")
BFCL_FAILURE_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_execution_failure.json")
BFCL_RUNTIME_ADAPTER_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_candidate_adapter.json")
BFCL_PROVIDER_PREFLIGHT_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_provider_preflight.json")
BFCL_NEXT_TRACE_AUDIT_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_next_trace_audit.json")
RUNTIME_SLOT_RESIDUAL_RESULT_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_residual_dev_smoke_result.json")
RUNTIME_SLOT_RESIDUAL_FAILURE_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_residual_failure_analysis.json")
RUNTIME_SLOT_RESIDUAL_AUDIT_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_sanitized_trace_audit.json")
RUNTIME_SLOT_CAUSALITY_AUDIT_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_causality_audit.json")
RUNTIME_SLOT_PATH_REPLAY_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_path_replay.json")
RUNTIME_SLOT_BINDABILITY_AUDIT_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_bindability_audit_v1.json")
RUNTIME_SLOT_OBSERVABILITY_PLAN_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_observability_plan.json")
RUNTIME_SLOT_OBSERVABILITY_FIXTURE_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_observability_fixture.json")
RUNTIME_SLOT_RESIDUAL_TRANSITION_PATH = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_archive_transition_dry_run.json")
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


def _summary(report: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    summary = {key: report.get(key) for key in keys if key in report}
    if "blockers" in report:
        summary["blockers"] = report.get("blockers", [])
    return summary


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
    bfcl_materialized_candidates = check_bfcl_materialized_candidates()
    bfcl_runtime_candidate_adapter = check_bfcl_runtime_candidate_adapter()
    bfcl_provider_preflight = _load_json(BFCL_PROVIDER_PREFLIGHT_PATH)
    bfcl_dev_smoke_request = check_bfcl_dev_smoke_request()
    bfcl_dev_smoke_approval = check_bfcl_dev_smoke_approval_packet()
    bfcl_execution_readiness = build_bfcl_execution_readiness()
    bfcl_dry_run_manifest = check_bfcl_dev_smoke_result(dry_run_manifest=True)
    bfcl_dev_smoke_result = check_bfcl_dev_smoke_result()
    bfcl_dev_feedback_schema = check_bfcl_dev_feedback(schema_only=True)
    bfcl_dev_feedback = check_bfcl_dev_feedback()
    bfcl_case_delta = check_bfcl_case_delta()
    bfcl_same_slice_stability = check_bfcl_same_slice_stability()
    bfcl_expanded_dev_smoke_request = check_bfcl_expanded_dev_smoke_request()
    bfcl_archive_transition = build_bfcl_archive_transition(bfcl_synthetic_feedback(), synthetic_fixture_only=True)
    bfcl_dataset_selection = _load_json(BFCL_DATASET_SELECTION_PATH)
    bfcl_fresh_slice_review_artifact = _load_json(BFCL_FRESH_SLICE_REVIEW_PATH)
    bfcl_source_exclusion_proof = _load_json(BFCL_SOURCE_EXCLUSION_PROOF_PATH)
    bfcl_fresh_slice_manifest = _load_json(BFCL_FRESH_SLICE_MANIFEST_PATH)
    bfcl_execution_failure = _load_json(BFCL_FAILURE_PATH)
    bfcl_next_trace_audit = _load_json(BFCL_NEXT_TRACE_AUDIT_PATH)
    runtime_slot_residual_result = _load_json(RUNTIME_SLOT_RESIDUAL_RESULT_PATH)
    runtime_slot_residual_failure = _load_json(RUNTIME_SLOT_RESIDUAL_FAILURE_PATH)
    runtime_slot_residual_audit = _load_json(RUNTIME_SLOT_RESIDUAL_AUDIT_PATH)
    runtime_slot_causality_audit = _load_json(RUNTIME_SLOT_CAUSALITY_AUDIT_PATH)
    runtime_slot_path_replay = _load_json(RUNTIME_SLOT_PATH_REPLAY_PATH)
    runtime_slot_bindability_audit = _load_json(RUNTIME_SLOT_BINDABILITY_AUDIT_PATH)
    runtime_slot_observability_plan = check_runtime_slot_observability_plan()
    runtime_slot_observability_fixture = check_runtime_slot_observability_fixture()
    runtime_slot_residual_transition = _load_json(RUNTIME_SLOT_RESIDUAL_TRANSITION_PATH)
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
        "abhe_v0_bfcl_selected_dataset_path": bfcl_dataset_selection.get("selected_dataset_path"),
        "abhe_v0_bfcl_proposed_selected_case_ids_hash": bfcl_fresh_slice_review_artifact.get("proposed_selected_case_ids_hash"),
        "abhe_v0_bfcl_source_exclusion_status": bfcl_source_exclusion_proof.get("overlap_check_status"),
        "abhe_v0_bfcl_overlap_count": bfcl_source_exclusion_proof.get("overlap_count"),
        "abhe_v0_bfcl_candidate_case_hash_count": bfcl_source_exclusion_proof.get("candidate_case_hash_count"),
        "abhe_v0_bfcl_fresh_slice_materialized": bfcl_fresh_slice_manifest.get("fresh_dev_slice_materialized") is True,
        "abhe_v0_bfcl_selected_case_ids_hash": bfcl_fresh_slice_manifest.get("selected_case_ids_hash"),
        "abhe_v0_candidate_materialization_plan_ready": bfcl_candidate_materialization.get("abhe_v0_candidate_materialization_plan_check_passed") is True,
        "abhe_v0_candidate_materialization_approved": bfcl_materialized_candidates.get("candidate_materialization_approved") is True,
        "abhe_v0_materialized_candidates_ready": bfcl_materialized_candidates.get("abhe_v0_materialized_candidates_check_passed") is True,
        "abhe_v0_runtime_candidate_adapter_ready": bfcl_runtime_candidate_adapter.get("adapter_ready") is True,
        "abhe_v0_provider_preflight_passed": bfcl_provider_preflight.get("provider_preflight_passed") is True,
        "abhe_v0_bfcl_dev_smoke_request_ready": bfcl_dev_smoke_request.get("abhe_v0_bfcl_dev_smoke_approval_request_passed") is True,
        "abhe_v0_bfcl_dev_smoke_approval_packet_ready": bfcl_dev_smoke_approval.get("approval_packet_passed") is True,
        "abhe_v0_bfcl_execution_failure_present": not bool(bfcl_execution_failure.get("artifact_missing")),
        "abhe_v0_bfcl_execution_ready": bfcl_execution_readiness.get("abhe_v0_bfcl_execution_ready") is True,
        "abhe_v0_bfcl_dry_run_manifest_ready": bfcl_dry_run_manifest.get("abhe_v0_bfcl_dev_smoke_result_check_passed") is True,
        "abhe_v0_bfcl_dev_smoke_result_ready": bfcl_dev_smoke_result.get("abhe_v0_bfcl_dev_smoke_result_check_passed") is True,
        "abhe_v0_bfcl_dev_feedback_ready": bfcl_dev_feedback.get("abhe_v0_bfcl_dev_feedback_check_passed") is True,
        "abhe_v0_bfcl_dev_feedback_schema_ready": bfcl_dev_feedback_schema.get("abhe_v0_bfcl_dev_feedback_check_passed") is True,
        "abhe_v0_bfcl_archive_transition_ready": bfcl_archive_transition.get("abhe_v0_bfcl_archive_transition_plan_passed") is True,
        "abhe_v0_bfcl_case_delta_analysis_ready": bfcl_case_delta.get("abhe_v0_bfcl_case_delta_analysis_check_passed") is True,
        "abhe_v0_bfcl_same_slice_rerun_stability_ready": bfcl_same_slice_stability.get("same_slice_rerun_stability_check_passed") is True,
        "abhe_v0_expanded_dev_smoke_request_ready": bfcl_expanded_dev_smoke_request.get("abhe_v0_expanded_dev_smoke_request_passed") is True,
        "abhe_v0_next_trace_audit_ready": bfcl_next_trace_audit.get("artifact_kind") == "abhe_v0_next_trace_audit",
        "abhe_v0_runtime_slot_residual_result_ready": runtime_slot_residual_result.get("artifact_kind") == "abhe_v0_runtime_slot_controller_residual_dev_smoke_result",
        "abhe_v0_runtime_slot_residual_failure_analysis_ready": runtime_slot_residual_failure.get("artifact_kind") == "abhe_v0_runtime_slot_controller_residual_failure_analysis",
        "abhe_v0_runtime_slot_residual_trace_audit_ready": runtime_slot_residual_audit.get("artifact_kind") == "abhe_v0_runtime_slot_controller_sanitized_trace_audit",
        "abhe_v0_runtime_slot_residual_archive_updated": runtime_slot_residual_transition.get("archive_updated") is True,
        "abhe_v0_runtime_slot_causality_audit_ready": runtime_slot_causality_audit.get("artifact_kind") == "abhe_v0_runtime_slot_controller_causality_audit",
        "abhe_v0_runtime_slot_binder_causality_confirmed": runtime_slot_causality_audit.get("binder_causality_confirmed") is True,
        "abhe_v0_runtime_slot_causality_assessment": runtime_slot_causality_audit.get("overall_assessment"),
        "abhe_v0_runtime_slot_path_replay_ready": runtime_slot_path_replay.get("artifact_kind") == "abhe_v0_runtime_slot_controller_path_replay",
        "abhe_v0_runtime_slot_proxy_fixture_confirmed": (runtime_slot_path_replay.get("summary") or {}).get("proxy_fixture_runtime_path_confirmed") is True,
        "abhe_v0_runtime_slot_same_request_noop_confirmed": (runtime_slot_path_replay.get("summary") or {}).get("same_request_noop_replay_confirmed") is True,
        "abhe_v0_runtime_slot_residual_performance_evidence": runtime_slot_residual_failure.get("performance_evidence") is True,
        "abhe_v0_runtime_slot_residual_target_delta": (runtime_slot_residual_failure.get("summary") or {}).get("multi_turn_miss_param_delta_vs_conditional_frozen_v2"),
        "abhe_v0_runtime_slot_residual_bind_repair_count": (runtime_slot_residual_failure.get("summary") or {}).get("slot_bind_repair_count"),
        "abhe_v0_runtime_slot_residual_next_required_action": "implement_pre_generation_post_decode_observability_no_provider_fixture_before_bfcl_rerun",
        "abhe_v0_runtime_slot_observability_plan_ready": runtime_slot_observability_plan.get("observability_plan_check_passed") is True,
        "abhe_v0_runtime_slot_observability_fixture_ready": runtime_slot_observability_fixture.get("observability_fixture_check_passed") is True,
        "abhe_v0_runtime_slot_observability_fixture_bind_repair_rows": runtime_slot_observability_fixture.get("bind_repair_rows"),
        "abhe_v0_runtime_slot_observability_plan_next_required_action": runtime_slot_observability_plan.get("next_required_action"),
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
            "abhe_v0_bfcl_fresh_dev_slice_manifest": str(BFCL_FRESH_SLICE_MANIFEST_PATH),
            "abhe_v0_bfcl_dataset_path_review": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dataset_path_review.json",
            "abhe_v0_bfcl_dataset_path_selection": str(BFCL_DATASET_SELECTION_PATH),
            "abhe_v0_bfcl_category_review": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_category_review.json",
            "abhe_v0_bfcl_fresh_dev_slice_review": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_review.json",
            "abhe_v0_bfcl_source_exclusion_proof": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_source_exclusion_proof.json",
            "abhe_v0_candidate_materialization_plan": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_materialization_plan.json",
            "abhe_v0_candidate_materialization_approval_packet": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_materialization_approval_packet.json",
            "abhe_v0_materialized_candidates": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_materialized_candidates.json",
            "abhe_v0_bfcl_dev_smoke_approval_request": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_request.json",
            "abhe_v0_bfcl_dev_smoke_approval_packet": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_packet.json",
            "abhe_v0_bfcl_dev_smoke_execution_failure": str(BFCL_FAILURE_PATH),
            "abhe_v0_runtime_candidate_adapter": str(BFCL_RUNTIME_ADAPTER_PATH),
            "abhe_v0_provider_preflight": str(BFCL_PROVIDER_PREFLIGHT_PATH),
            "abhe_v0_bfcl_execution_readiness": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_execution_readiness.json",
            "abhe_v0_bfcl_dev_smoke_result": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_result.json",
            "abhe_v0_bfcl_dev_feedback": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_feedback.json",
            "abhe_v0_bfcl_case_delta_analysis": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_case_delta_analysis.json",
            "abhe_v0_bfcl_dev_feedback_schema": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_feedback.schema.json",
            "abhe_v0_bfcl_archive_transition_plan": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_archive_transition_plan.json",
            "abhe_v0_bfcl_same_slice_rerun_stability": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_same_slice_rerun_stability.json",
            "abhe_v0_expanded_dev_smoke_request": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_expanded_dev_smoke_request.json",
            "abhe_v0_next_trace_audit": str(BFCL_NEXT_TRACE_AUDIT_PATH),
            "abhe_v0_runtime_slot_controller_residual_dev_smoke_result": str(RUNTIME_SLOT_RESIDUAL_RESULT_PATH),
            "abhe_v0_runtime_slot_controller_residual_failure_analysis": str(RUNTIME_SLOT_RESIDUAL_FAILURE_PATH),
            "abhe_v0_runtime_slot_controller_sanitized_trace_audit": str(RUNTIME_SLOT_RESIDUAL_AUDIT_PATH),
            "abhe_v0_runtime_slot_controller_causality_audit": str(RUNTIME_SLOT_CAUSALITY_AUDIT_PATH),
            "abhe_v0_runtime_slot_controller_path_replay": str(RUNTIME_SLOT_PATH_REPLAY_PATH),
            "abhe_v0_runtime_slot_observability_plan": str(RUNTIME_SLOT_OBSERVABILITY_PLAN_PATH),
            "abhe_v0_runtime_slot_observability_fixture": str(RUNTIME_SLOT_OBSERVABILITY_FIXTURE_PATH),
            "abhe_v0_runtime_slot_controller_archive_transition_dry_run": str(RUNTIME_SLOT_RESIDUAL_TRANSITION_PATH),
        },
        "component_summaries": {
            "planning_ready": _summary(planning_ready, [
                "abhe_planning_ready",
                "abhe_v0_bfcl_case_delta_analysis_ready",
                "abhe_v0_bfcl_dev_smoke_result_ready",
                "abhe_v0_bfcl_dev_feedback_ready",
                "no_leakage_boundary_passed",
            ]),
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
            "abhe_v0_materialized_candidates": bfcl_materialized_candidates,
            "abhe_v0_runtime_candidate_adapter": bfcl_runtime_candidate_adapter,
            "abhe_v0_provider_preflight": bfcl_provider_preflight,
            "abhe_v0_bfcl_dev_smoke_request": bfcl_dev_smoke_request,
            "abhe_v0_bfcl_dev_smoke_approval_packet": bfcl_dev_smoke_approval,
            "abhe_v0_bfcl_dev_smoke_execution_failure": bfcl_execution_failure,
            "abhe_v0_bfcl_execution_readiness": bfcl_execution_readiness,
            "abhe_v0_bfcl_dry_run_manifest": bfcl_dry_run_manifest,
            "abhe_v0_bfcl_dev_smoke_result": bfcl_dev_smoke_result,
            "abhe_v0_bfcl_dev_feedback": bfcl_dev_feedback,
            "abhe_v0_bfcl_case_delta_analysis": _summary(bfcl_case_delta, [
                "abhe_v0_bfcl_case_delta_analysis_check_passed",
                "analysis_present",
                "unique_bfcl_scorer_unit_count",
                "strict_per_compact_case_paired_available",
                "entry_specific_guidance_detected",
                "global_guidance_detected",
                "strict_scorer_unit_fixed_count",
                "scaled_compact_fixed_count",
                "performance_evidence",
            ]),
            "abhe_v0_bfcl_dev_feedback_schema": bfcl_dev_feedback_schema,
            "abhe_v0_bfcl_same_slice_rerun_stability": bfcl_same_slice_stability,
            "abhe_v0_expanded_dev_smoke_request": bfcl_expanded_dev_smoke_request,
            "abhe_v0_next_trace_audit": _summary(bfcl_next_trace_audit, [
                "artifact_kind",
                "bounded_dev_smoke_only",
                "trace_content_committed",
                "prompt_literal_committed",
                "performance_evidence",
                "holdout_touched",
                "full_suite_touched",
            ]),
            "abhe_v0_runtime_slot_residual_result": runtime_slot_residual_result,
            "abhe_v0_runtime_slot_residual_failure_analysis": runtime_slot_residual_failure,
            "abhe_v0_runtime_slot_residual_trace_audit": _summary(runtime_slot_residual_audit, [
                "artifact_kind",
                "safe_fields_only",
                "raw_material_absent",
                "performance_evidence",
                "holdout_touched",
                "full_suite_touched",
            ]),
            "abhe_v0_runtime_slot_causality_audit": _summary(runtime_slot_causality_audit, [
                "artifact_kind",
                "binder_causality_confirmed",
                "overall_assessment",
                "next_required_action",
                "performance_evidence",
                "holdout_touched",
                "full_suite_touched",
            ]),
            "abhe_v0_runtime_slot_path_replay": _summary(runtime_slot_path_replay, [
                "artifact_kind",
                "no_provider",
                "performance_evidence",
                "holdout_touched",
                "full_suite_touched",
            ]),
            "abhe_v0_runtime_slot_observability_plan": runtime_slot_observability_plan,
            "abhe_v0_runtime_slot_observability_fixture": runtime_slot_observability_fixture,
            "abhe_v0_runtime_slot_residual_archive_transition": runtime_slot_residual_transition,
            "abhe_v0_bfcl_archive_transition": bfcl_archive_transition,
            "no_leakage": _summary(leakage, ["abhe_no_leakage_boundary_passed", "report_scope"]),
        },
        "commit": _current_commit(),
        "next_required_action": "review_observability_fixture_before_any_bfcl_rerun",
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
        "abhe_v0_materialized_candidates_ready",
        "abhe_v0_bfcl_dev_smoke_request_ready",
        "abhe_v0_bfcl_dev_smoke_approval_packet_ready",
        "abhe_v0_bfcl_dry_run_manifest_ready",
        "abhe_v0_bfcl_dev_feedback_schema_ready",
        "abhe_v0_bfcl_same_slice_rerun_stability_ready",
        "abhe_v0_expanded_dev_smoke_request_ready",
        "abhe_v0_bfcl_archive_transition_ready",
        "abhe_v0_runtime_slot_observability_plan_ready",
        "abhe_v0_runtime_slot_observability_fixture_ready",
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
