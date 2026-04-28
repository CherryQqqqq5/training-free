from __future__ import annotations

import json
from pathlib import Path

import scripts.build_policy_conversion_candidate_manifest as manifest
import scripts.check_postcondition_guided_policy_manifest as checker


def _wj(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_policy_candidate_manifest_keeps_runtime_disabled_and_requires_review(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    _wj(audit, {"sample_candidates": [{
        "trace_relative_path": "soft/traces/1.json",
        "run_name": "soft",
        "postcondition_gap": "read_content",
        "recommended_tools": ["cat"],
        "available_tools": ["cat", "grep"],
        "expected_observation_keys": ["file_content"],
        "request_predicates": ["prior_tool_outputs_present"],
        "failure_labels": ["(POST_TOOL,POST_TOOL_PROSE_SUMMARY)"],
        "disambiguation_cue": "display",
        "precondition_observable": True,
        "postcondition_witness_available": True,
        "target_or_scorer_field_dependency": False,
    }]})

    report = manifest.evaluate(audit)

    assert report["candidate_count"] == 1
    assert report["runtime_enabled"] is False
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    assert report["low_risk_dry_run_review_eligible_count"] == 1
    row = report["candidate_records"][0]
    assert row["retention_eligibility"] == "diagnostic_only_until_family_review"
    assert row["requires_reviewer_approval_before_runtime"] is True
    assert row["risk_level"] == "low"
    assert row["exact_tool_choice"] is False
    assert row["available_tools"] == ["cat", "grep"]
    assert row["disambiguation_cue"] == "display"
    assert row["source_audit_record_id"].startswith("pcop_")
    assert row["forbidden_field_scan"]["forbidden_dependency_present"] is False
    assert row["low_risk_dry_run_review_eligible"] is True


def test_policy_candidate_manifest_marks_copy_move_as_high_risk(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    _wj(audit, {"sample_candidates": [{
        "postcondition_gap": "copy",
        "recommended_tools": ["cp"],
        "available_tools": ["cp"],
        "expected_observation_keys": ["target_path_changed"],
        "precondition_observable": True,
        "postcondition_witness_available": True,
        "target_or_scorer_field_dependency": False,
    }]})

    report = manifest.evaluate(audit)

    assert report["risk_level_distribution"] == {"high": 1}
    assert "copy_move_or_directory_policy_without_reviewer_approval" in report["rejection_criteria"]
    row = report["candidate_records"][0]
    assert row["low_risk_dry_run_review_eligible"] is False
    assert "copy_move_destructive" in row["ambiguity_flags"]


def test_policy_manifest_flags_directory_create_ambiguity(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    _wj(audit, {"sample_candidates": [{
        "trace_relative_path": "required/traces/abc.json",
        "postcondition_gap": "create_file",
        "recommended_tools": ["touch"],
        "available_tools": ["touch", "mkdir"],
        "expected_observation_keys": ["file_exists"],
        "failure_labels": ["(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)"],
        "request_predicates": ["prior_tool_outputs_present", "tools_available"],
        "disambiguation_cue": "create",
        "user_text_excerpt": "Move final_report.pdf to temp directory. Make sure to create the directory.",
        "precondition_observable": True,
        "postcondition_witness_available": True,
        "target_or_scorer_field_dependency": False,
    }]})

    row = manifest.evaluate(audit)["candidate_records"][0]

    assert row["risk_level"] == "medium"
    assert "directory_vs_file_ambiguous" in row["ambiguity_flags"]
    assert "multi_step_required" in row["ambiguity_flags"]
    assert row["low_risk_dry_run_review_eligible"] is False


def test_postcondition_policy_manifest_checker_passes_hardened_manifest(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    manifest_path = tmp_path / "manifest.json"
    _wj(audit, {"sample_candidates": [{
        "trace_relative_path": "soft/traces/1.json",
        "postcondition_gap": "search_or_find",
        "recommended_tools": ["grep", "find"],
        "available_tools": ["grep", "find"],
        "expected_observation_keys": ["matching_results"],
        "request_predicates": ["prior_tool_outputs_present"],
        "failure_labels": ["(POST_TOOL,POST_TOOL_PROSE_SUMMARY)"],
        "disambiguation_cue": "search",
        "precondition_observable": True,
        "postcondition_witness_available": True,
        "target_or_scorer_field_dependency": False,
    }]})
    report = manifest.evaluate(audit)
    _wj(manifest_path, report)

    check = checker.evaluate(manifest_path)

    assert check["postcondition_guided_policy_manifest_check_passed"] is True
    assert check["low_risk_dry_run_review_eligible_count"] == 1


def test_postcondition_policy_manifest_checker_rejects_missing_audit_fields(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    _wj(manifest_path, {
        "runtime_enabled": False,
        "candidate_commands": [],
        "planned_commands": [],
        "candidate_records": [{
            "candidate_id": "bad",
            "risk_level": "low",
            "postcondition_gap": "read_content",
            "recommended_tools": ["cat"],
            "runtime_enabled": False,
            "exact_tool_choice": False,
            "low_risk_dry_run_review_eligible": True,
        }],
    })

    check = checker.evaluate(manifest_path)

    assert check["postcondition_guided_policy_manifest_check_passed"] is False
    assert check["first_failure"]["check"] == "required_candidate_fields"
