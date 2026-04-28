from __future__ import annotations

import json
from pathlib import Path

import yaml

import scripts.build_memory_operation_dry_run_policy as build
import scripts.check_memory_operation_dry_run_policy as check


def _allowlist(path: Path, records: list[dict]) -> None:
    payload = {
        "report_scope": "memory_operation_obligation_compiler_allowlist",
        "runtime_enabled": False,
        "compiler_enabled": False,
        "exact_tool_choice": False,
        "candidate_commands": [],
        "planned_commands": [],
        "compiler_allowlist_ready": True,
        "compiler_input_eligible_count": len(records),
        "compiler_scope": "first_pass_retrieve_no_witness_only",
        "weak_witness_compiler_input_count": 0,
        "compiler_contract": {
            "compiler_must_read_only_this_allowlist": True,
            "raw_audit_forbidden_as_compiler_input": True,
            "review_manifest_forbidden_as_compiler_input": True,
            "second_pass_weak_witness_requires_separate_allowlist": True,
        },
        "allowlist_records": records,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _record(idx: int = 1, **overrides) -> dict:
    row = {
        "support_record_hash": f"memsup_{idx:016x}",
        "category": "memory_kv",
        "policy_family": "memory_operation_obligation",
        "theory_class": "memory_postcondition_obligation",
        "operation": "retrieve",
        "operation_scope": "retrieve_only",
        "memory_witness_strength": "no_witness",
        "support_class": "first_pass_retrieve",
        "recommended_tool_capability_families": ["memory_key_or_text_search", "memory_value_retrieve"],
        "forbidden_field_scan_clean": True,
        "review_eligible": True,
        "compiler_input_eligible": True,
        "approval_status": "compiler_allowlisted_first_pass_only",
        "requires_separate_weak_witness_approval": False,
        "runtime_enabled": False,
        "exact_tool_choice": False,
        "candidate_commands": [],
        "planned_commands": [],
    }
    row.update(overrides)
    return row


def test_memory_dry_run_compiler_builds_first_pass_policy_unit(tmp_path: Path) -> None:
    allowlist = tmp_path / "allowlist.json"
    _allowlist(allowlist, [_record(1), _record(2)])

    report = build.evaluate(allowlist)

    assert report["policy_unit_count"] == 1
    assert report["selected_first_pass_count"] == 2
    unit = report["policy_units"][0]
    assert unit["policy_unit_id"] == "memory_first_pass_retrieve_soft_v1"
    assert unit["trigger"]["memory_witness_strength"] == "no_witness"
    assert unit["decision_policy"]["argument_policy"] == "no_argument_creation_or_binding"
    assert unit["exact_tool_choice"] is False
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []


def test_memory_dry_run_compiler_excludes_weak_witness_records(tmp_path: Path) -> None:
    allowlist = tmp_path / "allowlist.json"
    _allowlist(allowlist, [
        _record(1),
        _record(2, memory_witness_strength="weak_lookup_witness", support_class="second_pass_retrieve", requires_separate_weak_witness_approval=True),
    ])

    report = build.evaluate(allowlist)

    assert report["selected_first_pass_count"] == 1
    assert report["policy_units"][0]["support_count"] == 1


def test_memory_dry_run_checker_passes_compiled_artifact(tmp_path: Path) -> None:
    allowlist = tmp_path / "allowlist.json"
    out = tmp_path / "out"
    _allowlist(allowlist, [_record(1), _record(2)])
    report = build.evaluate(allowlist)
    build.write_outputs(report, out)

    check_report = check.evaluate(out)

    assert check_report["dry_run_policy_boundary_check_passed"] is True


def test_memory_dry_run_checker_rejects_support_hash_in_runtime_policy(tmp_path: Path) -> None:
    allowlist = tmp_path / "allowlist.json"
    out = tmp_path / "out"
    _allowlist(allowlist, [_record(1)])
    report = build.evaluate(allowlist)
    build.write_outputs(report, out)
    policy_path = out / "policy_unit.yaml"
    policy = yaml.safe_load(policy_path.read_text())
    policy["policy_units"][0]["support_record_hash"] = "memsup_deadbeefdeadbeef"
    policy_path.write_text(yaml.safe_dump(policy), encoding="utf-8")

    check_report = check.evaluate(out)

    assert check_report["dry_run_policy_boundary_check_passed"] is False
    assert check_report["first_failure"]["check"] == "runtime_policy_forbidden_text"
