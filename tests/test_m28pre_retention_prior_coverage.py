from __future__ import annotations

import json
from pathlib import Path

from scripts.diagnose_m28pre_retention_prior_coverage import (
    BUCKET_AMBIGUOUS,
    BUCKET_CURRENT_CONTEXT,
    BUCKET_NO_OBSERVABLE,
    BUCKET_SOURCE_RESULT_ONLY,
    evaluate,
)
from scripts.check_m28pre_offline import evaluate as evaluate_m28pre


def _wj(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _wjl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _explicit_row(**overrides: object) -> dict:
    row = {
        "case_id": "case_a",
        "category": "simple_python",
        "tool": "calculate",
        "required_arg": "height",
        "literal_value": "12",
        "literal_source": "current_request",
        "literal_source_anchor": "current_request",
        "literal_candidate_count": 1,
        "literal_type_match": True,
        "candidate_rules_type": "explicit_required_arg_literal_completion",
        "rule_type": "explicit_required_arg_literal_completion",
        "no_next_tool_intervention": True,
        "exact_tool_choice": False,
        "ctspc_v0_action_rule": False,
        "retention_prior": {
            "rule_family": "explicit_required_arg_literal_completion",
            "retain_eligibility": "demote_candidate",
            "literal_uniqueness": True,
            "schema_type_match": True,
            "literal_source_observed_as": "current_request",
        },
    }
    row.update(overrides)
    return row


def test_coverage_audit_buckets_current_source_result_ambiguous_and_none(tmp_path: Path) -> None:
    root = tmp_path / "low"
    _wj(root / "compiler_summary.json", {"retain_eligible_candidate_count": 1})
    _wjl(root / "candidate_rules.jsonl", [
        _explicit_row(case_id="bucket_a"),
        _explicit_row(
            case_id="bucket_b",
            literal_source="source_result_tool_args",
            literal_candidate_count=0,
            literal_type_match=False,
            retention_prior={
                "rule_family": "explicit_required_arg_literal_completion",
                "retain_eligibility": "diagnostic_only",
                "prior_rejection_reason": "literal_source_not_observable",
                "schema_type_match": True,
                "literal_uniqueness": False,
                "literal_source_observed_as": "source_result_tool_args",
            },
        ),
    ])
    _wjl(root / "rejected_candidates.jsonl", [
        _explicit_row(
            case_id="bucket_c",
            literal_value=None,
            literal_candidate_count=2,
            rejection_reason="ambiguous_or_missing_observable_literal",
            retention_prior={
                "rule_family": "explicit_required_arg_literal_completion",
                "retain_eligibility": "diagnostic_only",
                "schema_type_match": True,
                "literal_uniqueness": False,
                "prior_rejection_reason": "ambiguous_or_missing_observable_literal",
                "literal_source_observed_as": "current_request",
            },
        ),
        _explicit_row(
            case_id="bucket_d",
            literal_value=None,
            literal_source=None,
            literal_candidate_count=0,
            rejection_reason="required_args_already_present_or_no_matching_emitted_tool",
            retention_prior={
                "rule_family": "explicit_required_arg_literal_completion",
                "retain_eligibility": "diagnostic_only",
                "schema_type_match": False,
                "literal_uniqueness": False,
                "prior_rejection_reason": "required_args_already_present_or_no_matching_emitted_tool",
            },
        ),
    ])

    report = evaluate(root, tmp_path / "missing_source_manifest.json")

    assert report["coverage_bucket_counts"] == {
        BUCKET_CURRENT_CONTEXT: 1,
        BUCKET_SOURCE_RESULT_ONLY: 1,
        BUCKET_AMBIGUOUS: 1,
        BUCKET_NO_OBSERVABLE: 1,
    }
    assert report["records"][0]["source_span"] == "current_request"
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    assert report["explicit_prior_family_coverage_zero"] is False


def test_coverage_zero_keeps_m28pre_scorer_authorization_blocked(tmp_path: Path) -> None:
    subset = tmp_path / "subset"
    low = tmp_path / "low"
    _wj(subset / "m27ae_ctspc_v0_status.json", {
        "ctspc_v0_frozen": True,
        "scorer_default": "off",
        "retain": 0,
        "dev_rerun_authorized": False,
        "holdout_authorized": False,
    })
    _wj(subset / "repair_stack_contribution.json", {"repair_stack_split_ready": True})
    _wj(low / "compiler_summary.json", {
        "compiler_ready": True,
        "explicit_holdout_ready": True,
        "ctspc_v0_action_rules_enabled": False,
        "ctspc_v0_file_path_multi_turn_enabled": False,
        "repair_stack_default": "disabled",
        "candidate_rules_type": "explicit_required_arg_literal_completion",
        "no_next_tool_intervention": True,
        "exact_tool_choice": False,
        "retention_prior_required": True,
        "retain_eligible_candidate_count": 35,
        "required_explicit_candidate_generatable": 35,
        "planned_commands": [],
        "candidate_commands": [],
    })
    _wj(low / "explicit_required_arg_literal_dev20_manifest.json", {"selected_case_ids": [f"d{i}" for i in range(20)], "planned_commands": []})
    _wj(low / "explicit_required_arg_literal_holdout20_manifest.json", {"selected_case_ids": [f"h{i}" for i in range(20)], "planned_commands": []})
    _wj(low / "retention_prior_coverage_audit.json", {
        "m28pre_retention_prior_coverage_audit_ready": True,
        "explicit_prior_family_coverage_zero": True,
        "current_context_anchored_literal_candidate_count": 0,
        "candidate_commands": [],
        "planned_commands": [],
    })

    report = evaluate_m28pre(subset, low)

    assert report["retention_prior_coverage_audit_ready"] is True
    assert report["explicit_prior_family_coverage_zero"] is True
    assert "explicit_prior_family_coverage_zero" in report["blockers"]
    assert report["scorer_authorization_ready"] is False
    assert report["m2_8pre_offline_passed"] is False


def test_non_explicit_rows_are_ignored(tmp_path: Path) -> None:
    root = tmp_path / "low"
    _wjl(root / "candidate_rules.jsonl", [{"case_id": "ctspc", "rule_type": "required_next_tool_choice", "retention_prior": {"rule_family": "required_next_tool_choice", "retain_eligibility": "never_retain"}}])

    report = evaluate(root, tmp_path / "missing.json")

    assert report["coverage_bucket_counts"][BUCKET_CURRENT_CONTEXT] == 0
    assert report["records"] == []
    assert report["explicit_prior_family_coverage_zero"] is True
