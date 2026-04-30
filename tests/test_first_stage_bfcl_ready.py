from __future__ import annotations

import scripts.check_first_stage_bfcl_ready as first_stage


def test_first_stage_ready_fails_closed_without_performance_claim(monkeypatch) -> None:
    monkeypatch.setattr(
        first_stage,
        "evaluate_delivery",
        lambda: {
            "delivery_claim_status": "scaffold_and_diagnostic_package_only",
            "sota_3pp_claim_ready": False,
            "p0_blockers": ["artifact_boundary_not_clean"],
            "artifact_boundary": {"artifact_boundary_passed": False},
        },
    )
    monkeypatch.setattr(
        first_stage,
        "evaluate_m28pre",
        lambda: {
            "m2_8pre_offline_passed": False,
            "manifest_case_integrity_passed": True,
            "scorer_authorization_ready": False,
            "remaining_gap_to_35_demote_candidates": 18,
            "route_recommendation": "expand_argument_repair_pool",
            "blockers": ["combined_demote_candidate_below_35"],
        },
    )
    monkeypatch.setattr(
        first_stage,
        "evaluate_explicit_smoke",
        lambda: {
            "ready": False,
            "execution_allowed": False,
            "next_required_action": "replace_ceiling_or_false_positive_cases_before_smoke",
            "blockers": ["smoke_selection_not_ready_after_baseline_dry_audit"],
        },
    )
    monkeypatch.setattr(
        first_stage,
        "evaluate_performance",
        lambda: {
            "ready_for_formal_bfcl_performance_acceptance": False,
            "next_required_action": "fix_provider_then_generate_same_protocol_baseline_candidate_bfcl_scores",
            "blockers": ["provider_green_preflight_not_passed"],
        },
    )

    report = first_stage.evaluate()

    assert report["ready_for_huawei_acceptance"] is False
    assert report["ready_for_scaffold_handoff"] is True
    assert "sota_3pp_claim_not_ready" in report["blockers"]
    assert "formal_bfcl_performance_evidence_not_ready" in report["blockers"]
    assert "provider_green_preflight_not_passed" in report["blockers"]
    assert "combined_demote_candidate_below_35" in report["blockers"]
    assert "artifact_boundary_not_clean" in report["blockers"]
    assert "smoke_selection_not_ready_after_baseline_dry_audit" in report["secondary_blockers"]
    assert report["next_required_action"] == "clean_or_move_forbidden_artifacts_outside_outputs"


def test_first_stage_ready_passes_only_when_all_acceptance_gates_pass(monkeypatch) -> None:
    monkeypatch.setattr(
        first_stage,
        "evaluate_delivery",
        lambda: {
            "delivery_claim_status": "bfcl_first_stage_performance_ready",
            "sota_3pp_claim_ready": True,
            "p0_blockers": [],
            "artifact_boundary": {"artifact_boundary_passed": True},
        },
    )
    monkeypatch.setattr(
        first_stage,
        "evaluate_m28pre",
        lambda: {
            "m2_8pre_offline_passed": True,
            "manifest_case_integrity_passed": True,
            "scorer_authorization_ready": True,
            "remaining_gap_to_35_demote_candidates": 0,
            "route_recommendation": "run_controlled_dev_holdout",
            "blockers": [],
        },
    )
    monkeypatch.setattr(
        first_stage,
        "evaluate_explicit_smoke",
        lambda: {
            "ready": True,
            "execution_allowed": False,
            "next_required_action": "request_explicit_smoke_execution_approval",
            "blockers": [],
        },
    )
    monkeypatch.setattr(
        first_stage,
        "evaluate_performance",
        lambda: {
            "ready_for_formal_bfcl_performance_acceptance": True,
            "next_required_action": "handoff_formal_bfcl_performance_delivery",
            "blockers": [],
        },
    )

    report = first_stage.evaluate()

    assert report["ready_for_huawei_acceptance"] is True
    assert report["blockers"] == []
    assert report["next_required_action"] == "handoff_first_stage_bfcl_performance_delivery"


def test_first_stage_ready_does_not_require_memory_heavy_explicit_smoke(monkeypatch) -> None:
    monkeypatch.setattr(
        first_stage,
        "evaluate_delivery",
        lambda: {
            "delivery_claim_status": "bfcl_first_stage_performance_ready",
            "sota_3pp_claim_ready": True,
            "p0_blockers": [],
            "artifact_boundary": {"artifact_boundary_passed": True},
        },
    )
    monkeypatch.setattr(
        first_stage,
        "evaluate_m28pre",
        lambda: {
            "m2_8pre_offline_passed": True,
            "manifest_case_integrity_passed": True,
            "scorer_authorization_ready": True,
            "remaining_gap_to_35_demote_candidates": 0,
            "route_recommendation": "run_controlled_dev_holdout",
            "blockers": [],
        },
    )
    monkeypatch.setattr(
        first_stage,
        "evaluate_explicit_smoke",
        lambda: {
            "ready": False,
            "execution_allowed": False,
            "next_required_action": "replace_ceiling_or_false_positive_cases_before_smoke",
            "blockers": ["smoke_selection_not_ready_after_baseline_dry_audit"],
        },
    )
    monkeypatch.setattr(
        first_stage,
        "evaluate_performance",
        lambda: {
            "ready_for_formal_bfcl_performance_acceptance": True,
            "next_required_action": "handoff_formal_bfcl_performance_delivery",
            "blockers": [],
        },
    )

    report = first_stage.evaluate()

    assert report["ready_for_huawei_acceptance"] is True
    assert report["blockers"] == []
    assert "explicit_obligation_smoke_not_ready" in report["secondary_blockers"]
