from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

from scripts.check_abhe_archive_policy import DEFAULT_ARCHIVE, DEFAULT_OPPORTUNITY, validate_archive
from scripts.check_abhe_candidate_spec_drafts import check as check_candidate_specs
from scripts.check_abhe_dev_feedback import validate_feedback, validate_schema
from scripts.check_abhe_dev_smoke_dry_run_manifest import validate_manifest
from scripts.check_abhe_dev_smoke_packet import validate_packet
from scripts.check_abhe_execution_approval_packet import check as check_execution_approval_packet
from scripts.check_abhe_execution_readiness import build_report as build_execution_readiness_report
from scripts.check_abhe_fresh_dev_slice_request import validate_request as validate_fresh_slice_request
from scripts.check_abhe_no_leakage_boundary import check_paths, scan_value
from scripts.check_abhe_planning_ready import build_report
from scripts.check_abhe_review_request import validate_request as validate_review_request
from scripts.check_abhe_trace_cards import validate_card, validate_schema as validate_trace_card_schema
from scripts.check_abhe_trace_extraction_packet import validate_packet as validate_trace_packet
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


def test_abhe_planner_records_actual_input_paths() -> None:
    archive = load(DEFAULT_ARCHIVE)
    opportunity = load(DEFAULT_OPPORTUNITY)
    plan = build_plan(
        archive,
        opportunity,
        [],
        Path("tmp/custom_archive.json"),
        Path("tmp/custom_opportunity.json"),
    )
    assert plan["source_archive"] == "tmp/custom_archive.json"
    assert plan["source_opportunity_table"] == "tmp/custom_opportunity.json"


def test_abhe_planner_fails_closed_when_dev_feedback_exists() -> None:
    archive = load(DEFAULT_ARCHIVE)
    opportunity = load(DEFAULT_OPPORTUNITY)
    plan = build_plan(archive, opportunity, [{"entry_id": "state_tracking_v0"}])
    assert "dev_feedback_present_post_dev_planner_not_implemented" in plan["blockers"]
    assert plan["next_required_action"] == "run_check_abhe_dev_feedback_and_enable_post_dev_planner"


def test_abhe_dev_smoke_packet_checker_accepts_pending_draft_contract() -> None:
    packet = {
        "artifact_kind": "abhe_bounded_dev_smoke_execution_packet",
        "schema_version": "abhe_dev_smoke_packet_v0",
        "approval_status": "pending",
        "authorized": False,
        "execution_started": False,
        "entry_ids": ["state_tracking_v0", "hallucination_abstain_v0"],
        "baseline_command_template": "PYTHONPATH=.:src .venv/bin/python scripts/run_abhe_dev_smoke.py --arm baseline --compact-only",
        "candidate_command_template": "PYTHONPATH=.:src .venv/bin/python scripts/run_abhe_dev_smoke.py --arm candidate --compact-only",
        "case_list_hash": "sha256:placeholder_fresh_dev_slice_hash",
        "fresh_dev_slice_source": "future_approved_fresh_dev_slice",
        "provider": "novacode",
        "model": "gpt-5.2",
        "protocol": "bfcl_v4_paired_dev_smoke",
        "runtime_config_path": "configs/runtime_bfcl_skills.yaml",
        "candidate_rule_path": "future_approved_candidate_rule_path",
        "runner_materialized": True,
        "runner_status": "dry_run_only_runner_materialized",
        "fresh_slice_materialized": False,
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
    mutated = copy.deepcopy(packet)
    mutated["entry_ids"] = ["state_tracking_v0", "hallucination_abstain_v0", "unresolved_search_memory_watch_v0"]
    assert any("watch_entries_must_not_enter_dev_smoke" in blocker for blocker in validate_packet(mutated))


def test_abhe_trace_packet_checker_accepts_sanitized_draft_only_contract() -> None:
    packet = {
        "artifact_kind": "abhe_temporary_trace_extraction_packet",
        "schema_version": "abhe_trace_extraction_packet_v0",
        "approval_status": "pending",
        "authorized": False,
        "execution_started": False,
        "target_entry_ids": ["state_tracking_v0", "hallucination_abstain_v0"],
        "allowed_output": "sanitized_trace_cards_only",
        "requested_output_path": "outputs/artifacts/stage1_bfcl_acceptance/abhe_trace_cards.json",
        "max_trace_card_count": {"state_tracking_v0": 6, "hallucination_abstain_v0": 4},
        "source_artifact_boundary": "historical_compact_or_approved_source_only_no_raw_material",
        "raw_material_absent_required": True,
        "raw_prompt_allowed": False,
        "raw_trace_allowed": False,
        "raw_payload_allowed": False,
        "raw_case_id_allowed": False,
        "gold_expected_allowed": False,
        "scorer_diff_allowed": False,
        "candidate_output_allowed": False,
        "performance_evidence": False,
        "explanatory_evidence_only": True,
        "trace_cards_do_not_update_archive_status": True,
    }
    assert validate_trace_packet(packet) == []
    mutated = copy.deepcopy(packet)
    mutated["raw_case_id_allowed"] = True
    assert any("raw_case_id_allowed_not_false" in blocker for blocker in validate_trace_packet(mutated))


def test_abhe_trace_card_schema_and_card_contract() -> None:
    schema = load(Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_trace_card.schema.json"))
    assert validate_trace_card_schema(schema) == []
    card = {
        "trace_card_id": "state_tracking_trace_001",
        "source_hash": "sha256:compact_source",
        "entry_id": "state_tracking_v0",
        "behavior_cluster": "multi_turn_state_lost",
        "observed_failure_pattern": "state carryover dropped across turns",
        "state_variable_lost": "selected_entity",
        "turn_span_summary": "compact summary only",
        "allowed_compact_evidence": ["archive_entry:state_tracking_v0"],
        "forbidden_fields_absent": True,
    }
    assert validate_card(card, "card") == []
    mutated = copy.deepcopy(card)
    mutated.pop("state_variable_lost")
    assert any("state_variable_lost_required" in blocker for blocker in validate_card(mutated, "card"))


def test_abhe_dev_feedback_schema_and_record_contract() -> None:
    schema = load(Path("abhe_archive/dev_feedback.schema.json"))
    assert validate_schema(schema) == []
    row = {
        "entry_id": "state_tracking_v0",
        "dev_run_id_hash": "sha256:dev_run",
        "fresh_dev_slice_hash": "sha256:fresh_slice",
        "target_bucket_reduction": 1.0,
        "fixed_count": 3,
        "regressed_count": 1,
        "net_fixed": 2,
        "non_target_regression_count": 0,
        "activation_precision": 1.0,
        "activation_recall": 0.5,
        "cost_delta_pct": 0.0,
        "latency_delta_pct": 0.0,
        "leakage_count": 0,
        "boundary_violation_count": 0,
        "provider_model_protocol_match": True,
        "raw_material_absent": True,
        "candidate_pool_created": False,
        "holdout_touched": False,
        "full_suite_touched": False,
    }
    assert validate_feedback(row, "feedback") == []
    mutated = copy.deepcopy(row)
    mutated["candidate_pool_created"] = True
    assert any("candidate_pool_created_must_be_false" in blocker for blocker in validate_feedback(mutated, "feedback"))


def test_abhe_no_leakage_allows_negative_markdown_taxonomy() -> None:
    blockers = scan_value(
        {"markdown_lines": [{"line_number": 1, "text": "Raw case id is forbidden and must not be included."}]},
        label="doc",
    )
    assert blockers == []


def test_abhe_no_leakage_default_paths_cover_abhe_docs_and_packets() -> None:
    summary = check_paths([
        Path("docs/stage1_abhe_fresh_dev_slice_boundary.md"),
        Path("docs/stage1_abhe_approval_lanes.md"),
        Path("docs/stage1_abhe_trace_packet_boundary.md"),
        Path("docs/stage1_abhe_trace_card_contract.md"),
        Path("docs/stage1_abhe_post_dev_update_contract.md"),
        Path("docs/stage1_abhe_search_memory_watch_split_proposal.md"),
        Path("docs/stage1_abhe_state_tracking_candidate_spec_draft.md"),
        Path("docs/stage1_abhe_hallucination_abstain_candidate_spec_draft.md"),
        Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_review_request.json"),
        Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_review_bundle.json"),
        Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_approval_chain.json"),
        Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_execution_approval.schema.json"),
        Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_trace_extraction_approval.schema.json"),
        Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_fresh_dev_slice_approval.schema.json"),
        Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_candidate_spec_approval.schema.json"),
        Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_temporary_trace_extraction_packet.json"),
        Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_bounded_dev_smoke_execution_packet.json"),
        Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_fresh_dev_slice_request.json"),
        Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_trace_card.schema.json"),
    ])
    assert summary["abhe_no_leakage_boundary_passed"] is True


def test_abhe_planning_ready_report_is_review_ready_not_execution_ready() -> None:
    report = build_report()
    assert report["abhe_planning_ready"] is True
    assert report["trace_packet_ready_for_review"] is True
    assert report["trace_card_contract_ready"] is True
    assert report["dev_smoke_packet_ready_for_review"] is True
    assert report["post_dev_feedback_contract_ready"] is True
    assert report["review_request_ready"] is True
    assert report["review_bundle_ready"] is True
    assert report["approval_chain_ready_for_review"] is True
    assert report["trace_extraction_approval_schema_ready"] is True
    assert report["fresh_dev_slice_approval_schema_ready"] is True
    assert report["candidate_spec_approval_schema_ready"] is True
    assert report["execution_approval_schema_ready"] is True
    assert report["execution_approval_packet_present"] is False
    assert report["candidate_spec_drafts_ready"] is True
    assert report["post_dev_synthetic_planner_ready"] is True
    assert report["state_transition_dry_run_ready"] is True
    assert report["next_required_action"] in {"restore_provider_env_and_materialize_real_runner_adapter_before_execution", "resolve_execution_readiness_blockers_before_bfcl_execution", "review_compact_dev_feedback_before_any_archive_write", "request_expanded_40_60_case_dev_smoke_not_full_bfcl", "instrument_why_target_bfcl_requests_do_not_present_bindable_missing_slots_before_next_bfcl_run", "design_pre_generation_or_post_decode_observability_for_provider_generated_valid_calls_before_bfcl_rerun", "implement_pre_generation_post_decode_observability_no_provider_fixture_before_bfcl_rerun", "review_observability_fixture_before_any_bfcl_rerun", "request_bounded_bfcl_rerun_approval_with_observability_enabled", "build_scorer_unit_aligned_residual_diagnostic_before_more_bfcl", "implement_scorer_unit_aligned_result_parser_or_slice_before_more_bfcl", "redesign_residual_slice_at_scorer_unit_level_or_enable_per_turn_scoring_before_more_bfcl", "build_scorer_unit_distinct_residual_slice_or_enable_true_per_turn_scoring_before_more_bfcl", "fix_score_output_contract_or_enable_true_per_selected_or_per_turn_scoring_before_more_bfcl", "approve_bounded_rerun_only_after_true_per_selected_or_distinct_scorer_unit_output_gate", "request_explicit_distinct_residual_bounded_rerun_approval", "instrument_runner_scorer_to_emit_compact_alignment_sidecar_before_more_bfcl", "request_bounded_rerun_with_compact_alignment_sidecar_enabled"}
    assert report["execution_authorized"] is False
    assert report["scorer_authorized"] is False
    assert report["performance_evidence"] is False


def test_abhe_fresh_dev_slice_request_keeps_discovery_cases_out_of_validation() -> None:
    request = load(Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_fresh_dev_slice_request.json"))
    assert validate_fresh_slice_request(request) == []
    mutated = copy.deepcopy(request)
    mutated["source_160_compact_cases_reused_for_validation"] = True
    assert any("source_160_compact_cases_reused_for_validation_not_false" in blocker for blocker in validate_fresh_slice_request(mutated))


def test_abhe_dry_run_manifest_contract_rejects_execution_side_effects() -> None:
    manifest = {
        "artifact_kind": "abhe_dev_smoke_dry_run_manifest",
        "schema_version": "abhe_dev_smoke_dry_run_manifest_v0",
        "arm": "baseline",
        "fresh_dev_slice": "pending_approved_fresh_dev_slice",
        "dry_run": True,
        "compact_only": True,
        "no_provider": True,
        "no_bfcl": True,
        "no_scorer": True,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "candidate_generated": False,
        "candidate_jsonl_created": False,
        "performance_evidence": False,
        "execution_authorized": False,
        "runner_mode": "dry_run_only",
    }
    assert validate_manifest(manifest) == []
    mutated = copy.deepcopy(manifest)
    mutated["provider_calls_made"] = True
    assert any("provider_calls_made_not_false" in blocker for blocker in validate_manifest(mutated))


def test_abhe_review_request_is_request_only() -> None:
    request = load(Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_review_request.json"))
    assert validate_review_request(request) == []
    mutated = copy.deepcopy(request)
    mutated["authorized"] = True
    assert any("authorized_not_false" in blocker for blocker in validate_review_request(mutated))


def test_abhe_execution_approval_schema_ready_but_packet_missing_fail_closed() -> None:
    summary = check_execution_approval_packet()
    assert summary["schema_passed"] is True
    assert summary["packet_present"] is False
    assert "execution_approval_packet_missing" in summary["blockers"]


def test_abhe_candidate_spec_drafts_are_review_docs_only() -> None:
    summary = check_candidate_specs()
    assert summary["abhe_candidate_spec_drafts_passed"] is True
    assert summary["candidate_rule_generated"] is False
    assert summary["candidate_yaml_generated"] is False
    assert summary["candidate_jsonl_generated"] is False


def test_abhe_execution_readiness_is_false_until_materialized_approval_chain_exists() -> None:
    report = build_execution_readiness_report()
    assert report["abhe_execution_ready"] is False
    assert report["execution_readiness_check_passed"] is True
    assert report["dry_run_runner_materialized"] is True
    assert "fresh_dev_slice_not_materialized" in report["blockers"]
    assert "execution_approval_missing" in report["blockers"]
    assert "candidate_rule_not_generated_or_authorized" in report["blockers"]
    assert "runtime_config_not_selected" in report["blockers"]
    assert "scorer_authorization_false" in report["blockers"]
