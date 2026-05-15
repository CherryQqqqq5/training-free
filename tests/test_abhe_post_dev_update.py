from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from scripts.append_abhe_state_transition import validate as validate_transition
from scripts.plan_abhe_post_dev_update import build_plan, decide_transition

FIXTURE_ROOT = Path("tests/fixtures/abhe_dev_feedback")


def transition_by_fixture() -> dict[str, str]:
    plan = build_plan(FIXTURE_ROOT, synthetic_fixture_only=True)
    assert plan["abhe_post_dev_update_plan_passed"] is True
    return {
        Path(row["fixture_path"]).name: row["to_status"]
        for row in plan["planned_transitions"]
    }


def test_post_dev_synthetic_planner_requires_synthetic_flag() -> None:
    plan = build_plan(FIXTURE_ROOT, synthetic_fixture_only=False)
    assert plan["post_dev_transition_planner_enabled"] is False
    assert "synthetic_fixture_only_required" in plan["blockers"]


def test_post_dev_synthetic_fixture_transitions() -> None:
    transitions = transition_by_fixture()
    assert transitions["dev_passed.json"] == "dev_passed"
    assert transitions["narrow_router_requested.json"] == "narrow_router_requested"
    assert transitions["split_requested.json"] == "split_requested"
    assert transitions["demoted_no_mechanism_signal.json"] == "demoted_no_mechanism_signal"
    assert transitions["demoted_regression_not_controlled.json"] == "demoted_regression_not_controlled"
    assert transitions["rejected_boundary_failure.json"] == "rejected_boundary_failure"


def test_post_dev_decision_prioritizes_boundary_failure() -> None:
    row = {
        "leakage_count": 1,
        "boundary_violation_count": 0,
        "target_bucket_reduction": 5,
        "fixed_count": 5,
        "regressed_count": 1,
        "non_target_regression_count": 0,
        "cost_delta_pct": 0,
        "latency_delta_pct": 0,
    }
    assert decide_transition(row) == "rejected_boundary_failure"


def test_state_transition_writer_dry_run_success() -> None:
    args = Namespace(
        entry_id="state_tracking_v0",
        from_status="proposal_ready",
        to_status="dev_smoke_requested",
        reason="synthetic_dry_run",
        dry_run=True,
        write=False,
    )
    assert validate_transition(args) == []


def test_state_transition_writer_rejects_non_dry_run_without_approval() -> None:
    args = Namespace(
        entry_id="state_tracking_v0",
        from_status="proposal_ready",
        to_status="dev_smoke_requested",
        reason="synthetic_dry_run",
        dry_run=False,
        write=False,
    )
    blockers = validate_transition(args)
    assert "non_dry_run_requires_future_explicit_approval_artifact" in blockers


def test_state_transition_writer_rejects_direct_dev_passed() -> None:
    args = Namespace(
        entry_id="state_tracking_v0",
        from_status="proposal_ready",
        to_status="dev_passed",
        reason="invalid_direct_transition",
        dry_run=True,
        write=False,
    )
    blockers = validate_transition(args)
    assert "direct_proposal_ready_to_dev_passed_forbidden" in blockers
