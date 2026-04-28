from __future__ import annotations

import json
from pathlib import Path

import yaml

import scripts.build_postcondition_guided_dry_run_policy as build
import scripts.check_postcondition_guided_dry_run_policy as check


def _wj(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _manifest(path: Path) -> None:
    _wj(path, {
        "policy_family": "postcondition_guided_trajectory_policy",
        "candidate_count": 4,
        "low_risk_dry_run_review_eligible_count": 3,
        "runtime_enabled": False,
        "candidate_records": [
            {
                "candidate_id": "c1",
                "source_audit_record_id": "pcop_1",
                "source_audit_record_pointer": "run/traces/one.json",
                "postcondition_gap": "read_content",
                "recommended_tools": ["cat"],
                "risk_level": "low",
                "ambiguity_flags": [],
                "low_risk_dry_run_review_eligible": True,
                "forbidden_field_scan": {"forbidden_dependency_present": False},
            },
            {
                "candidate_id": "c2",
                "source_audit_record_id": "pcop_2",
                "source_audit_record_pointer": "run/traces/two.json",
                "postcondition_gap": "search_or_find",
                "recommended_tools": ["grep", "find"],
                "risk_level": "low",
                "ambiguity_flags": [],
                "low_risk_dry_run_review_eligible": True,
                "forbidden_field_scan": {"forbidden_dependency_present": False},
            },
            {
                "candidate_id": "c3",
                "source_audit_record_id": "pcop_3",
                "source_audit_record_pointer": "run/traces/three.json",
                "postcondition_gap": "search_or_find",
                "recommended_tools": ["grep", "find"],
                "risk_level": "low",
                "ambiguity_flags": ["multi_step_required"],
                "low_risk_dry_run_review_eligible": True,
                "forbidden_field_scan": {"forbidden_dependency_present": False},
            },
            {
                "candidate_id": "c4",
                "source_audit_record_id": "pcop_4",
                "source_audit_record_pointer": "run/traces/four.json",
                "postcondition_gap": "copy",
                "recommended_tools": ["cp"],
                "risk_level": "high",
                "ambiguity_flags": ["copy_move_destructive"],
                "low_risk_dry_run_review_eligible": False,
                "forbidden_field_scan": {"forbidden_dependency_present": False},
            },
        ],
    })


def test_builds_non_ambiguous_low_risk_policy_units_without_runtime_case_fields(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    out = tmp_path / "out"
    _manifest(manifest)

    report = build.evaluate(manifest)
    build.write_outputs(report, out)

    assert report["selected_non_ambiguous_low_risk_count"] == 2
    assert report["reviewer_excluded_ambiguous_low_risk_count"] == 1
    assert report["policy_unit_count"] == 2
    policy_text = (out / "policy_unit.yaml").read_text()
    assert "run/traces" not in policy_text
    assert "candidate_id" not in policy_text
    policy = yaml.safe_load(policy_text)
    assert policy["runtime_enabled"] is False
    assert policy["candidate_commands"] == []
    assert policy["planned_commands"] == []
    for unit in policy["policy_units"]:
        assert unit["runtime_enabled"] is False
        assert unit["tool_choice_mode"] == "soft"
        assert unit["exact_tool_choice"] is False
        assert unit["decision_policy"]["argument_policy"] == "no_argument_creation_or_binding"
        assert unit["ambiguity_guard"]["require_ambiguity_flags_empty"] is True


def test_dry_run_policy_checker_passes_compiled_artifact(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    out = tmp_path / "out"
    _manifest(manifest)
    build.write_outputs(build.evaluate(manifest), out)

    report = check.evaluate(out)

    assert report["dry_run_policy_boundary_check_passed"] is True
    assert report["policy_unit_count"] == 2
    assert report["selected_non_ambiguous_low_risk_count"] == 2


def test_dry_run_policy_checker_rejects_trace_pointer_in_runtime_policy(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "policy_unit.yaml").write_text(yaml.safe_dump({
        "runtime_enabled": False,
        "candidate_commands": [],
        "planned_commands": [],
        "policy_units": [{
            "policy_unit_id": "bad",
            "runtime_enabled": False,
            "tool_choice_mode": "soft",
            "exact_tool_choice": False,
            "trigger": {"postcondition_gap": "read_content", "trace_relative_path": "run/traces/x.json"},
            "decision_policy": {"recommended_tools": ["cat"], "argument_policy": "no_argument_creation_or_binding"},
        }],
    }), encoding="utf-8")
    _wj(out / "policy_approval_manifest.json", {"runtime_enabled": False, "selected_non_ambiguous_low_risk_count": 1, "candidate_commands": [], "planned_commands": []})
    _wj(out / "compile_status.json", {"runtime_enabled": False})

    report = check.evaluate(out)

    assert report["dry_run_policy_boundary_check_passed"] is False
    assert report["first_failure"]["check"] == "runtime_policy_forbidden_text"
