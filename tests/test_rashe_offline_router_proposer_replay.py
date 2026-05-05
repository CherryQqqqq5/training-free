from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_rashe_offline_router_proposer_replay import (
    ALLOWED_SEED_SKILLS,
    CATEGORY_ROUTING,
    DEFAULT_PACKET,
    DISALLOWED_SEED_SKILLS,
    SELECTED_SKILL_COUNTS,
    validate_packet,
    validate_report,
)
from scripts.run_rashe_offline_router_proposer_replay import build_report, write_report


def test_packet_is_approved_for_compact_report_only() -> None:
    packet = json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))
    assert validate_packet(packet) == []
    assert packet["approval_status"] == "approved"
    assert packet["authorized"] is True
    assert packet["allowed_seed_skills"] == ALLOWED_SEED_SKILLS
    assert packet["disallowed_seed_skills"] == DISALLOWED_SEED_SKILLS
    for key in (
        "candidate_jsonl_created", "candidate_pool_created", "candidate_activation_authorized",
        "bfcl_generate_executed", "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed",
        "dev_holdout_material_used", "performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready", "raw_outputs_committed",
    ):
        assert packet[key] is False


def test_build_report_routes_only_signed_compact_buckets() -> None:
    report = build_report(DEFAULT_PACKET)
    assert validate_report(report) == []
    assert report["artifact_kind"] == "rashe_offline_router_proposer_replay_report"
    assert report["candidate_proposer_ready_passed"] is True
    assert report["input_mode"] == "compact_source_diagnostics_only"
    assert report["replay_mode"] == "offline_router_proposer_report_only"
    assert report["allowed_seed_skills"] == ALLOWED_SEED_SKILLS
    assert report["disallowed_seed_skills"] == DISALLOWED_SEED_SKILLS
    assert report["total_source_cases"] == 160
    assert report["selected_skill_counts"] == SELECTED_SKILL_COUNTS
    assert report["category_routing"] == CATEGORY_ROUTING
    assert report["forbidden_skill_selection_count"] == 0
    assert report["ambiguous_or_leakage_fail_closed_count"] == 0
    assert report["no_leakage_audit_passed"] is True
    assert report["blockers"] == []


def test_write_report_and_markdown(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    md = tmp_path / "report.md"
    report = write_report(output, md, DEFAULT_PACKET)
    assert output.exists()
    assert md.exists()
    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded == report
    assert validate_report(loaded) == []


def test_checker_rejects_forbidden_material_and_execution_flags() -> None:
    report = build_report(DEFAULT_PACKET)
    for key in (
        "candidate_jsonl_created", "candidate_pool_created", "candidate_activation_authorized",
        "bfcl_generate_executed", "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed",
        "dev_holdout_material_used", "performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready", "raw_outputs_committed",
    ):
        mutated = copy.deepcopy(report)
        mutated[key] = True
        assert any(key in blocker for blocker in validate_report(mutated))
    for key in ("prompt_text", "raw_trace", "provider_exchange", "case_id", "gold", "expected", "reference", "tool_args", "scorer_diff", "candidate_output", "candidate_jsonl", "candidate_pool"):
        mutated = copy.deepcopy(report)
        mutated[key] = "redacted"
        assert any("forbidden_key" in blocker or "invalid" in blocker for blocker in validate_report(mutated))
    mutated = copy.deepcopy(report)
    mutated["note"] = "raw prompt with scorer diff and candidate output"
    assert any("forbidden_value" in blocker or "invalid" in blocker for blocker in validate_report(mutated))


def test_no_disallowed_skill_is_selected() -> None:
    report = build_report(DEFAULT_PACKET)
    selected = {row["selected_skill"] for row in report["category_routing"].values()}
    assert not (selected & set(DISALLOWED_SEED_SKILLS))
    assert report["category_routing"]["agentic_web_search"]["selected_skill"] == "no_spec_selected"
    assert report["category_routing"]["agentic_memory"]["selected_skill"] == "no_spec_selected"
