from __future__ import annotations

import json
from pathlib import Path

import scripts.build_policy_conversion_candidate_manifest as manifest


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
        "expected_observation_keys": ["file_content"],
        "request_predicates": ["prior_tool_outputs_present"],
        "failure_labels": ["(POST_TOOL,POST_TOOL_PROSE_SUMMARY)"],
        "precondition_observable": True,
        "postcondition_witness_available": True,
        "target_or_scorer_field_dependency": False,
    }]})

    report = manifest.evaluate(audit)

    assert report["candidate_count"] == 1
    assert report["runtime_enabled"] is False
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    row = report["candidate_records"][0]
    assert row["retention_eligibility"] == "diagnostic_only_until_family_review"
    assert row["requires_reviewer_approval_before_runtime"] is True
    assert row["risk_level"] == "low"
    assert row["exact_tool_choice"] is False


def test_policy_candidate_manifest_marks_copy_move_as_high_risk(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    _wj(audit, {"sample_candidates": [{
        "postcondition_gap": "copy",
        "recommended_tools": ["cp"],
        "expected_observation_keys": ["target_path_changed"],
        "precondition_observable": True,
        "postcondition_witness_available": True,
        "target_or_scorer_field_dependency": False,
    }]})

    report = manifest.evaluate(audit)

    assert report["risk_level_distribution"] == {"high": 1}
    assert "copy_move_or_directory_policy_without_reviewer_approval" in report["rejection_criteria"]
