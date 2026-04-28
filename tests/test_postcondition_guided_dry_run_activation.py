from __future__ import annotations

import json
from pathlib import Path

import yaml

import scripts.audit_postcondition_guided_dry_run_activation as audit


def _wj(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_activation_audit_reports_approved_replay_and_ambiguous_generic_risk(tmp_path: Path) -> None:
    policy_dir = tmp_path / "policy"
    policy_dir.mkdir()
    (policy_dir / "policy_unit.yaml").write_text(yaml.safe_dump({
        "runtime_enabled": False,
        "candidate_commands": [],
        "planned_commands": [],
        "policy_units": [{
            "policy_unit_id": "read",
            "runtime_enabled": False,
            "tool_choice_mode": "soft",
            "exact_tool_choice": False,
            "trigger": {"postcondition_gap": "read_content"},
            "decision_policy": {"recommended_tools": ["cat"], "argument_policy": "no_argument_creation_or_binding"},
        }],
    }), encoding="utf-8")
    _wj(policy_dir / "policy_approval_manifest.json", {
        "approval_records": [{"candidate_id": "approved"}],
        "candidate_commands": [],
        "planned_commands": [],
    })
    manifest = tmp_path / "manifest.json"
    _wj(manifest, {"candidate_records": [
        {"candidate_id": "approved", "postcondition_gap": "read_content", "recommended_tools": ["cat"], "low_risk_dry_run_review_eligible": True, "ambiguity_flags": []},
        {"candidate_id": "ambiguous", "postcondition_gap": "read_content", "recommended_tools": ["cat"], "low_risk_dry_run_review_eligible": True, "ambiguity_flags": ["multi_step_required"], "source_audit_record_id": "pcop_x"},
        {"candidate_id": "other", "postcondition_gap": "copy", "recommended_tools": ["cp"], "low_risk_dry_run_review_eligible": False, "ambiguity_flags": []},
    ]})

    report = audit.evaluate(policy_dir, manifest)

    assert report["activation_audit_scope"] == "approved_record_replay_only"
    assert report["approved_record_replay_activation_count"] == 1
    assert report["generic_low_risk_match_without_ambiguity_guard_count"] == 2
    assert report["ambiguous_low_risk_would_activate_without_guard_count"] == 1
    assert report["generic_low_risk_match_with_ambiguity_guard_count"] == 1
    assert report["trace_level_ambiguity_guard_spec_ready"] is True
    assert report["runtime_generalization_ready"] is False
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
