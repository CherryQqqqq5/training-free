from __future__ import annotations

import json
from pathlib import Path

import scripts.simulate_memory_operation_activation as sim


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_activation_simulation_activates_first_pass_resolved_record(tmp_path: Path) -> None:
    resolver = tmp_path / "resolver.json"
    negative = tmp_path / "negative.json"
    approval = tmp_path / "approval.json"
    _write(resolver, {
        "requested_capability_families": ["memory_value_retrieve"],
        "resolver_records": [{
            "support_record_hash": "memsup_1",
            "category": "memory_kv",
            "policy_unit_id": "memory_first_pass_retrieve_soft_v1",
            "resolved_tool_families": {"memory_value_retrieve": ["core_memory_retrieve"]},
            "argument_policy": "no_argument_creation_or_binding",
            "exact_tool_choice": False,
            "runtime_enabled": False,
        }],
    })
    _write(negative, {"negative_control_evaluations": {"no_memory_tools": {"activation_count": 0}}})
    _write(approval, {"second_pass_review_candidate_count": 3})

    report = sim.evaluate(resolver, negative, approval)

    assert report["activation_simulation_passed"] is True
    assert report["activation_count"] == 1
    assert report["argument_creation_count"] == 0
    assert report["candidate_commands"] == []


def test_activation_simulation_fails_when_negative_control_activates(tmp_path: Path) -> None:
    resolver = tmp_path / "resolver.json"
    negative = tmp_path / "negative.json"
    approval = tmp_path / "approval.json"
    _write(resolver, {
        "resolver_records": [{
            "support_record_hash": "memsup_1",
            "category": "memory_kv",
            "policy_unit_id": "memory_first_pass_retrieve_soft_v1",
            "resolved_tool_families": {"memory_value_retrieve": ["core_memory_retrieve"]},
            "argument_policy": "no_argument_creation_or_binding",
            "exact_tool_choice": False,
            "runtime_enabled": False,
        }],
    })
    _write(negative, {"negative_control_evaluations": {"no_memory_tools": {"activation_count": 1}}})
    _write(approval, {})

    report = sim.evaluate(resolver, negative, approval)

    assert report["activation_simulation_passed"] is False
    assert report["negative_control_activation_count"] == 1


def test_activation_simulation_blocks_empty_resolution(tmp_path: Path) -> None:
    resolver = tmp_path / "resolver.json"
    negative = tmp_path / "negative.json"
    approval = tmp_path / "approval.json"
    _write(resolver, {
        "resolver_records": [{
            "support_record_hash": "memsup_1",
            "category": "memory_kv",
            "policy_unit_id": "memory_first_pass_retrieve_soft_v1",
            "resolved_tool_families": {},
            "argument_policy": "no_argument_creation_or_binding",
            "exact_tool_choice": False,
            "runtime_enabled": False,
        }],
    })
    _write(negative, {"negative_control_evaluations": {"no_memory_tools": {"activation_count": 0}}})
    _write(approval, {})

    report = sim.evaluate(resolver, negative, approval)

    assert report["activation_simulation_passed"] is False
    assert report["blocked_count"] == 1
