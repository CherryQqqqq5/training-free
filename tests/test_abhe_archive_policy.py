from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

from scripts.check_abhe_archive_policy import DEFAULT_ARCHIVE, DEFAULT_OPPORTUNITY, validate_archive
from scripts.check_abhe_dev_smoke_packet import validate_packet
from scripts.plan_abhe_next_evolution import build_plan


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_abhe_archive_policy_checker_passes_current_artifacts() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_abhe_archive_policy.py", "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["abhe_archive_policy_passed"] is True
    assert summary["entry_count"] == 3
    assert summary["proposal_ready_entry_count"] == 2
    assert summary["watch_entry_count"] == 1
    assert summary["performance_evidence"] is False
    assert summary["scorer_authorized"] is False
    assert summary["candidate_pool_ready"] is False


def test_abhe_archive_rejects_legacy_or_category_bound_entry_id() -> None:
    archive = load(DEFAULT_ARCHIVE)
    opportunity = load(DEFAULT_OPPORTUNITY)
    archive["entries"][0]["entry_id"] = "bfcl_multi_turn_state_tracking_v0"
    opportunity["entries"][0]["entry_id"] = "bfcl_multi_turn_state_tracking_v0"
    blockers = validate_archive(archive, opportunity)
    assert any("category_bound_or_legacy_name" in blocker for blocker in blockers)


def test_abhe_planner_outputs_request_only_actions() -> None:
    archive = load(DEFAULT_ARCHIVE)
    opportunity = load(DEFAULT_OPPORTUNITY)
    plan = build_plan(archive, opportunity, [])
    assert plan["blockers"] == []
    assert plan["does_not_call_provider"] is True
    assert plan["does_not_call_bfcl_or_model"] is True
    assert plan["does_not_authorize_scorer"] is True
    assert plan["does_not_generate_candidate"] is True
    assert plan["does_not_claim_performance"] is True
    assert [row["entry_id"] for row in plan["selected_actions"]] == [
        "state_tracking_v0",
        "hallucination_abstain_v0",
    ]
    assert [row["entry_id"] for row in plan["watch_actions"]] == ["unresolved_search_memory_watch_v0"]
    assert plan["performance_evidence"] is False
    assert plan["scorer_authorized"] is False


def test_abhe_planner_fails_closed_when_dev_feedback_exists() -> None:
    archive = load(DEFAULT_ARCHIVE)
    opportunity = load(DEFAULT_OPPORTUNITY)
    plan = build_plan(archive, opportunity, [{"entry_id": "state_tracking_v0"}])
    assert "dev_feedback_present_post_dev_planner_not_implemented" in plan["blockers"]


def test_abhe_dev_smoke_packet_checker_accepts_pending_draft_contract() -> None:
    packet = {
        "artifact_kind": "abhe_bounded_dev_smoke_execution_packet",
        "schema_version": "abhe_dev_smoke_packet_v0",
        "approval_status": "pending",
        "authorized": False,
        "execution_started": False,
        "entry_ids": ["state_tracking_v0"],
        "baseline_command_template": "PYTHONPATH=.:src .venv/bin/python scripts/run_abhe_dev_smoke.py --arm baseline --compact-only",
        "candidate_command_template": "PYTHONPATH=.:src .venv/bin/python scripts/run_abhe_dev_smoke.py --arm candidate --compact-only",
        "case_list_hash": "sha256:placeholder_fresh_dev_slice_hash",
        "fresh_dev_slice_source": "future_approved_fresh_dev_slice",
        "provider": "novacode",
        "model": "gpt-5.2",
        "protocol": "bfcl_v4_paired_dev_smoke",
        "runtime_config_path": "configs/runtime_bfcl_skills.yaml",
        "candidate_rule_path": "future_approved_candidate_rule_path",
        "artifact_boundary": {
            "compact_only": True,
            "raw_outputs_committed": False,
            "forbidden_fields_absent_required": True,
        },
        "cost_latency_cap": {"max_cost_usd": 0.0, "max_latency_delta_pct": 0},
        "regression_cap": {"max_regressed_count": 0},
        "stop_loss_criteria": [
            "raw_leakage",
            "case_count_exceeds_cap",
            "provider_model_protocol_mismatch",
            "fresh_dev_slice_missing_or_reused",
            "candidate_jsonl_or_pool_created",
            "holdout_or_full_suite_touched",
            "cost_or_latency_cap_exceeded",
            "regression_cap_exceeded",
            "checker_failure",
        ],
        "provider_calls_authorized": False,
        "bfcl_generate_authorized": False,
        "bfcl_evaluate_authorized": False,
        "candidate_generation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
    }
    assert validate_packet(packet) == []
    mutated = copy.deepcopy(packet)
    mutated["authorized"] = True
    assert any("authorized_not_false" in blocker for blocker in validate_packet(mutated))
