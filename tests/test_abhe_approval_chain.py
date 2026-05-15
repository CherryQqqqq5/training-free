from __future__ import annotations

from scripts.check_abhe_approval_chain import EXPECTED_MISSING_APPROVAL_BLOCKERS, build_report as build_approval_chain
from scripts.check_abhe_candidate_spec_approval_packet import validate_packet as validate_candidate_spec_approval
from scripts.check_abhe_execution_approval_packet import validate_packet as validate_execution_approval
from scripts.check_abhe_execution_readiness import build_report as build_execution_readiness
from scripts.check_abhe_fresh_dev_slice_approval_packet import validate_packet as validate_fresh_slice_approval
from scripts.check_abhe_planning_ready import build_report as build_planning_ready
from scripts.check_abhe_review_bundle import build_bundle, validate_bundle
from scripts.check_abhe_trace_extraction_approval_packet import validate_packet as validate_trace_approval


def trace_approval_packet() -> dict:
    return {
        "approval_status": "approved",
        "authorized": True,
        "review_owner": "reviewer",
        "approved_output_path": "outputs/artifacts/stage1_bfcl_acceptance/approved_trace_cards.json",
        "approved_max_trace_card_count": 10,
        "approved_target_entry_ids": ["state_tracking_v0", "hallucination_abstain_v0"],
        "approval_scope": "trace_cards_only",
        "provider_calls_authorized": False,
        "bfcl_generate_authorized": False,
        "bfcl_evaluate_authorized": False,
        "scorer_authorized": False,
        "candidate_generation_authorized": False,
        "performance_evidence": False,
    }


def fresh_slice_approval_packet() -> dict:
    return {
        "approval_status": "approved",
        "authorized": True,
        "review_owner": "reviewer",
        "approved_fresh_dev_slice_hash": "sha256:fresh-slice-review-placeholder",
        "approved_case_count": 20,
        "approved_entry_ids": ["state_tracking_v0", "hallucination_abstain_v0"],
        "archive_seed_source_excluded": True,
        "source_160_compact_cases_reused_for_validation": False,
        "approval_scope": "fresh_dev_slice_only",
        "provider_calls_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
    }


def candidate_spec_approval_packet() -> dict:
    return {
        "approval_status": "approved",
        "authorized": True,
        "review_owner": "reviewer",
        "approved_candidate_spec_hashes": {
            "state_tracking_v0": "sha256:state-spec-review-placeholder",
            "hallucination_abstain_v0": "sha256:hallucination-spec-review-placeholder",
        },
        "approved_entry_ids": ["state_tracking_v0", "hallucination_abstain_v0"],
        "approval_scope": "spec_review_only",
        "candidate_rule_generation_authorized": False,
        "candidate_jsonl_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
    }


def execution_approval_packet() -> dict:
    return {
        "approval_status": "approved",
        "authorized": True,
        "review_owner": "reviewer",
        "approved_entry_ids": ["state_tracking_v0", "hallucination_abstain_v0"],
        "approved_fresh_dev_slice_hash": "sha256:fresh-slice-review-placeholder",
        "approved_case_count": 20,
        "approved_provider": "reviewed_provider",
        "approved_model": "reviewed_model",
        "approved_protocol": "reviewed_protocol",
        "approved_runtime_config_path": "configs/reviewed_runtime_config.yaml",
        "approved_runner_manifest_hash": "sha256:runner-manifest-review-placeholder",
        "approved_candidate_spec_hash": "sha256:candidate-spec-review-placeholder",
        "approval_scope": "bounded_dev_smoke_only",
        "holdout_authorized": False,
        "full_suite_authorized": False,
        "performance_claim_authorized": False,
    }


def test_review_bundle_passes() -> None:
    bundle = build_bundle()
    assert validate_bundle(bundle) == []
    assert bundle["abhe_review_bundle_ready"] is True
    assert bundle["execution_authorized"] is False
    assert bundle["performance_evidence"] is False


def test_approval_chain_records_missing_approval_packets() -> None:
    report = build_approval_chain()
    assert report["abhe_approval_chain_ready_for_review"] is True
    assert set(EXPECTED_MISSING_APPROVAL_BLOCKERS).issubset(set(report["blockers"]))
    assert report["trace_extraction_approved"] is False
    assert report["fresh_dev_slice_approved"] is False
    assert report["candidate_spec_approved"] is False
    assert report["execution_approved"] is False
    assert report["performance_evidence"] is False


def test_missing_approvals_do_not_fail_planning_readiness() -> None:
    report = build_planning_ready()
    assert report["abhe_planning_ready"] is True
    assert report["approval_chain_ready_for_review"] is True
    assert report["execution_authorized"] is False
    assert report["performance_evidence"] is False


def test_execution_readiness_stays_false() -> None:
    report = build_execution_readiness()
    assert report["execution_readiness_check_passed"] is True
    assert report["abhe_execution_ready"] is False
    assert "trace_extraction_approval_missing" in report["blockers"]
    assert "fresh_dev_slice_approval_missing" in report["blockers"]
    assert "candidate_spec_approval_missing" in report["blockers"]
    assert "execution_approval_missing" in report["blockers"]


def test_approval_checkers_reject_authorized_false() -> None:
    packet = trace_approval_packet()
    packet["authorized"] = False
    blockers = validate_trace_approval(packet)
    assert any("authorized_not_true" in blocker for blocker in blockers)


def test_approval_checkers_reject_wrong_scope() -> None:
    packet = fresh_slice_approval_packet()
    packet["approval_scope"] = "bounded_dev_smoke_only"
    blockers = validate_fresh_slice_approval(packet)
    assert any("scope_invalid" in blocker for blocker in blockers)


def test_candidate_spec_approval_rejects_rule_generation_authorization() -> None:
    packet = candidate_spec_approval_packet()
    packet["candidate_rule_generation_authorized"] = True
    blockers = validate_candidate_spec_approval(packet)
    assert any("candidate_rule_generation_authorized_not_false" in blocker for blocker in blockers)


def test_approval_checkers_reject_scorer_or_performance_flags() -> None:
    candidate_packet = candidate_spec_approval_packet()
    candidate_packet["scorer_authorized"] = True
    assert any("scorer_authorized_not_false" in blocker for blocker in validate_candidate_spec_approval(candidate_packet))

    fresh_packet = fresh_slice_approval_packet()
    fresh_packet["performance_evidence"] = True
    assert any("performance_evidence_not_false" in blocker for blocker in validate_fresh_slice_approval(fresh_packet))


def test_execution_approval_rejects_performance_claim_authorization() -> None:
    packet = execution_approval_packet()
    packet["performance_claim_authorized"] = True
    blockers = validate_execution_approval(packet)
    assert any("performance_claim_authorized_not_false" in blocker for blocker in blockers)
